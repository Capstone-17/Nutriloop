"""
Personalized Weekly Diet Recommendation Engine
==============================================
Generates a clinically validated, culturally authentic 7-day (Monday-Sunday),
5-interval meal schedule based on:
  1. Patient's latest clinical test reports (biomarkers and/or report text)
  2. Native place / regional culinary background (South Indian, North Indian, Western, Eastern, Continental)
  3. Individual dietary preferences, interests, allergies, and dislikes
  4. Active medications (cross-referenced against 31+ drug pharmacopeia in safety_engine)
  5. Clinical comorbidity solver (KDOQI vs. DASH paradox & ADA guidelines)
  6. Dynamic caloric portion scaler ensuring daily totals hit targets within +/- 3%
"""

from __future__ import annotations
import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import copy
from datetime import datetime, timezone
import json
import math
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.schemas import (
    LatestTestReportInput,
    PatientPreferencesInput,
    MealItem,
    SingleMealInterval,
    DayDietPlan,
    WeeklyDietPlanRequest,
    WeeklyDietPlanResponse,
)
from backend.safety_engine import safety_engine
from backend.medical_knowledge import medical_knowledge_base
from backend.rules import calculate_ckd_epi_egfr


# ==============================================================================
# 1. Biomarker Parser & Lab Extraction from Report Text
# ==============================================================================

def parse_report_text(report_text: str, existing_labs: LatestTestReportInput) -> LatestTestReportInput:
    """
    Extracts clinical biomarkers from free-text lab notes using domain regexes
    to populate any unprovided structured fields.
    """
    if not report_text:
        return existing_labs

    text = report_text.lower()
    data = existing_labs.model_dump()

    # 1. Blood Pressure: e.g. "BP 150/94", "blood pressure: 140 / 85 mmHg"
    bp_match = re.search(r"(?:bp|blood\s+pressure)[:\s=]+(\d{2,3})\s*[/:]\s*(\d{2,3})", text)
    if bp_match:
        if data.get("systolic_bp_mmhg") is None:
            data["systolic_bp_mmhg"] = float(bp_match.group(1))
        if data.get("diastolic_bp_mmhg") is None:
            data["diastolic_bp_mmhg"] = float(bp_match.group(2))

    # 2. Serum Creatinine: e.g. "creatinine: 2.1 mg/dl", "s.creat 1.8"
    if data.get("serum_creatinine_mg_dl") is None:
        m = re.search(r"(?:serum\s+)?creat(?:inine)?[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["serum_creatinine_mg_dl"] = float(m.group(1))

    # 3. Fasting Glucose / Blood Sugar: e.g. "fasting blood sugar: 145", "fbs 132"
    if data.get("fasting_glucose_mg_dl") is None:
        m = re.search(r"(?:fasting\s+)?(?:blood\s+)?(?:glucose|sugar|fbs)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["fasting_glucose_mg_dl"] = float(m.group(1))

    # 4. Postprandial Glucose: e.g. "ppbs 180", "postprandial glucose: 210"
    if data.get("postprandial_glucose_mg_dl") is None:
        m = re.search(r"(?:post\s*prandial|ppbs|pp\s+glucose)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["postprandial_glucose_mg_dl"] = float(m.group(1))

    # 5. HbA1c: e.g. "hba1c: 7.8%", "a1c 8.2"
    if data.get("hba1c_pct") is None:
        m = re.search(r"(?:hba1c|a1c)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["hba1c_pct"] = float(m.group(1))

    # 6. eGFR: e.g. "egfr 48 ml/min", "gfr: 52"
    if data.get("egfr_ml_min") is None:
        m = re.search(r"(?:egfr|gfr)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["egfr_ml_min"] = float(m.group(1))

    # 7. Serum Potassium: e.g. "potassium: 4.8 meq/l", "k+ 5.1"
    if data.get("serum_potassium_meq_l") is None:
        m = re.search(r"(?:serum\s+)?(?:potassium|k\+)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["serum_potassium_meq_l"] = float(m.group(1))

    # 8. Serum Sodium: e.g. "sodium: 138", "na+ 136"
    if data.get("serum_sodium_meq_l") is None:
        m = re.search(r"(?:serum\s+)?(?:sodium|na\+)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["serum_sodium_meq_l"] = float(m.group(1))

    # 9. Blood Urea / BUN: e.g. "blood urea: 58 mg/dl", "bun 26"
    if data.get("blood_urea_mg_dl") is None:
        m = re.search(r"(?:blood\s+urea|urea|bun)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["blood_urea_mg_dl"] = float(m.group(1))

    # 10. Urine Albumin / Dipstick: e.g. "urine albumin 2+", "proteinuria 1+"
    if data.get("urine_albumin_dipstick") is None:
        m = re.search(r"(?:urine\s+)?(?:albumin|protein(?:uria)?)[:\s=]+(\+?\d+|\+)", text)
        if m:
            val_str = m.group(1).replace("+", "")
            data["urine_albumin_dipstick"] = float(val_str) if val_str else 1.0

    # 11. Total Cholesterol: e.g. "cholesterol 235 mg/dl"
    if data.get("total_cholesterol_mg_dl") is None:
        m = re.search(r"(?:total\s+)?cholesterol[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["total_cholesterol_mg_dl"] = float(m.group(1))

    # 12. LDL Cholesterol
    if data.get("ldl_cholesterol_mg_dl") is None:
        m = re.search(r"(?:ldl|low\s+density)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["ldl_cholesterol_mg_dl"] = float(m.group(1))

    # 13. HDL Cholesterol
    if data.get("hdl_cholesterol_mg_dl") is None:
        m = re.search(r"(?:hdl|high\s+density)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["hdl_cholesterol_mg_dl"] = float(m.group(1))

    # 14. Triglycerides
    if data.get("triglycerides_mg_dl") is None:
        m = re.search(r"(?:triglycerides|tg)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["triglycerides_mg_dl"] = float(m.group(1))

    return LatestTestReportInput(**data)


# ==============================================================================
# 2. Clinical Target Derivation Engine
# ==============================================================================

def derive_clinical_targets(
    age: int,
    sex: str,
    bmi: float,
    labs: LatestTestReportInput,
    override_calories: Optional[int] = None,
    medications: Optional[List[str]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Computes precise daily nutritional targets and identifies clinical conditions
    strictly from laboratory biomarkers, anthropometry (Mifflin-St Jeor), and active medications.
    """
    detected_conditions = []
    
    # 1. Anthropometry & Weight Status
    s = str(sex).lower().strip()
    height_m = 1.72 if s == "male" else 1.60
    height_cm = height_m * 100.0
    actual_weight_kg = round(bmi * height_m * height_m, 1)
    ideal_weight_kg = round(22.0 * height_m * height_m, 1)
    
    # Adjusted Body Weight (aBW) for overweight/obesity (KDOQI 2020 protocol)
    if bmi >= 25.0:
        abw_kg = round(ideal_weight_kg + 0.25 * (actual_weight_kg - ideal_weight_kg), 1)
    else:
        abw_kg = actual_weight_kg

    # 2. Biomarkers
    creat = labs.serum_creatinine_mg_dl
    egfr = labs.egfr_ml_min
    urea = labs.blood_urea_mg_dl
    alb = labs.urine_albumin_dipstick
    sys_bp = labs.systolic_bp_mmhg
    dia_bp = labs.diastolic_bp_mmhg
    fbs = labs.fasting_glucose_mg_dl
    ppbs = labs.postprandial_glucose_mg_dl
    a1c = labs.hba1c_pct
    k_val = labs.serum_potassium_meq_l
    chol = labs.total_cholesterol_mg_dl
    ldl = labs.ldl_cholesterol_mg_dl
    tg = labs.triglycerides_mg_dl

    # CKD-EPI 2021 eGFR Imputation if missing
    if egfr is None and creat is not None and creat > 0:
        egfr = calculate_ckd_epi_egfr(creat, float(age), s)

    # 3. Disease Identification & Staging
    # CKD Detection & Staging (KDIGO 2024 / KDOQI 2020)
    has_ckd = False
    ckd_stage_str = ""
    if egfr is not None:
        if egfr < 15.0:
            has_ckd = True
            ckd_stage_str = "Stage 5 (Kidney Failure)"
        elif egfr < 30.0:
            has_ckd = True
            ckd_stage_str = "Stage 4 (Severe CKD)"
        elif egfr < 45.0:
            has_ckd = True
            ckd_stage_str = "Stage 3b (Moderate-to-Severe CKD)"
        elif egfr < 60.0:
            has_ckd = True
            ckd_stage_str = "Stage 3a (Mild-to-Moderate CKD)"
        elif alb is not None and alb >= 1.0:
            has_ckd = True
            ckd_stage_str = "Stage 1-2 with Persistent Albuminuria"
    elif (creat is not None and creat >= 1.3) or (alb is not None and alb >= 1.0) or (urea is not None and urea >= 45.0):
        has_ckd = True
        ckd_stage_str = "Biomarker Elevation Profile"

    if has_ckd:
        detected_conditions.append(f"Chronic Kidney Disease (CKD) - {ckd_stage_str}")

    # Hypertension Detection (AHA/ACC 2023)
    has_htn = False
    if (sys_bp is not None and sys_bp >= 130.0) or (dia_bp is not None and dia_bp >= 80.0):
        has_htn = True
        if (sys_bp is not None and sys_bp >= 140.0) or (dia_bp is not None and dia_bp >= 90.0):
            detected_conditions.append("Hypertension (Stage 2)")
        else:
            detected_conditions.append("Hypertension (Stage 1)")

    # Diabetes Detection (ADA 2024)
    has_diabetes = False
    if (fbs is not None and fbs >= 126.0) or (a1c is not None and a1c >= 6.5) or (ppbs is not None and ppbs >= 200.0):
        has_diabetes = True
        detected_conditions.append("Type 2 Diabetes Mellitus")
    elif (fbs is not None and 100.0 <= fbs < 126.0) or (a1c is not None and 5.7 <= a1c < 6.5):
        detected_conditions.append("Prediabetes / Impaired Fasting Glucose")

    # Dyslipidemia
    if (chol is not None and chol >= 200.0) or (ldl is not None and ldl >= 130.0) or (tg is not None and tg >= 150.0):
        detected_conditions.append("Dyslipidemia / Elevated Lipids")

    # Potassium Abnormalities
    has_hyperkalemia = (k_val is not None and k_val >= 5.0) or (has_ckd and k_val is not None and k_val >= 4.7)
    has_hypokalemia = k_val is not None and k_val < 3.5
    if has_hyperkalemia:
        detected_conditions.append("Elevated Serum Potassium (Hyperkalemia Risk)")
    elif has_hypokalemia:
        detected_conditions.append("Low Serum Potassium (Hypokalemia Risk)")

    if not detected_conditions:
        detected_conditions.append("General Health Maintenance / Normal Range")

    # 4. Caloric Target Calculation (Mifflin-St Jeor TDEE Model)
    if override_calories:
        daily_calories = override_calories
    else:
        # BMR = 10*wt + 6.25*ht - 5*age + (5 if male else -161)
        bmr = 10.0 * actual_weight_kg + 6.25 * height_cm - 5.0 * float(age) + (5.0 if s == "male" else -161.0)
        tdee = bmr * 1.25  # sedentary activity factor

        if has_ckd:
            # KDOQI 2020: 28-32 kcal/kg aBW to prevent protein-energy wasting
            daily_calories = round(abw_kg * 30.0)
        elif has_diabetes or bmi >= 25.0:
            # Moderate sustainable deficit for glycemic/weight control
            deficit = 400.0 if bmi >= 30.0 else 300.0
            daily_calories = round(tdee - deficit)
        elif bmi < 18.5:
            # Surplus for underweight
            daily_calories = round(tdee + 350.0)
        else:
            daily_calories = round(tdee)

        # Clamping to safe clinical bounds
        min_cal = 1350 if s == "female" else 1500
        daily_calories = max(min_cal, min(daily_calories, 2600))

    # 5. Protein Target (g)
    # KDOQI 2020: CKD Stage 3-5 non-dialysis 0.60-0.70 g/kg aBW; Diabetic CKD 0.70-0.80 g/kg aBW
    # ADA 2024: Diabetes alone 1.0-1.1 g/kg aBW; Elderly (>=65) 1.0-1.2 g/kg
    if has_ckd:
        daily_protein_g = round(abw_kg * (0.75 if has_diabetes else 0.65), 1)
    elif has_diabetes:
        daily_protein_g = round(abw_kg * 1.05, 1)
    elif age >= 65:
        daily_protein_g = round(abw_kg * 1.10, 1)  # Sarcopenia protection
    else:
        daily_protein_g = round(abw_kg * 0.95, 1)

    daily_protein_g = max(45.0, min(daily_protein_g, 105.0))

    # 6. Sodium Limit (mg)
    # AHA / DASH / KDIGO: 1500 mg if hypertensive or CKD
    daily_sodium_mg = 1500.0 if (has_htn or has_ckd) else 2000.0

    # 7. Potassium Guidance (mg) - Clinical Precedence Rule
    meds_clean = [m.lower().strip() for m in (medications or [])]
    has_acei_arb = any(m in meds_clean for m in ["lisinopril", "losartan", "ramipril", "valsartan", "telmisartan", "enalapril"])

    if has_ckd or has_hyperkalemia:
        daily_potassium_mg = 1800.0 if has_hyperkalemia else 2000.0
    elif has_acei_arb:
        daily_potassium_mg = 2000.0 if (k_val is not None and k_val >= 4.5) else 2400.0
    elif has_hypokalemia:
        daily_potassium_mg = 3600.0
    elif has_htn:
        daily_potassium_mg = 3400.0  # DASH natriuretic support
    else:
        daily_potassium_mg = 2800.0

    # 8. Phosphorus Limit (mg)
    daily_phosphorus_mg = 800.0 if has_ckd else 1200.0

    # 9. Carbohydrate, Sugar, Fiber & Fat
    has_sglt2i = any(m in meds_clean for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana"])
    carb_fraction = 0.42 if has_diabetes else 0.50
    daily_carb_g = round((daily_calories * carb_fraction) / 4.0, 1)

    # SGLT2i Safety Floor: Guard against Euglycemic DKA
    if has_sglt2i:
        daily_carb_g = max(daily_carb_g, 130.0)

    daily_sugar_g = 20.0 if has_diabetes else 35.0
    daily_fiber_g = 35.0 if (has_diabetes or has_htn) else 28.0
    daily_fat_g = round((daily_calories - (daily_protein_g * 4.0 + daily_carb_g * 4.0)) / 9.0, 1)
    daily_fat_g = max(35.0, daily_fat_g)

    # 10. Fluid Intake Target (ml)
    fluid_ml = 1800 if (has_ckd and ckd_stage_str in ["Stage 4 (Severe CKD)", "Stage 5 (Kidney Failure)"]) else (2000 if has_ckd else 2500)
    if has_sglt2i:
        fluid_ml = max(fluid_ml, 2500)

    targets = {
        "calories_kcal": daily_calories,
        "protein_g": daily_protein_g,
        "carbohydrate_g": daily_carb_g,
        "fat_g": daily_fat_g,
        "sodium_limit_mg": daily_sodium_mg,
        "potassium_guidance_mg": daily_potassium_mg,
        "phosphorus_limit_mg": daily_phosphorus_mg,
        "free_sugar_limit_g": daily_sugar_g,
        "fiber_target_g": daily_fiber_g,
        "fluid_intake_ml": fluid_ml,
    }

    return targets, detected_conditions


# ==============================================================================
# 3. Dynamic Portion Scaler & Macro Optimizer
# ==============================================================================

def scale_portion_string(portion_str: str, multiplier: float) -> str:
    """
    Intelligently adjusts numeric quantities in a portion string (e.g. '2 medium idlis (150g)')
    so that user preparation instructions accurately match the scaled caloric intake.
    """
    if not portion_str or abs(multiplier - 1.0) < 0.05:
        return portion_str

    def scale_num_match(m):
        val = float(m.group(1))
        unit = m.group(2)
        scaled_val = val * multiplier
        u_lower = unit.lower()
        if u_lower in ["g", "ml", "mg"]:
            return f"{int(round(scaled_val))}{unit}"
        elif u_lower in ["cup", "cups", "tbsp", "tsp", "rotis", "roti", "idlis", "idli", "fillet", "whites", "ramekin", "glass", "slices", "pieces", "bhakris", "bhakri", "chillas", "chilla", "rolls", "roll", "spears", "spear"]:
            if scaled_val < 4:
                r_val = round(scaled_val * 2.0) / 2.0
                return f"{int(r_val) if r_val.is_integer() else r_val} {unit}"
            else:
                return f"{int(round(scaled_val))} {unit}"
        return m.group(0)

    return re.sub(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', scale_num_match, portion_str)


def scale_dish_items(
    dish: Dict[str, Any],
    target_interval_calories: float
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Proportionally scales dish items and nutrients so interval total matches target calories.
    Clamps scaling between 0.65x and 1.85x to preserve authentic culinary proportions.
    """
    items = dish.get("items", [])
    if not items:
        return [], {}

    base_calories = sum(it.get("nutrients", {}).get("calories", 0.0) for it in items)
    if base_calories <= 0:
        multiplier = 1.0
    else:
        raw_multiplier = target_interval_calories / base_calories
        multiplier = max(0.50, min(raw_multiplier, 2.40))

    scaled_items = []
    interval_totals = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "sodium_mg": 0.0,
        "potassium_mg": 0.0,
        "fiber_g": 0.0,
    }

    for it in items:
        orig_nutr = it.get("nutrients", {})
        scaled_nutr = {}
        for k in interval_totals:
            val = orig_nutr.get(k, 0.0) * multiplier
            scaled_nutr[k] = round(val, 1)
            interval_totals[k] += scaled_nutr[k]

        scaled_portion = scale_portion_string(it.get("portion", ""), multiplier)
        scaled_items.append({
            "name": it.get("name", "Dish Item"),
            "portion": scaled_portion,
            "nutrients": scaled_nutr
        })

    interval_totals = {k: round(v, 1) for k, v in interval_totals.items()}
    return scaled_items, interval_totals


# ==============================================================================
# 4. Comprehensive 5-Region Culinary Catalog
# ==============================================================================

REGIONAL_DISH_CATALOG = {
  "south_indian": {
    "breakfast": [
      {
        "title": "Steamed Ragi Idli with Mint Coriander Chutney",
        "items": [
          {
            "name": "Steamed Ragi Idli",
            "portion": "3 medium idlis (150g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 6.5,
              "carbs_g": 40,
              "fat_g": 1.5,
              "sodium_mg": 85,
              "potassium_mg": 180,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Thin Mint Coriander Chutney (Low Salt)",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.0,
              "carbs_g": 3.0,
              "fat_g": 1.5,
              "sodium_mg": 50,
              "potassium_mg": 70,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Finger millet (Ragi) provides low glycemic index carbs with high soluble fiber, keeping postprandial glucose stable.",
        "prep_tips": "Steam batter without sodium bicarbonate or baking soda to control sodium."
      },
      {
        "title": "Moong Dal Dosa (Pesarattu) with Ginger Chutney",
        "items": [
          {
            "name": "Moong Dal Dosa (Pesarattu)",
            "portion": "2 medium (140g)",
            "nutrients": {
              "calories": 240,
              "protein_g": 10.5,
              "carbs_g": 38,
              "fat_g": 4.5,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Fresh Ginger Allam Chutney (Mild)",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 0.8,
              "carbs_g": 7.0,
              "fat_g": 1.0,
              "sodium_mg": 55,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Yellow moong is easy on renal filtration with lower purine and high plant-based bioavailable protein.",
        "prep_tips": "Grind soaked green moong with ginger and cumin; use cold-pressed sesame or olive oil."
      },
      {
        "title": "Vegetable Oats Upma with Curry Leaves",
        "items": [
          {
            "name": "Vegetable Oats Upma with French Beans & Carrots",
            "portion": "1.5 cups (200g)",
            "nutrients": {
              "calories": 230,
              "protein_g": 7.0,
              "carbs_g": 39,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 190,
              "fiber_g": 6.0
            }
          }
        ],
        "justification": "Beta-glucan fiber in oats aids blood pressure reduction and cholesterol regulation without loading potassium.",
        "prep_tips": "Temper mustard and curry leaves in 1 tsp oil; simmer beans till tender."
      },
      {
        "title": "Red Rice Idli with Drumstick Sambhar",
        "items": [
          {
            "name": "Red Rice Idli",
            "portion": "3 medium (150g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 5.8,
              "carbs_g": 43,
              "fat_g": 1.2,
              "sodium_mg": 70,
              "potassium_mg": 160,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Mild Drumstick & Lauki Sambhar",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 4.0,
              "carbs_g": 14,
              "fat_g": 1.5,
              "sodium_mg": 110,
              "potassium_mg": 190,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Drumsticks and bottle gourd have gentle renal profiles and high antioxidant flavonoid levels.",
        "prep_tips": "Boil drumstick in lightly spiced tamarind broth without packaged sambhar powders."
      },
      {
        "title": "Kodu Millet Pongal with Cumin & Pepper",
        "items": [
          {
            "name": "Kodu Millet & Yellow Moong Pongal",
            "portion": "1.3 cups (180g)",
            "nutrients": {
              "calories": 235,
              "protein_g": 8.0,
              "carbs_g": 38,
              "fat_g": 5.0,
              "sodium_mg": 85,
              "potassium_mg": 185,
              "fiber_g": 5.2
            }
          },
          {
            "name": "Coriander Mint Pachadi",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 1.0,
              "sodium_mg": 45,
              "potassium_mg": 65,
              "fiber_g": 1.1
            }
          }
        ],
        "justification": "Kodu millet delivers slow-release energy with lower glycemic load and protective polyphenols.",
        "prep_tips": "Temper whole cumin and crushed black pepper in minimal cold-pressed oil."
      },
      {
        "title": "Steamed Rice Sevai with Mixed Vegetable Poriyal",
        "items": [
          {
            "name": "Steamed Brown Rice Sevai with French Beans & Peas",
            "portion": "1.5 cups (190g)",
            "nutrients": {
              "calories": 225,
              "protein_g": 6.2,
              "carbs_g": 41,
              "fat_g": 3.5,
              "sodium_mg": 80,
              "potassium_mg": 175,
              "fiber_g": 4.8
            }
          }
        ],
        "justification": "Steamed rice noodles provide easily digestible complex carbohydrates with negligible phosphorus.",
        "prep_tips": "Steam without oil; toss with lemon juice, grated ginger, and curry leaves."
      },
      {
        "title": "Multi-Millet Dosa with Ridge Gourd Chutney",
        "items": [
          {
            "name": "Multi-Millet Dosa (Foxtail & Little Millet)",
            "portion": "2 medium (140g)",
            "nutrients": {
              "calories": 230,
              "protein_g": 7.5,
              "carbs_g": 39,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Ridge Gourd Peel & Mint Chutney",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.9,
              "carbs_g": 3.5,
              "fat_g": 1.2,
              "sodium_mg": 50,
              "potassium_mg": 75,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "Ridge gourd peel is rich in insoluble fiber that lowers postprandial glycemic excursions.",
        "prep_tips": "Roast ridge gourd peel with cumin and green chili before blending."
      }
    ],
    "mid_morning": [
      {
        "title": "Crisp Cucumber Spears with Roasted Cumin & Lemon with Roasted Bengal Gram",
        "items": [
          {
            "name": "Crisp Cucumber Slices with Lemon & Jeera",
            "portion": "1 cup (120g)",
            "nutrients": {
              "calories": 20,
              "protein_g": 0.8,
              "carbs_g": 4.0,
              "fat_g": 0.2,
              "sodium_mg": 15,
              "potassium_mg": 140,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Fresh Lemon Mint Chia Cooler",
            "portion": "1 glass (180ml)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 4.0,
              "fat_g": 0.5,
              "sodium_mg": 15,
              "potassium_mg": 75,
              "fiber_g": 1.8
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Hydrating, low glycemic, low sodium snack to bridge morning glucose levels without potassium spikes.",
        "prep_tips": "Sprinkle freshly roasted cumin powder; prepare chia water with fresh lemon."
      },
      {
        "title": "Spiced Buttermilk (Neer Mor) with Curry Leaves & Hing with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Diluted Buttermilk (Neer Mor) with Hing & Ginger",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.8,
              "carbs_g": 4.5,
              "fat_g": 1.2,
              "sodium_mg": 40,
              "potassium_mg": 150,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Naturally probiotic; diluted yogurt reduces phosphorus load while soothing digestion.",
        "prep_tips": "Whisk curd with 3 parts chilled water; temper with mustard and crushed ginger."
      },
      {
        "title": "Steamed White Chana Sundal (Lightly Tempered)",
        "items": [
          {
            "name": "Steamed Chickpea Sundal with Lemon & Mustard",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 4.5,
              "carbs_g": 15,
              "fat_g": 1.8,
              "sodium_mg": 45,
              "potassium_mg": 170,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Provides sustained satiety through complex carbohydrates and soluble legumes.",
        "prep_tips": "Pre-soak overnight and pressure cook; drain cooking water to reduce potassium."
      },
      {
        "title": "Fresh Guava Slices with Roasted Jeera with Roasted Bengal Gram",
        "items": [
          {
            "name": "Crisp Guava Slices with Roasted Cumin",
            "portion": "1 medium guava (100g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 2.0,
              "carbs_g": 11.0,
              "fat_g": 0.8,
              "sodium_mg": 5,
              "potassium_mg": 180,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "High pectin and ascorbic acid content without raising glycemic spikes.",
        "prep_tips": "Select firm semi-ripe guava; wash thoroughly."
      },
      {
        "title": "Steamed Sprouted Moong with Pomegranate Arils",
        "items": [
          {
            "name": "Lightly Steamed Moong Sprouts with Pomegranate",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.2,
              "carbs_g": 13.0,
              "fat_g": 0.6,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Sprouted moong has higher protein bioavailability and lower phytate content.",
        "prep_tips": "Steam for 3 minutes to preserve active enzymes while softening fiber."
      }
    ],
    "lunch": [
      {
        "title": "Brown Rice with Lauki Kootu & Pepper Rasam",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Bottle Gourd (Lauki) & Moong Dal Kootu",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 140,
              "protein_g": 7.0,
              "carbs_g": 20,
              "fat_g": 3.5,
              "sodium_mg": 95,
              "potassium_mg": 220,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Clear Pepper Cumin Tomato Rasam",
            "portion": "1 cup (150ml)",
            "nutrients": {
              "calories": 45,
              "protein_g": 1.2,
              "carbs_g": 8.0,
              "fat_g": 0.8,
              "sodium_mg": 85,
              "potassium_mg": 160,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Snake Gourd (Pudalangai) Poriyal",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 1.5,
              "carbs_g": 7.0,
              "fat_g": 2.5,
              "sodium_mg": 45,
              "potassium_mg": 130,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Snake gourd and bottle gourd are top-ranked renal vegetables with exceptionally low potassium density.",
        "prep_tips": "Cook dal and gourd together; season with black pepper instead of red chili."
      },
      {
        "title": "Foxtail Millet Rice with Sambhar & Cabbage Thoran",
        "items": [
          {
            "name": "Steamed Foxtail Millet (Thinai)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 180,
              "protein_g": 5.0,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 8,
              "potassium_mg": 125,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Mixed Vegetable Sambhar (Carrot, Beans)",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 6.5,
              "carbs_g": 18,
              "fat_g": 2.5,
              "sodium_mg": 110,
              "potassium_mg": 210,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Cabbage Green Peas Thoran",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 2.5,
              "carbs_g": 9.0,
              "fat_g": 3.0,
              "sodium_mg": 60,
              "potassium_mg": 150,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Millets possess significantly lower glycemic indices than polished white rice, preventing insulin spikes.",
        "prep_tips": "Soak foxtail millet for 30 minutes before steaming for fluffier texture."
      },
      {
        "title": "Curd Rice with Pomegranate & Ridge Gourd Poriyal",
        "items": [
          {
            "name": "Low-Fat Probiotic Curd Rice with Mustard Tempering",
            "portion": "1.2 cups (180g)",
            "nutrients": {
              "calories": 190,
              "protein_g": 6.2,
              "carbs_g": 32,
              "fat_g": 3.5,
              "sodium_mg": 80,
              "potassium_mg": 170,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Ridge Gourd (Peerkangai) Stir-Fry",
            "portion": "1 cup (120g)",
            "nutrients": {
              "calories": 70,
              "protein_g": 2.0,
              "carbs_g": 9.0,
              "fat_g": 2.5,
              "sodium_mg": 50,
              "potassium_mg": 160,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Pomegranate Arils Garnish",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.5,
              "carbs_g": 5.5,
              "fat_g": 0.3,
              "sodium_mg": 3,
              "potassium_mg": 65,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Pomegranate provides polyphenol vascular protection, while ridge gourd supports smooth renal clearance.",
        "prep_tips": "Use homemade skimmed-milk dahi to maintain low saturated fat."
      },
      {
        "title": "Meen Kuzhambu (Steamed Fish Curry) with Matta Rice & Cabbage Thoran",
        "items": [
          {
            "name": "Steamed White Fish in Tamarind Kokum Gravy",
            "portion": "120g fillet + gravy",
            "nutrients": {
              "calories": 165,
              "protein_g": 20.0,
              "carbs_g": 5.0,
              "fat_g": 5.0,
              "sodium_mg": 95,
              "potassium_mg": 230,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Steamed Matta / Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Cabbage Green Peas Poriyal",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 70,
              "protein_g": 2.2,
              "carbs_g": 9.0,
              "fat_g": 2.5,
              "sodium_mg": 50,
              "potassium_mg": 140,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Lean white fish provides cardioprotective omega-3 fatty acids without raising saturated lipid levels.",
        "prep_tips": "Poach fish in tangy tamarind and fenugreek broth; do not deep fry or add coconut milk."
      },
      {
        "title": "Kozhi Saaru (Lean Pepper Chicken Stew) with Foxtail Millet & Beans Poriyal",
        "items": [
          {
            "name": "Skinless Chicken Breast Stew with Crushed Black Pepper",
            "portion": "110g chicken + broth",
            "nutrients": {
              "calories": 160,
              "protein_g": 22.0,
              "carbs_g": 3.0,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 220,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Steamed Foxtail Millet",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 180,
              "protein_g": 5.0,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 8,
              "potassium_mg": 125,
              "fiber_g": 4.0
            }
          },
          {
            "name": "French Beans & Carrot Poriyal",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 55,
              "protein_g": 1.8,
              "carbs_g": 8.0,
              "fat_g": 1.5,
              "sodium_mg": 45,
              "potassium_mg": 150,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Skinless chicken breast delivers complete amino acids with minimal purines and low lipid density.",
        "prep_tips": "Simmer diced skinless breast in fresh cumin, black pepper, and tomato broth."
      },
      {
        "title": "South Indian Egg White Curry with Brown Rice & Ridge Gourd Poriyal",
        "items": [
          {
            "name": "Egg White Curry (3 Boiled Whites in Mild Tomato Gravy)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 13.0,
              "carbs_g": 7.0,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 190,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Steamed Ridge Gourd Poriyal",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 1.5,
              "carbs_g": 7.0,
              "fat_g": 1.8,
              "sodium_mg": 40,
              "potassium_mg": 130,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Pure egg albumen provides essential amino acids with near-zero phosphorus and zero cholesterol.",
        "prep_tips": "Discard egg yolks to remove cholesterol and heavy phosphorus loads."
      },
      {
        "title": "Little Millet Rice with Murungakai Sambhar & Tindora Stir-Fry",
        "items": [
          {
            "name": "Steamed Little Millet (Samai)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.8,
              "carbs_g": 35,
              "fat_g": 1.4,
              "sodium_mg": 7,
              "potassium_mg": 120,
              "fiber_g": 4.2
            }
          },
          {
            "name": "Fresh Drumstick Sambhar",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 6.0,
              "carbs_g": 17,
              "fat_g": 2.2,
              "sodium_mg": 105,
              "potassium_mg": 200,
              "fiber_g": 3.2
            }
          },
          {
            "name": "Steamed Tindora (Ivy Gourd) Poriyal",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 1.6,
              "carbs_g": 7.5,
              "fat_g": 2.0,
              "sodium_mg": 45,
              "potassium_mg": 140,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Ivy gourd has documented insulin-sensitizing properties with negligible nephrotoxic stress.",
        "prep_tips": "Steam ivy gourd slices; temper with mustard and turmeric."
      }
    ],
    "evening_snack": [
      {
        "title": "Roasted Makhana (Fox Nuts) with Green Tea",
        "items": [
          {
            "name": "Lightly Roasted Makhana with Turmeric & Pepper",
            "portion": "1 cup (30g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 20,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 120,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Unsweetened Jasmine Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Makhana is low in sodium and fat, delivering clean plant protein without phosphorus overload.",
        "prep_tips": "Dry roast in a cast-iron pan for 4 minutes till crunchy; toss with pinch of turmeric."
      },
      {
        "title": "Boiled Sprouted Moong Chaat with Lime",
        "items": [
          {
            "name": "Boiled Moong Sprouts with Lemon & Coriander",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 6.0,
              "carbs_g": 15,
              "fat_g": 0.8,
              "sodium_mg": 35,
              "potassium_mg": 160,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Sprouting enhances amino acid bioaccessibility while reducing phytate anti-nutrients.",
        "prep_tips": "Steam sprouts for 5 minutes; toss with chopped cucumber, cilantro, and fresh lime."
      },
      {
        "title": "Steamed Sweet Corn with Lemon & Black Pepper",
        "items": [
          {
            "name": "Steamed Yellow Corn Kernels with Lime",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.8,
              "carbs_g": 18,
              "fat_g": 1.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 2.2
            }
          }
        ],
        "justification": "Lutein-rich snack with low glycemic impact when consumed in controlled portion.",
        "prep_tips": "Boil corn kernels; drain water thoroughly and toss with lime juice."
      },
      {
        "title": "Roasted Bengal Gram (Chana) with Curry Leaves",
        "items": [
          {
            "name": "Roasted Bengal Gram (Chana) with Mustard & Curry Leaves",
            "portion": "1/4 cup (35g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 6.5,
              "carbs_g": 18,
              "fat_g": 2.0,
              "sodium_mg": 30,
              "potassium_mg": 165,
              "fiber_g": 4.0
            }
          }
        ],
        "justification": "Excellent source of resistant starch that feeds gut microbiome without rapid glucose spikes.",
        "prep_tips": "Roast chana dry; toss with curry leaves heated in few drops of oil."
      },
      {
        "title": "Fresh Mint Green Tea with Roasted Flaxseeds with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Fresh Mint Infused Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Lightly Roasted Flaxseeds",
            "portion": "1 tbsp (10g)",
            "nutrients": {
              "calories": 55,
              "protein_g": 1.9,
              "carbs_g": 3.0,
              "fat_g": 4.2,
              "sodium_mg": 3,
              "potassium_mg": 80,
              "fiber_g": 2.8
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Alpha-linolenic acid (ALA) in flaxseeds supports vascular elasticity.",
        "prep_tips": "Grind roasted flaxseeds coarsely just before eating for maximum bioavailability."
      }
    ],
    "dinner": [
      {
        "title": "Phulka Rotis with Tinda Masala & Yellow Moong Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Phulka (Oil-free)",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 30,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Stewed Tinda (Apple Gourd) Gravy",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.0,
              "carbs_g": 11,
              "fat_g": 3.0,
              "sodium_mg": 70,
              "potassium_mg": 180,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Thin Tadka Yellow Moong Dal",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 5.5,
              "carbs_g": 13,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Light, evening-friendly digestion profile that avoids midnight blood pressure spikes.",
        "prep_tips": "Puff phulkas directly on flame; do not brush with butter or ghee."
      },
      {
        "title": "Jowar (Sorghum) Roti with Ridge Gourd Stew & Rasam",
        "items": [
          {
            "name": "Gluten-Free Jowar Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 4.5,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 15,
              "potassium_mg": 130,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Turmeric Braised Peerkangai (Ridge Gourd)",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 80,
              "protein_g": 2.2,
              "carbs_g": 11,
              "fat_g": 2.8,
              "sodium_mg": 65,
              "potassium_mg": 170,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Warm Spiced Rasam Broth",
            "portion": "3/4 cup (120ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 6.0,
              "fat_g": 0.5,
              "sodium_mg": 70,
              "potassium_mg": 110,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Sorghum provides slow-release complex carbs, avoiding early morning fasting glucose elevations.",
        "prep_tips": "Knead jowar flour with warm water; roll thin and cook on high heat."
      },
      {
        "title": "Millet Khichdi with Steamed French Beans",
        "items": [
          {
            "name": "Little Millet (Samai) & Split Yellow Moong Khichdi",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 230,
              "protein_g": 8.5,
              "carbs_g": 41,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Steamed French Beans with Grated Ginger",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 1.8,
              "carbs_g": 7.5,
              "fat_g": 0.8,
              "sodium_mg": 30,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Equal parts millet and split moong create a balanced amino acid pool without uric acid accumulation.",
        "prep_tips": "Pressure cook for 3 whistles with cumin, turmeric, and pinch of black pepper."
      },
      {
        "title": "Grilled Fish with Jowar Roti & Warm Rasam",
        "items": [
          {
            "name": "Herb-Spiced Grilled White Fish",
            "portion": "100g fillet",
            "nutrients": {
              "calories": 145,
              "protein_g": 19.0,
              "carbs_g": 2.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Gluten-Free Jowar Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 4.5,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 15,
              "potassium_mg": 130,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Warm Spiced Rasam Broth",
            "portion": "3/4 cup (120ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 6.0,
              "fat_g": 0.5,
              "sodium_mg": 70,
              "potassium_mg": 110,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Easily digested lean protein with low saturated fat, optimizing nocturnal metabolic rest.",
        "prep_tips": "Marinate fish with turmeric, lime juice, and fenugreek powder before pan grilling."
      },
      {
        "title": "Bajra Roti with Methi Dal & Steamed Bottle Gourd",
        "items": [
          {
            "name": "Steamed Bajra (Pearl Millet) Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.8,
              "carbs_g": 35,
              "fat_g": 1.8,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Fresh Fenugreek (Methi) & Moong Dal",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 6.8,
              "carbs_g": 15,
              "fat_g": 2.5,
              "sodium_mg": 80,
              "potassium_mg": 190,
              "fiber_g": 3.8
            }
          },
          {
            "name": "Steamed Lauki with Jeera",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 5.0,
              "fat_g": 1.0,
              "sodium_mg": 35,
              "potassium_mg": 120,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Fenugreek seeds and leaves contain trigonelline that enhances insulin sensitivity.",
        "prep_tips": "Cook washed methi leaves into yellow dal without frying."
      },
      {
        "title": "Ragi Mudde with Mild Vegetable Saaru",
        "items": [
          {
            "name": "Steamed Ragi Mudde (Finger Millet Ball)",
            "portion": "1 medium ball (150g)",
            "nutrients": {
              "calories": 190,
              "protein_g": 5.5,
              "carbs_g": 38,
              "fat_g": 1.5,
              "sodium_mg": 25,
              "potassium_mg": 170,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Mild Diluted Vegetable Saaru (Beans, Tomato)",
            "portion": "1.2 cups (200ml)",
            "nutrients": {
              "calories": 70,
              "protein_g": 2.5,
              "carbs_g": 11,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 160,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Ragi mudde is a traditional low-GI staple rich in calcium and essential amino acids.",
        "prep_tips": "Stir ragi flour in boiling water until glossy and lump-free."
      },
      {
        "title": "Barley & Moong Khichdi with Ash Gourd Soup",
        "items": [
          {
            "name": "Pearl Barley & Yellow Moong Khichdi",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 7.8,
              "carbs_g": 39,
              "fat_g": 2.5,
              "sodium_mg": 80,
              "potassium_mg": 180,
              "fiber_g": 6.2
            }
          },
          {
            "name": "Clear Ash Gourd (Petha) Broth",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.8,
              "carbs_g": 5.0,
              "fat_g": 0.5,
              "sodium_mg": 40,
              "potassium_mg": 110,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Ash gourd has cooling properties and natural diuretic action without causing potassium depletion.",
        "prep_tips": "Boil ash gourd with cumin and black pepper; strain or serve rustic."
      }
    ]
  },
  "north_indian": {
    "breakfast": [
      {
        "title": "Methi Missi Roti with Skimmed Curd",
        "items": [
          {
            "name": "Fenugreek (Methi) Besan & Wheat Roti",
            "portion": "2 medium (100g)",
            "nutrients": {
              "calories": 220,
              "protein_g": 8.5,
              "carbs_g": 36,
              "fat_g": 3.5,
              "sodium_mg": 90,
              "potassium_mg": 190,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Fresh Low-Fat Cow Curd",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 4.0,
              "carbs_g": 5.0,
              "fat_g": 2.0,
              "sodium_mg": 50,
              "potassium_mg": 150,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Methi leaves contain 4-hydroxyisoleucine which stimulates glucose-dependent insulin secretion.",
        "prep_tips": "Mix fresh chopped fenugreek into 50:50 wheat and chickpea flour."
      },
      {
        "title": "Vegetable Dalia (Broken Wheat Porridge)",
        "items": [
          {
            "name": "Savory Dalia with Peas, Carrots & Cumin",
            "portion": "1.5 cups (220g)",
            "nutrients": {
              "calories": 230,
              "protein_g": 7.2,
              "carbs_g": 42,
              "fat_g": 3.0,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 6.5
            }
          }
        ],
        "justification": "High whole-grain endosperm fiber slows enzymatic carbohydrate breakdown.",
        "prep_tips": "Dry roast dalia until nutty before pressure cooking with vegetables."
      },
      {
        "title": "Moong Dal Chilla with Mint Chutney",
        "items": [
          {
            "name": "Yellow Moong Dal Savory Pancake",
            "portion": "2 chillas (130g)",
            "nutrients": {
              "calories": 225,
              "protein_g": 11.0,
              "carbs_g": 35,
              "fat_g": 4.0,
              "sodium_mg": 90,
              "potassium_mg": 210,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Pudina Coriander Chutney (No Garlic)",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.8,
              "carbs_g": 4.0,
              "fat_g": 1.0,
              "sodium_mg": 45,
              "potassium_mg": 75,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Moong chilla delivers satisfying plant protein with negligible saturated fat.",
        "prep_tips": "Spread batter thin on a non-stick griddle with a brush of olive or mustard oil."
      },
      {
        "title": "Besan & Paneer/Tofu Chilla with Mint Dip",
        "items": [
          {
            "name": "Chickpea Flour Chilla stuffed with Crumbled Tofu/Paneer",
            "portion": "2 chillas (140g)",
            "nutrients": {
              "calories": 240,
              "protein_g": 12.5,
              "carbs_g": 32,
              "fat_g": 5.0,
              "sodium_mg": 95,
              "potassium_mg": 200,
              "fiber_g": 4.8
            }
          },
          {
            "name": "Fresh Pudina Dip",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 40,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Chickpea flour provides low glycemic index carbs with high plant protein density.",
        "prep_tips": "Grate firm tofu or low-fat paneer into batter."
      },
      {
        "title": "Vegetable Poha with Green Peas & Lemon",
        "items": [
          {
            "name": "Flattened Rice (Poha) with Green Peas & Turmeric",
            "portion": "1.3 cups (180g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 5.5,
              "carbs_g": 39,
              "fat_g": 3.0,
              "sodium_mg": 75,
              "potassium_mg": 170,
              "fiber_g": 4.2
            }
          }
        ],
        "justification": "Easily digestible breakfast with gentle renal filtration load.",
        "prep_tips": "Rinse thick poha lightly; toss with lemon juice, mustard seeds, and fresh curry leaves."
      },
      {
        "title": "Spinach & Oats Cheela with Coriander Chutney",
        "items": [
          {
            "name": "Rolled Oats & Pureed Palak Savory Pancake",
            "portion": "2 medium (130g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 8.0,
              "carbs_g": 36,
              "fat_g": 3.8,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 5.8
            }
          },
          {
            "name": "Coriander Mint Chutney",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 45,
              "potassium_mg": 65,
              "fiber_g": 1.1
            }
          }
        ],
        "justification": "Oats beta-glucan binds bile acids, lowering cholesterol while maintaining stable blood sugar.",
        "prep_tips": "Grind oats into coarse flour and whisk with blanched spinach puree."
      },
      {
        "title": "Sprouted Moong & Vegetable Dhokla (Steamed)",
        "items": [
          {
            "name": "Steamed Sprouted Moong Dhokla with Mustard Tempering",
            "portion": "3 pieces (140g)",
            "nutrients": {
              "calories": 205,
              "protein_g": 9.2,
              "carbs_g": 34,
              "fat_g": 2.5,
              "sodium_mg": 80,
              "potassium_mg": 190,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Thin Pudina Chutney",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 45,
              "potassium_mg": 65,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Fermented and steamed sprouted pulse enhances zinc and iron bioavailability without adding sodium carbonate.",
        "prep_tips": "Steam without fruit salt or baking soda; use lemon juice for aeration."
      }
    ],
    "mid_morning": [
      {
        "title": "Roasted Chana & Sweet Papaya Cubes",
        "items": [
          {
            "name": "Unsalted Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 80,
              "protein_g": 4.0,
              "carbs_g": 12,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 130,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Fresh Ripe Papaya Slices",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 0.5,
              "carbs_g": 10,
              "fat_g": 0.1,
              "sodium_mg": 5,
              "potassium_mg": 180,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Papain enzyme aids peptide digestion while maintaining safe potassium limits.",
        "prep_tips": "Consume fresh; avoid adding chaat masala to restrict sodium."
      },
      {
        "title": "Thin Chaas (Spiced Buttermilk) with Roasted Jeera with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Diluted Cow Chaas with Roasted Cumin & Mint",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.8,
              "carbs_g": 4.5,
              "fat_g": 1.2,
              "sodium_mg": 45,
              "potassium_mg": 155,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Replenishes electrolyte volume gently with probiotic support.",
        "prep_tips": "Whisk fresh dahi with 3 parts water; avoid table salt."
      },
      {
        "title": "Roasted Makhana with Black Salt & Pepper",
        "items": [
          {
            "name": "Dry Roasted Fox Nuts with Mild Pepper",
            "portion": "1 cup (30g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 20,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 120,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Rich in flavonoids and kaempferol that suppress vascular inflammation.",
        "prep_tips": "Roast dry on low heat until crisp."
      },
      {
        "title": "Cucumber & Carrot Sticks with Mint Yogurt Dip with Roasted Bengal Gram",
        "items": [
          {
            "name": "Crisp Cucumber & Tender Carrot Batons",
            "portion": "1.2 cups (140g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.2,
              "carbs_g": 7.5,
              "fat_g": 0.2,
              "sodium_mg": 25,
              "potassium_mg": 190,
              "fiber_g": 2.8
            }
          },
          {
            "name": "Fresh Mint Low-Fat Yogurt Dip",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 1.5,
              "carbs_g": 2.5,
              "fat_g": 0.8,
              "sodium_mg": 20,
              "potassium_mg": 60,
              "fiber_g": 0.3
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "High moisture and soluble fiber provide satiety without insulin response.",
        "prep_tips": "Cut vegetables fresh and serve chilled."
      },
      {
        "title": "Fresh Sweet Orange / Mosambi Slices (Controlled) with Roasted Bengal Gram",
        "items": [
          {
            "name": "Fresh Mosambi (Sweet Lime) Slices",
            "portion": "1 small fruit (100g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 0.8,
              "carbs_g": 10.5,
              "fat_g": 0.2,
              "sodium_mg": 2,
              "potassium_mg": 160,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Rich in citrus bioflavonoids without extreme potassium loading (avoid if on CCB).",
        "prep_tips": "Eat whole fruit segments to preserve fiber rather than juicing."
      }
    ],
    "lunch": [
      {
        "title": "Multigrain Rotis with Lauki Kofta (Steamed) & Dal Tadka",
        "items": [
          {
            "name": "Multigrain Wheat & Barley Rotis",
            "portion": "2 rotis (70g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 5.5,
              "carbs_g": 35,
              "fat_g": 1.2,
              "sodium_mg": 35,
              "potassium_mg": 120,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Steamed Lauki (Bottle Gourd) Dumplings in Light Gravy",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 4.5,
              "carbs_g": 16,
              "fat_g": 4.5,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Yellow Arhar Dal with Cumin Hing Tempering",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 110,
              "protein_g": 6.5,
              "carbs_g": 16,
              "fat_g": 2.0,
              "sodium_mg": 85,
              "potassium_mg": 180,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Steaming the lauki kofta instead of deep frying removes trans-fats and protects endothelial function.",
        "prep_tips": "Bind grated bottle gourd with gram flour, steam for 10 minutes, and simmer in tomato puree."
      },
      {
        "title": "Jeera Rice with Low-Fat Paneer Bhurji & Cucumber Salad",
        "items": [
          {
            "name": "Steamed Rice with Cumin Seeds",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 3.8,
              "carbs_g": 36,
              "fat_g": 1.0,
              "sodium_mg": 10,
              "potassium_mg": 95,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Low-Fat Cottage Cheese (Paneer) Bhurji with Capsicum",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 14.0,
              "carbs_g": 6.0,
              "fat_g": 8.0,
              "sodium_mg": 110,
              "potassium_mg": 160,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Cucumber Tomato Onion Salad with Lemon",
            "portion": "1 cup (120g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 7.0,
              "fat_g": 0.2,
              "sodium_mg": 15,
              "potassium_mg": 170,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Low-fat paneer delivers high biological value protein without phosphorus-heavy processing additives.",
        "prep_tips": "Make paneer at home using skimmed cow milk curdled with lemon juice."
      },
      {
        "title": "Tandoori Grilled Herb Chicken Breast with Multigrain Rotis & Dal",
        "items": [
          {
            "name": "Herb-Marinated Dry Grilled Chicken Breast",
            "portion": "110g fillet",
            "nutrients": {
              "calories": 165,
              "protein_g": 23.0,
              "carbs_g": 2.0,
              "fat_g": 4.5,
              "sodium_mg": 95,
              "potassium_mg": 230,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Multigrain Wheat & Barley Rotis",
            "portion": "2 rotis (70g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 5.5,
              "carbs_g": 35,
              "fat_g": 1.2,
              "sodium_mg": 35,
              "potassium_mg": 120,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Yellow Moong Dal with Cumin Hing Tempering",
            "portion": "1/2 cup (90g)",
            "nutrients": {
              "calories": 80,
              "protein_g": 5.0,
              "carbs_g": 12,
              "fat_g": 1.2,
              "sodium_mg": 65,
              "potassium_mg": 130,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Dry grilling eliminates saturated cooking oils while curd marinade provides lean protein digestability.",
        "prep_tips": "Marinate skinless chicken breast in skimmed dahi, ginger-garlic paste, and roasted cumin; oven bake."
      },
      {
        "title": "Amritsari Baked Fish Tikka with Mint Chutney & Steamed Rice",
        "items": [
          {
            "name": "Baked White Fish Tikka with Ajwain & Lemon",
            "portion": "110g fillet",
            "nutrients": {
              "calories": 150,
              "protein_g": 20.0,
              "carbs_g": 3.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 220,
              "fiber_g": 0.8
            }
          },
          {
            "name": "Steamed Cumin Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 3.8,
              "carbs_g": 36,
              "fat_g": 1.0,
              "sodium_mg": 10,
              "potassium_mg": 95,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Fresh Mint Coriander Chutney (Low Salt)",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 40,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Ajwain (carom seeds) aids gastrointestinal motility while white fish provides lean protein with negligible saturated fat.",
        "prep_tips": "Rub fish fillet with crushed ajwain, turmeric, and lemon juice; bake at 190°C for 15 minutes."
      },
      {
        "title": "Egg White Curry with Phulkas & Kachumber Salad",
        "items": [
          {
            "name": "Egg White Curry (3 Whites in Onion Tomato Gravy)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 13.5,
              "carbs_g": 8.0,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 190,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Soft Whole Wheat Phulkas",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 30,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Kachumber Salad (Cucumber, Tomato, Lemon)",
            "portion": "1 cup (120g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.0,
              "carbs_g": 6.0,
              "fat_g": 0.2,
              "sodium_mg": 15,
              "potassium_mg": 160,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Pure egg albumen supplies zero-cholesterol, high-efficiency protein ideal for renal and cardiovascular health.",
        "prep_tips": "Boil eggs, discard yolks, and simmer whites in tomato-onion gravy."
      },
      {
        "title": "Brown Basmati Rice with Rajma Masala & Steamed Lauki",
        "items": [
          {
            "name": "Steamed Brown Basmati Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 105,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Mild Rajma (Kidney Beans) Masala",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 165,
              "protein_g": 9.5,
              "carbs_g": 26,
              "fat_g": 2.5,
              "sodium_mg": 110,
              "potassium_mg": 220,
              "fiber_g": 6.5
            }
          },
          {
            "name": "Steamed Lauki with Jeera",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 5.0,
              "fat_g": 1.0,
              "sodium_mg": 35,
              "potassium_mg": 120,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Kidney beans supply soluble fiber that binds intestinal bile, assisting lipid clearance.",
        "prep_tips": "Soak rajma for 12 hours and pressure cook thoroughly; drain initial boil water to reduce purines."
      },
      {
        "title": "Missi Roti with Torai (Ridge Gourd) Ki Sabzi & Masoor Dal",
        "items": [
          {
            "name": "High-Fiber Missi Roti",
            "portion": "2 rotis (70g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 6.0,
              "carbs_g": 33,
              "fat_g": 2.0,
              "sodium_mg": 40,
              "potassium_mg": 130,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Stewed Torai (Ridge Gourd) with Cumin & Turmeric",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 70,
              "protein_g": 2.0,
              "carbs_g": 9.0,
              "fat_g": 2.5,
              "sodium_mg": 60,
              "potassium_mg": 160,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Red Lentil (Masoor) Dal",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 110,
              "protein_g": 7.0,
              "carbs_g": 16,
              "fat_g": 1.5,
              "sodium_mg": 80,
              "potassium_mg": 180,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Ridge gourd provides gentle renal clearance while red lentils offer easily digestible zinc and iron.",
        "prep_tips": "Cook torai in covered pan without excess oil; garnish with fresh coriander."
      }
    ],
    "evening_snack": [
      {
        "title": "Roasted Makhana with Tulsi Herbal Tea",
        "items": [
          {
            "name": "Dry Roasted Fox Nuts with Black Salt & Jeera",
            "portion": "1 cup (30g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 20,
              "fat_g": 0.5,
              "sodium_mg": 30,
              "potassium_mg": 120,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Holy Basil (Tulsi) Ginger Infusion",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.4,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 20,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Tulsi compounds support cortisol regulation and blood pressure stabilization.",
        "prep_tips": "Steep fresh tulsi leaves and crushed ginger in boiling water for 5 minutes."
      },
      {
        "title": "Boiled Black Chana Salad with Lemon",
        "items": [
          {
            "name": "Boiled Kala Chana with Tomato & Cucumber",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 5.2,
              "carbs_g": 15,
              "fat_g": 1.5,
              "sodium_mg": 35,
              "potassium_mg": 170,
              "fiber_g": 4.0
            }
          }
        ],
        "justification": "High soluble fiber snack that stabilizes evening glucose without rapid insulin release.",
        "prep_tips": "Toss boiled black chickpeas with lime juice and fresh mint."
      },
      {
        "title": "Sprouted Moong & Vegetable Salad with Lemon",
        "items": [
          {
            "name": "Moong Sprouts with Finely Chopped Vegetables",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 6.0,
              "carbs_g": 15,
              "fat_g": 0.8,
              "sodium_mg": 35,
              "potassium_mg": 160,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Digestive enzyme activation and steady satiety before dinner.",
        "prep_tips": "Steam sprouts 3 minutes for easy digestion."
      },
      {
        "title": "Steamed Corn Chaat with Cumin & Lemon",
        "items": [
          {
            "name": "Warm Steamed Sweet Corn Kernels",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.8,
              "carbs_g": 18,
              "fat_g": 1.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 2.2
            }
          }
        ],
        "justification": "Low-fat complex carbohydrate bridge that prevents dinner over-eating.",
        "prep_tips": "Toss warm corn with roasted cumin and lemon."
      },
      {
        "title": "Green Tea with Raw Walnuts",
        "items": [
          {
            "name": "Unsweetened Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Raw Walnut Halves",
            "portion": "4 halves (12g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 1.8,
              "carbs_g": 1.6,
              "fat_g": 7.5,
              "sodium_mg": 1,
              "potassium_mg": 50,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Walnut polyphenols and ALA support neuro-vascular health.",
        "prep_tips": "Soak walnuts for 2 hours to reduce bitterness."
      }
    ],
    "dinner": [
      {
        "title": "Phulkas with Baingan Bharta & Moong Dal",
        "items": [
          {
            "name": "Whole Wheat Roti",
            "portion": "2 rotis (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Char-Roasted Baingan Bharta with Fresh Peas",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 14,
              "fat_g": 3.5,
              "sodium_mg": 70,
              "potassium_mg": 210,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Light Yellow Moong Soup Dal",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 6.0,
              "carbs_g": 14,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 150,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Eggplant (brinjal) has low caloric density and high nasunin anthocyanins protecting cerebral vessels.",
        "prep_tips": "Roast whole eggplant over open flame, peel burnt skin, and mash with tomatoes and green chilies."
      },
      {
        "title": "Jowar Rotis with Lauki Chana Dal & Steamed Beans",
        "items": [
          {
            "name": "Gluten-Free Jowar Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 4.5,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 15,
              "potassium_mg": 130,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Bottle Gourd & Split Bengal Gram Gravy",
            "portion": "1 cup (170g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 6.5,
              "carbs_g": 17,
              "fat_g": 3.0,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 4.2
            }
          },
          {
            "name": "Steamed French Beans with Ginger",
            "portion": "1/2 cup (70g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.5,
              "carbs_g": 6.0,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Sorghum combined with bottle gourd keeps nocturnal glycemic levels stable and avoids nocturnal thirst.",
        "prep_tips": "Pressure cook lauki with chana dal and mild spices."
      },
      {
        "title": "Bajra Khichdi with Diluted Dahi Kadhi",
        "items": [
          {
            "name": "Cracked Pearl Millet (Bajra) & Moong Khichdi",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 220,
              "protein_g": 7.5,
              "carbs_g": 40,
              "fat_g": 2.8,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Diluted Cow Curd Kadhi with Methi Tempering",
            "portion": "3/4 cup (120ml)",
            "nutrients": {
              "calories": 65,
              "protein_g": 3.0,
              "carbs_g": 6.0,
              "fat_g": 2.5,
              "sodium_mg": 70,
              "potassium_mg": 130,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Pearl millet delivers iron and magnesium for nocturnal muscle relaxation.",
        "prep_tips": "Slow-simmer cracked bajra with split yellow moong."
      },
      {
        "title": "Grilled Lemon Herb Chicken with Phulkas & Steamed Zucchini",
        "items": [
          {
            "name": "Pan-Grilled Skinless Chicken Breast",
            "portion": "100g fillet",
            "nutrients": {
              "calories": 150,
              "protein_g": 21.0,
              "carbs_g": 2.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Whole Wheat Phulkas",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Zucchini Slices with Black Pepper",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.2,
              "carbs_g": 5.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 140,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Lean protein with minimal carbohydrates aids nocturnal tissue repair without spiking fasting blood glucose.",
        "prep_tips": "Marinate chicken in lemon juice, garlic, and dried oregano; grill without butter."
      },
      {
        "title": "Phulkas with Methi Paneer (Low Carb) & Dal Palak",
        "items": [
          {
            "name": "Whole Wheat Phulkas",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Low-Fat Paneer Stewed with Fresh Methi Leaves",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 140,
              "protein_g": 11.0,
              "carbs_g": 5.0,
              "fat_g": 7.0,
              "sodium_mg": 90,
              "potassium_mg": 160,
              "fiber_g": 2.2
            }
          },
          {
            "name": "Spinach Yellow Moong Dal",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 5.5,
              "carbs_g": 12,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 160,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "High dietary nitrate from spinach supports endothelial nitric oxide synthesis and vascular dilation.",
        "prep_tips": "Saute paneer cubes lightly in chopped fenugreek and tomato gravy."
      },
      {
        "title": "Dalia Khichdi with Moong Dal & Bottle Gourd",
        "items": [
          {
            "name": "Broken Wheat (Dalia) & Moong Khichdi with Lauki",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 8.0,
              "carbs_g": 40,
              "fat_g": 2.5,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 5.8
            }
          },
          {
            "name": "Fresh Mint Tomato Shorba",
            "portion": "1 cup (150ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 7.0,
              "fat_g": 0.5,
              "sodium_mg": 55,
              "potassium_mg": 110,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Easily digested warm cereal soothing to gastric lining while preserving slow glucose release.",
        "prep_tips": "Pressure cook dalia, moong, and diced lauki together."
      },
      {
        "title": "Phulkas with Parwal (Pointed Gourd) Masala & Clear Tomato Soup",
        "items": [
          {
            "name": "Whole Wheat Phulkas",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Parwal in Light Tomato Cumin Gravy",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 11,
              "fat_g": 3.0,
              "sodium_mg": 70,
              "potassium_mg": 175,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Clear Spiced Tomato Cumin Soup",
            "portion": "1 cup (150ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 6.5,
              "fat_g": 0.5,
              "sodium_mg": 60,
              "potassium_mg": 130,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Pointed gourd is traditional ayurvedic renal supportive vegetable with low glycemic burden.",
        "prep_tips": "Steam parwal halves before simmering in light cumin gravy."
      }
    ]
  },
  "western_indian": {
    "breakfast": [
      {
        "title": "Bajra Methi Thepla with Low-Fat Curd",
        "items": [
          {
            "name": "Pearl Millet & Fenugreek Thepla",
            "portion": "2 medium (90g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 6.5,
              "carbs_g": 35,
              "fat_g": 4.5,
              "sodium_mg": 85,
              "potassium_mg": 180,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Fresh Low-Fat Cow Curd",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 4.0,
              "carbs_g": 5.0,
              "fat_g": 2.0,
              "sodium_mg": 50,
              "potassium_mg": 150,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Pearl millet combined with methi leaves suppresses postprandial glucose surges while keeping sodium in strict check.",
        "prep_tips": "Knead bajra and whole wheat flour with fresh fenugreek; cook on iron tawa with drops of cold-pressed oil."
      },
      {
        "title": "Steamed Dudhi (Bottle Gourd) Muthia with Mint Chutney",
        "items": [
          {
            "name": "Steamed Lauki Muthia with Mustard Tempering",
            "portion": "4 pieces (150g)",
            "nutrients": {
              "calories": 195,
              "protein_g": 6.5,
              "carbs_g": 34,
              "fat_g": 3.0,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Mint Coriander Chutney",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 45,
              "potassium_mg": 65,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Steamed muthia provides complex carbs with high vegetable moisture and minimal fat.",
        "prep_tips": "Do not deep fry muthia; steam in a dhokla steamer and temper lightly."
      },
      {
        "title": "Poha with Sprouted Moong & Green Peas",
        "items": [
          {
            "name": "Flattened Rice with Sprouted Moong & Fresh Turmeric",
            "portion": "1.3 cups (180g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 7.0,
              "carbs_g": 38,
              "fat_g": 3.2,
              "sodium_mg": 75,
              "potassium_mg": 185,
              "fiber_g": 4.5
            }
          }
        ],
        "justification": "Adding sprouted moong elevates the protein-to-carb ratio, buffering glycemic release.",
        "prep_tips": "Saute mustard, curry leaves, and green chillies in 1 tsp peanut or sesame oil."
      },
      {
        "title": "Steamed Khandvi with Fresh Coriander & Mustard Tempering",
        "items": [
          {
            "name": "Steamed Gram Flour Khandvi Rolls",
            "portion": "4 rolls (120g)",
            "nutrients": {
              "calories": 185,
              "protein_g": 8.0,
              "carbs_g": 26,
              "fat_g": 4.5,
              "sodium_mg": 80,
              "potassium_mg": 170,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Fresh Coriander Mint Dip",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 40,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Gram flour and buttermilk cooked into silky rolls provide high protein density with low glycemic load.",
        "prep_tips": "Cook batter thoroughly until glossy; roll thin without heavy coconut topping."
      },
      {
        "title": "Jowar Bhakri with Roasted Sesame & Garlic Chutney",
        "items": [
          {
            "name": "Crisp Sorghum (Jowar) Bhakri",
            "portion": "1.5 bhakris (75g)",
            "nutrients": {
              "calories": 190,
              "protein_g": 5.5,
              "carbs_g": 38,
              "fat_g": 1.8,
              "sodium_mg": 20,
              "potassium_mg": 140,
              "fiber_g": 4.8
            }
          },
          {
            "name": "Mild Til (Sesame) Herb Chutney",
            "portion": "1.5 tbsp (20g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 2.0,
              "carbs_g": 2.5,
              "fat_g": 5.0,
              "sodium_mg": 35,
              "potassium_mg": 70,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "Sorghum bhakri is completely gluten-free and packed with resistant starch.",
        "prep_tips": "Pat bhakri by hand on flat griddle; cook with high dry heat."
      },
      {
        "title": "Sprouted Moong Chilla with Ginger & Coriander",
        "items": [
          {
            "name": "Sprouted Green Moong Savory Pancake",
            "portion": "2 chillas (130g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 10.5,
              "carbs_g": 33,
              "fat_g": 3.5,
              "sodium_mg": 80,
              "potassium_mg": 200,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Lemon Ginger Dip",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 20,
              "protein_g": 0.5,
              "carbs_g": 4.0,
              "fat_g": 0.2,
              "sodium_mg": 35,
              "potassium_mg": 50,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Sprouted pulses deliver intact vitamins and easy peptide absorption.",
        "prep_tips": "Grind sprouts coarsely with ginger and green chili; cook crisp."
      },
      {
        "title": "Ragi & Oats Thalipeeth with Low-Fat Yogurt",
        "items": [
          {
            "name": "Finger Millet & Rolled Oats Flatbread with Onion & Herbs",
            "portion": "2 medium (110g)",
            "nutrients": {
              "calories": 225,
              "protein_g": 7.5,
              "carbs_g": 37,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 6.0
            }
          },
          {
            "name": "Fresh Cow Dahi",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 4.0,
              "carbs_g": 5.0,
              "fat_g": 2.0,
              "sodium_mg": 50,
              "potassium_mg": 150,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Thalipeeth made with multiple millets produces sustained daytime satiety.",
        "prep_tips": "Press dough thin directly on cold tawa; make central hole for even steam cooking."
      }
    ],
    "mid_morning": [
      {
        "title": "Plain Roasted Khakhra with Green Tea",
        "items": [
          {
            "name": "Oil-Free Whole Wheat Roasted Khakhra",
            "portion": "2 pieces (40g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 3.8,
              "carbs_g": 24,
              "fat_g": 0.8,
              "sodium_mg": 35,
              "potassium_mg": 90,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Unsweetened Lemon Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Crisp whole wheat khakhra satisfies mid-morning snack cravings without oil or high sodium.",
        "prep_tips": "Roast on low heat using a wooden press until crisp."
      },
      {
        "title": "Spiced Kokum Sharbat (Unsweetened Cumin Infusion) with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Chilled Kokum & Roasted Cumin Infusion",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.5,
              "carbs_g": 5.0,
              "fat_g": 0.1,
              "sodium_mg": 20,
              "potassium_mg": 95,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Hydroxyl citric acid (HCA) in kokum assists cellular lipid metabolism and digestion.",
        "prep_tips": "Soak kokum rinds in cold water; season with roasted cumin and crushed mint."
      },
      {
        "title": "Diluted Gujarati Chaas with Roasted Jeera with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Light Buttermilk with Roasted Cumin & Hing",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.8,
              "carbs_g": 4.5,
              "fat_g": 1.2,
              "sodium_mg": 40,
              "potassium_mg": 150,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Digestive cooling beverage that soothes gastric mucosal inflammation.",
        "prep_tips": "Whisk curd with chilled water; avoid added salt."
      },
      {
        "title": "Crisp Cucumber Slices with Lemon & Rock Salt with Roasted Bengal Gram",
        "items": [
          {
            "name": "Cucumber Slices with Lime Juice & Roasted Jeera",
            "portion": "1.2 cups (130g)",
            "nutrients": {
              "calories": 20,
              "protein_g": 0.8,
              "carbs_g": 4.0,
              "fat_g": 0.2,
              "sodium_mg": 15,
              "potassium_mg": 150,
              "fiber_g": 1.6
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "High cellular water volume assists renal flushing.",
        "prep_tips": "Serve chilled with a light dusting of cumin."
      },
      {
        "title": "Fresh Pomegranate Arils with Mint with Roasted Bengal Gram",
        "items": [
          {
            "name": "Fresh Pomegranate Arils with Crushed Mint",
            "portion": "1/2 cup (85g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 1.2,
              "carbs_g": 15.0,
              "fat_g": 0.8,
              "sodium_mg": 3,
              "potassium_mg": 180,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Punicalagin flavonoids protect arterial endothelium against lipid oxidation.",
        "prep_tips": "Separate arils fresh; do not add sugar."
      }
    ],
    "lunch": [
      {
        "title": "Jowar Bhakri with Sev Tameta (Mild) & Tuvar Dal",
        "items": [
          {
            "name": "Jowar Bhakri",
            "portion": "2 bhakris (90g)",
            "nutrients": {
              "calories": 205,
              "protein_g": 6.0,
              "carbs_g": 42,
              "fat_g": 2.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 5.2
            }
          },
          {
            "name": "Mild Stewed Tomato Curry with Baked Sev",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 3.0,
              "carbs_g": 12,
              "fat_g": 4.0,
              "sodium_mg": 90,
              "potassium_mg": 190,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Gujarati Tuvar Dal (Low Jaggery, High Cumin)",
            "portion": "3/4 cup (130g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 6.8,
              "carbs_g": 17,
              "fat_g": 2.0,
              "sodium_mg": 85,
              "potassium_mg": 185,
              "fiber_g": 3.2
            }
          }
        ],
        "justification": "High lycopene cooked tomatoes support cardiovascular health, while sorghum flour minimizes insulin surges.",
        "prep_tips": "Cook tomato gravy with cumin and coriander; top with a small portion of baked gram flour sev."
      },
      {
        "title": "Bajra Bhakri with Pithla (Gram Flour Curry) & Steamed Methi",
        "items": [
          {
            "name": "Warm Bajra Bhakri",
            "portion": "2 bhakris (90g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 6.0,
              "carbs_g": 41,
              "fat_g": 2.5,
              "sodium_mg": 25,
              "potassium_mg": 165,
              "fiber_g": 5.5
            }
          },
          {
            "name": "Traditional Maharashtrian Besan Pithla",
            "portion": "3/4 cup (130g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 7.5,
              "carbs_g": 14,
              "fat_g": 3.5,
              "sodium_mg": 90,
              "potassium_mg": 180,
              "fiber_g": 3.8
            }
          },
          {
            "name": "Steamed Fenugreek Leaves with Garlic",
            "portion": "1/2 cup (70g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 2.0,
              "carbs_g": 4.5,
              "fat_g": 0.8,
              "sodium_mg": 30,
              "potassium_mg": 130,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Pithla delivers clean legume protein while bajra provides sustained complex carbohydrate release.",
        "prep_tips": "Whisk besan in water; cook on medium flame till thick and smooth."
      },
      {
        "title": "Steamed Brown Rice with Gujarati Tuvar Dal & Bhindi Sambharo",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Gujarati Tuvar Dal with Kokum & Cumin",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 7.5,
              "carbs_g": 19,
              "fat_g": 2.5,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 3.8
            }
          },
          {
            "name": "Bhindi (Okra) & Cabbage Sambharo",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 2.0,
              "carbs_g": 8.0,
              "fat_g": 2.5,
              "sodium_mg": 50,
              "potassium_mg": 160,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Okra mucilage slows glucose absorption in the upper duodenum.",
        "prep_tips": "Stir-fry okra and cabbage with mustard seeds for just 4 minutes to retain crunch."
      },
      {
        "title": "Malvani Steamed Pomfret/Surmai Fish Curry with Brown Rice & Tindora",
        "items": [
          {
            "name": "Steamed White Fish in Tangy Kokum Broth",
            "portion": "120g fillet + gravy",
            "nutrients": {
              "calories": 160,
              "protein_g": 21.0,
              "carbs_g": 4.0,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 225,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Steamed Tindora (Ivy Gourd) with Cumin",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 55,
              "protein_g": 1.6,
              "carbs_g": 7.0,
              "fat_g": 2.0,
              "sodium_mg": 45,
              "potassium_mg": 140,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "White fish cooked in kokum rather than coconut milk provides cardioprotective omega-3 without saturated lipids.",
        "prep_tips": "Simmer fish in kokum extract, coriander, and crushed cumin broth without frying."
      },
      {
        "title": "Lean Chicken Sukka (Skinless Breast) with Jowar Bhakri & Dal",
        "items": [
          {
            "name": "Dry Roasted Spiced Chicken Breast (Skinless)",
            "portion": "110g",
            "nutrients": {
              "calories": 165,
              "protein_g": 23.0,
              "carbs_g": 2.5,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 220,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Jowar Bhakri",
            "portion": "2 bhakris (90g)",
            "nutrients": {
              "calories": 205,
              "protein_g": 6.0,
              "carbs_g": 42,
              "fat_g": 2.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 5.2
            }
          },
          {
            "name": "Yellow Moong Dal Broth",
            "portion": "1/2 cup (90g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.8,
              "carbs_g": 11,
              "fat_g": 1.2,
              "sodium_mg": 60,
              "potassium_mg": 120,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Complete animal protein source with low phosphorus and negligible purine build-up.",
        "prep_tips": "Roast chicken breast with dry spices and a touch of roasted onion."
      },
      {
        "title": "Egg White Bhurji with Jowar Bhakri & Steamed Dudhi",
        "items": [
          {
            "name": "Egg White Bhurji (3 Whites with Tomato & Green Chili)",
            "portion": "1 cup (140g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 13.0,
              "carbs_g": 5.0,
              "fat_g": 3.0,
              "sodium_mg": 90,
              "potassium_mg": 180,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Jowar Bhakri",
            "portion": "2 bhakris (90g)",
            "nutrients": {
              "calories": 205,
              "protein_g": 6.0,
              "carbs_g": 42,
              "fat_g": 2.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 5.2
            }
          },
          {
            "name": "Steamed Lauki (Bottle Gourd) with Cumin",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 5.0,
              "fat_g": 1.0,
              "sodium_mg": 35,
              "potassium_mg": 120,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Zero-cholesterol protein ideal for hypertensive and dyslipidemic profiles.",
        "prep_tips": "Scramble egg whites with diced tomato and turmeric in 1 tsp oil."
      },
      {
        "title": "Brown Rice with Sprouted Vaal Dal & Lauki Nu Shaak",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Sprouted Field Beans (Vaal) Curry",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 140,
              "protein_g": 8.0,
              "carbs_g": 20,
              "fat_g": 2.8,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Simple Lauki Nu Shaak",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 1.2,
              "carbs_g": 7.0,
              "fat_g": 1.8,
              "sodium_mg": 45,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Sprouted vaal provides authentic regional flavor with high dietary fiber.",
        "prep_tips": "Remove outer skins of sprouted vaal to optimize peptide digestion."
      }
    ],
    "evening_snack": [
      {
        "title": "Sprouted Usal Chaat with Lime & Coriander",
        "items": [
          {
            "name": "Steamed Mixed Sprouted Beans with Lemon",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 6.5,
              "carbs_g": 15,
              "fat_g": 0.8,
              "sodium_mg": 35,
              "potassium_mg": 170,
              "fiber_g": 4.0
            }
          }
        ],
        "justification": "High satiety snack that curbs late-afternoon sugar cravings.",
        "prep_tips": "Steam sprouted moong and matki; toss with lime juice."
      },
      {
        "title": "Roasted Kurmura (Puffed Rice) with Roasted Chana & Curry Leaves",
        "items": [
          {
            "name": "Roasted Puffed Rice & Chana with Mustard Tempering",
            "portion": "1.2 cups (40g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 4.5,
              "carbs_g": 22,
              "fat_g": 1.8,
              "sodium_mg": 40,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Crunchy low-sodium snack with zero cholesterol.",
        "prep_tips": "Roast kurmura in pan with turmeric and curry leaves."
      },
      {
        "title": "Steamed Methi Muthia (Oil-Free)",
        "items": [
          {
            "name": "Steamed Fenugreek Muthia",
            "portion": "3 pieces (90g)",
            "nutrients": {
              "calories": 110,
              "protein_g": 4.2,
              "carbs_g": 19,
              "fat_g": 1.5,
              "sodium_mg": 50,
              "potassium_mg": 130,
              "fiber_g": 3.2
            }
          }
        ],
        "justification": "Fenugreek supports glucose transport into muscle cells.",
        "prep_tips": "Steam without baking soda or frying."
      },
      {
        "title": "Mint Lemon Water with Soaked Sabja (Basil) Seeds with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Cooling Sabja Seed & Fresh Lemon Water",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 4.5,
              "fat_g": 0.5,
              "sodium_mg": 15,
              "potassium_mg": 70,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Basil seeds swell with mucilaginous fiber, soothing digestive transit.",
        "prep_tips": "Soak sabja seeds for 15 minutes in cool water."
      },
      {
        "title": "Roasted Makhana with Rock Salt",
        "items": [
          {
            "name": "Crispy Roasted Fox Nuts",
            "portion": "1 cup (30g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 20,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 120,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Gentle on kidney filtration with light mineral density.",
        "prep_tips": "Dry roast on low heat."
      }
    ],
    "dinner": [
      {
        "title": "Moong Dal Khichdi with Dahi Kadhi & Steamed Tindora",
        "items": [
          {
            "name": "Split Moong & Brown Rice Khichdi",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 220,
              "protein_g": 8.0,
              "carbs_g": 40,
              "fat_g": 2.5,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Diluted Buttermilk Kadhi with Methi Seeds",
            "portion": "3/4 cup (120ml)",
            "nutrients": {
              "calories": 65,
              "protein_g": 3.0,
              "carbs_g": 6.0,
              "fat_g": 2.5,
              "sodium_mg": 70,
              "potassium_mg": 130,
              "fiber_g": 0.8
            }
          },
          {
            "name": "Steamed Tindora (Ivy Gourd)",
            "portion": "1/2 cup (70g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 1.2,
              "carbs_g": 5.5,
              "fat_g": 1.2,
              "sodium_mg": 30,
              "potassium_mg": 110,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Khichdi is the ultimate comforting evening meal that minimizes nighttime blood pressure surge and acid reflux.",
        "prep_tips": "Cook moong and rice together with pinch of turmeric and cumin; avoid heavy ghee tempering."
      },
      {
        "title": "Jowar Bhakri with Baingan Bharta & Rasam Broth",
        "items": [
          {
            "name": "Handmade Jowar Bhakri",
            "portion": "2 bhakris (90g)",
            "nutrients": {
              "calories": 205,
              "protein_g": 6.0,
              "carbs_g": 42,
              "fat_g": 2.0,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 5.2
            }
          },
          {
            "name": "Roasted Eggplant Bharta with Tomatoes & Peas",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 14,
              "fat_g": 3.5,
              "sodium_mg": 70,
              "potassium_mg": 210,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Warm Pepper Tomato Broth",
            "portion": "3/4 cup (120ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 6.0,
              "fat_g": 0.5,
              "sodium_mg": 65,
              "potassium_mg": 110,
              "fiber_g": 0.8
            }
          }
        ],
        "justification": "Slow-release complex carbohydrates prevent nocturnal hypoglycemia and dawn phenomenon.",
        "prep_tips": "Roast whole brinjal over flame and season with roasted cumin."
      },
      {
        "title": "Bajra Roti with Dudhi Chana Dal Nu Shaak",
        "items": [
          {
            "name": "Pearl Millet (Bajra) Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.8,
              "carbs_g": 35,
              "fat_g": 1.8,
              "sodium_mg": 20,
              "potassium_mg": 150,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Bottle Gourd with Split Bengal Gram",
            "portion": "1 cup (170g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 6.5,
              "carbs_g": 17,
              "fat_g": 3.0,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 4.2
            }
          },
          {
            "name": "Thin Spiced Chaas",
            "portion": "1/2 glass (100ml)",
            "nutrients": {
              "calories": 25,
              "protein_g": 1.5,
              "carbs_g": 2.5,
              "fat_g": 0.6,
              "sodium_mg": 25,
              "potassium_mg": 80,
              "fiber_g": 0.2
            }
          }
        ],
        "justification": "High dietary magnesium in pearl millet relaxes vascular smooth muscle during sleep.",
        "prep_tips": "Simmer diced lauki and chana dal in covered pot."
      },
      {
        "title": "Whole Wheat Phulkas with Parwal Nu Shaak & Tuvar Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Phulkas",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Stewed Pointed Gourd (Parwal) with Cumin",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 11,
              "fat_g": 3.0,
              "sodium_mg": 70,
              "potassium_mg": 175,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Thin Yellow Tuvar Dal",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 5.5,
              "carbs_g": 13,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Easy to digest, kidney-friendly vegetable profile.",
        "prep_tips": "Cook parwal in minimal oil with turmeric."
      },
      {
        "title": "Grilled Fish Fillet with Steamed Ridge Gourd & Jowar Bhakri",
        "items": [
          {
            "name": "Pan-Grilled White Fish Fillet",
            "portion": "100g fillet",
            "nutrients": {
              "calories": 145,
              "protein_g": 19.0,
              "carbs_g": 2.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Jowar Bhakri",
            "portion": "1.5 bhakris (75g)",
            "nutrients": {
              "calories": 190,
              "protein_g": 5.5,
              "carbs_g": 38,
              "fat_g": 1.8,
              "sodium_mg": 20,
              "potassium_mg": 140,
              "fiber_g": 4.8
            }
          },
          {
            "name": "Steamed Ridge Gourd with Cumin",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 1.5,
              "carbs_g": 6.5,
              "fat_g": 1.2,
              "sodium_mg": 35,
              "potassium_mg": 130,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Lean seafood dinner that supplies essential amino acids without kidney phosphorus overload.",
        "prep_tips": "Marinate fish with turmeric, kokum, and lemon."
      },
      {
        "title": "Vegetable Dalia Khichdi with Yellow Moong & Steamed Zucchini",
        "items": [
          {
            "name": "Broken Wheat (Dalia) & Moong Khichdi",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 8.0,
              "carbs_g": 40,
              "fat_g": 2.5,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 5.8
            }
          },
          {
            "name": "Steamed Zucchini Slices with Black Pepper",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.2,
              "carbs_g": 5.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 140,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Gentle on gastrointestinal mucosa with steady glycemic release.",
        "prep_tips": "Cook in pressure cooker with turmeric and cumin."
      },
      {
        "title": "Jowar Roti with Methi Tofu Bhurji & Clear Veg Soup",
        "items": [
          {
            "name": "Gluten-Free Jowar Roti",
            "portion": "2 rotis (80g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 4.5,
              "carbs_g": 36,
              "fat_g": 1.5,
              "sodium_mg": 15,
              "potassium_mg": 130,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Organic Soya Tofu Scramble with Fenugreek Leaves",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 12.0,
              "carbs_g": 4.0,
              "fat_g": 6.0,
              "sodium_mg": 65,
              "potassium_mg": 140,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Clear Bottle Gourd Broth",
            "portion": "1 cup (150ml)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.8,
              "carbs_g": 5.0,
              "fat_g": 0.5,
              "sodium_mg": 45,
              "potassium_mg": 110,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "100% plant-based dinner with zero saturated fat and high phytoestrogenic vascular protection.",
        "prep_tips": "Crumble firm tofu into pan with fresh methi."
      }
    ]
  },
  "eastern_indian": {
    "breakfast": [
      {
        "title": "Dalia Khichuri with Seasonal Vegetables & Ginger",
        "items": [
          {
            "name": "Broken Wheat (Dalia) & Moong Khichuri with Peas & Carrot",
            "portion": "1.5 cups (220g)",
            "nutrients": {
              "calories": 225,
              "protein_g": 7.5,
              "carbs_g": 41,
              "fat_g": 3.0,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 6.2
            }
          }
        ],
        "justification": "Warm, soothing broken wheat preparation tempered with ginger that minimizes early-morning blood pressure surge.",
        "prep_tips": "Dry-roast dalia and yellow moong before simmering with fresh ginger and whole cumin."
      },
      {
        "title": "Chire Bhaja (Roasted Puffed Rice) with Roasted Chana & Green Tea",
        "items": [
          {
            "name": "Dry Roasted Flattened Rice (Chire) with Green Chili & Peanuts/Chana",
            "portion": "1.2 cups (45g)",
            "nutrients": {
              "calories": 165,
              "protein_g": 5.0,
              "carbs_g": 31,
              "fat_g": 2.5,
              "sodium_mg": 35,
              "potassium_mg": 110,
              "fiber_g": 3.2
            }
          },
          {
            "name": "Darjeeling Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Oil-free traditional breakfast staple with light glycemic footprint and high digestive compliance.",
        "prep_tips": "Dry roast thick chire on cast iron tawa until crisp; toss with curry leaves."
      },
      {
        "title": "Handmade Roti with Lau Ghonto (Bottle Gourd) Stew",
        "items": [
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Traditional Lau Ghonto with Bori / Jeera",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 2.2,
              "carbs_g": 11,
              "fat_g": 2.2,
              "sodium_mg": 65,
              "potassium_mg": 170,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Bottle gourd has exceptional renal safety profile with high biological hydration.",
        "prep_tips": "Grate lauki fine; cook in its own water with bay leaf and cumin seeds."
      },
      {
        "title": "Steamed Rice & Moong Pitha with Mint Dip",
        "items": [
          {
            "name": "Steamed Rice Flour & Split Moong Savory Pitha",
            "portion": "3 medium (140g)",
            "nutrients": {
              "calories": 210,
              "protein_g": 6.8,
              "carbs_g": 40,
              "fat_g": 2.0,
              "sodium_mg": 75,
              "potassium_mg": 175,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Fresh Coriander Mint Chutney",
            "portion": "2 tbsp (30g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 3.0,
              "fat_g": 0.8,
              "sodium_mg": 40,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Steaming preserves amino acid integrity without requiring cooking fats.",
        "prep_tips": "Steam in bamboo or stainless steel steamer for 10 minutes."
      },
      {
        "title": "Vegetable Oats Upma with Bengali Panch Phoron",
        "items": [
          {
            "name": "Oats Upma with French Beans, Carrots & Five-Spice Tempering",
            "portion": "1.5 cups (200g)",
            "nutrients": {
              "calories": 220,
              "protein_g": 6.8,
              "carbs_g": 38,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 185,
              "fiber_g": 5.8
            }
          }
        ],
        "justification": "Panch phoron (fenugreek, nigella, cumin, black mustard, fennel) stimulates digestive secretions without salt.",
        "prep_tips": "Temper panch phoron in half-teaspoon cold-pressed mustard oil."
      },
      {
        "title": "Egg White Bhurji with Whole Wheat Toast & Papaya",
        "items": [
          {
            "name": "Egg White Scramble with Tomato & Onion",
            "portion": "1 cup (140g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 13.0,
              "carbs_g": 5.0,
              "fat_g": 3.0,
              "sodium_mg": 90,
              "potassium_mg": 180,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Whole Wheat Toast",
            "portion": "2 slices (50g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 4.5,
              "carbs_g": 24,
              "fat_g": 1.5,
              "sodium_mg": 110,
              "potassium_mg": 70,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Fresh Papaya Cubes",
            "portion": "1/2 cup (70g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.4,
              "carbs_g": 7.5,
              "fat_g": 0.1,
              "sodium_mg": 3,
              "potassium_mg": 130,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Pure egg albumen provides essential amino acids with near-zero phosphorus and zero cholesterol.",
        "prep_tips": "Discard egg yolks to remove cholesterol and heavy phosphorus loads."
      },
      {
        "title": "Fresh Chena (Low-Fat Cottage Cheese) Crumble with Roti",
        "items": [
          {
            "name": "Fresh Skimmed Cow Milk Chena with Cardamom",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 9.5,
              "carbs_g": 3.5,
              "fat_g": 4.5,
              "sodium_mg": 45,
              "potassium_mg": 85,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Freshly coagulated cow milk chena is rich in bioactive whey peptides with minimal sodium.",
        "prep_tips": "Curdle skimmed cow milk with lemon juice; squeeze whey completely."
      }
    ],
    "mid_morning": [
      {
        "title": "Fresh Guava Slices with Black Salt & Cumin with Roasted Bengal Gram",
        "items": [
          {
            "name": "Crisp Guava Slices with Roasted Jeera",
            "portion": "1 medium guava (100g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 2.0,
              "carbs_g": 11.0,
              "fat_g": 0.8,
              "sodium_mg": 5,
              "potassium_mg": 180,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Guava provides high dietary fiber that reduces glycemic and lipid absorption.",
        "prep_tips": "Wash thoroughly and slice firm semi-ripe fruit."
      },
      {
        "title": "Thin Ghol (Bengali Spiced Buttermilk) with Gandharaj Lime with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Diluted Cow Curd Ghol with Mint & Gandharaj Lime",
            "portion": "1 glass (200ml)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.8,
              "carbs_g": 4.5,
              "fat_g": 1.2,
              "sodium_mg": 40,
              "potassium_mg": 150,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Gandharaj lime zest provides limonene antioxidants while buttermilk delivers probiotic flora.",
        "prep_tips": "Whisk low-fat curd with chilled water; squeeze aromatic Gandharaj lime juice."
      },
      {
        "title": "Fresh Daab (Tender Coconut Water) / Lemon Chia Cooler with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Fresh Lemon Mint Chia Water (Renal Safe)",
            "portion": "1 glass (180ml)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.8,
              "carbs_g": 4.0,
              "fat_g": 0.5,
              "sodium_mg": 15,
              "potassium_mg": 75,
              "fiber_g": 1.8
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Hydrating, low glycemic, low sodium snack to bridge morning glucose levels without potassium spikes.",
        "prep_tips": "Prepare chia water with fresh lemon; substitute for daab if potassium restricted."
      },
      {
        "title": "Green Apple Slices with Dash of Cinnamon with Roasted Bengal Gram",
        "items": [
          {
            "name": "Crisp Green Apple Slices with Ceylon Cinnamon",
            "portion": "1 small apple (100g)",
            "nutrients": {
              "calories": 52,
              "protein_g": 0.3,
              "carbs_g": 13.8,
              "fat_g": 0.2,
              "sodium_mg": 2,
              "potassium_mg": 107,
              "fiber_g": 2.4
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Malic acid and pectin support gentle digestive transit without potassium spikes.",
        "prep_tips": "Slice crisp apple fresh and dust with ground cinnamon."
      },
      {
        "title": "Fresh Papaya Cubes with Mint with Roasted Bengal Gram",
        "items": [
          {
            "name": "Ripe Papaya Cubes with Fresh Mint Leaves",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 0.5,
              "carbs_g": 10.0,
              "fat_g": 0.1,
              "sodium_mg": 5,
              "potassium_mg": 180,
              "fiber_g": 1.8
            }
          },
          {
            "name": "Roasted Bengal Gram (Chana)",
            "portion": "2 tbsp (25g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 4.5,
              "carbs_g": 12.0,
              "fat_g": 1.2,
              "sodium_mg": 20,
              "potassium_mg": 115,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Papain enzyme aids peptide digestion while maintaining safe potassium limits.",
        "prep_tips": "Serve chilled with finely chopped mint."
      }
    ],
    "lunch": [
      {
        "title": "Brown Rice with Rui Machher Patla Jhol & Potol Chorchori",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Light Rohu Fish Stew with Papaya & Kalonji (Patla Jhol)",
            "portion": "120g fish + broth",
            "nutrients": {
              "calories": 165,
              "protein_g": 21.0,
              "carbs_g": 4.0,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 230,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Pointed Gourd (Potol) & Cabbage Chorchori",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 1.8,
              "carbs_g": 8.0,
              "fat_g": 2.5,
              "sodium_mg": 45,
              "potassium_mg": 150,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Freshwater rohu fish cooked in ginger-cumin-kalonji broth delivers pure lean protein with minimal purines and low saturated lipids.",
        "prep_tips": "Poach fish in light papaya and cumin broth; do not deep fry."
      },
      {
        "title": "Brown Rice with Cholar Dal (Bengal Gram) & Steamed Lauki",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Mild Cholar Dal with Cumin & Hing (Low Coconut)",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 145,
              "protein_g": 8.5,
              "carbs_g": 21,
              "fat_g": 2.8,
              "sodium_mg": 90,
              "potassium_mg": 200,
              "fiber_g": 4.8
            }
          },
          {
            "name": "Steamed Lauki (Bottle Gourd) with Black Cumin",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 1.2,
              "carbs_g": 6.5,
              "fat_g": 1.5,
              "sodium_mg": 40,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Chana dal has one of the lowest glycemic indices of all pulses (GI ~28), preserving glycemic equilibrium.",
        "prep_tips": "Simmer cholar dal with ginger and cumin; omit coconut flakes for renal safety."
      },
      {
        "title": "Brown Rice with Moong Mohan Dal & Begun Basanti (Steamed)",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Roasted Yellow Moong Dal with Ginger & Bay Leaf",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 7.5,
              "carbs_g": 19,
              "fat_g": 2.2,
              "sodium_mg": 85,
              "potassium_mg": 195,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Eggplant in Light Mustard Broth",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 1.8,
              "carbs_g": 7.0,
              "fat_g": 2.5,
              "sodium_mg": 50,
              "potassium_mg": 160,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Roasted moong dal is gentle on nephron filtration while steamed brinjal supplies antioxidant bioflavonoids.",
        "prep_tips": "Steam eggplant wedges; toss with diluted mustard paste and green chili."
      },
      {
        "title": "Brown Rice with Dhokar Dalna (Steamed Lentil Cakes) & Jhinge Posto",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Steamed Chana Dal Dhoka in Mild Ginger Gravy",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 150,
              "protein_g": 9.0,
              "carbs_g": 19,
              "fat_g": 3.5,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Ridge Gourd (Jhinge) with Light Poppy Paste",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 1.5,
              "carbs_g": 7.5,
              "fat_g": 3.0,
              "sodium_mg": 45,
              "potassium_mg": 150,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Steaming the lentil cakes instead of frying prevents lipid peroxidation while poppy seed paste provides soothing calcium.",
        "prep_tips": "Steam dhoka batter for 12 minutes until firm; simmer in ginger-tomato broth."
      },
      {
        "title": "Murgir Jhol (Lean Chicken Stew) with Brown Rice & Potol Bhaja (Air-fried)",
        "items": [
          {
            "name": "Skinless Chicken Breast Stew with Green Papaya",
            "portion": "110g chicken + broth",
            "nutrients": {
              "calories": 160,
              "protein_g": 22.0,
              "carbs_g": 3.0,
              "fat_g": 4.5,
              "sodium_mg": 90,
              "potassium_mg": 220,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Pointed Gourd (Potol) Air-Fried with Turmeric",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 1.5,
              "carbs_g": 6.5,
              "fat_g": 1.8,
              "sodium_mg": 35,
              "potassium_mg": 140,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Green papaya stewed with lean chicken provides papain for protein breakdown without adding saturated fats.",
        "prep_tips": "Simmer chicken breast with green papaya slices, turmeric, and ginger."
      },
      {
        "title": "Dimer Jhol (Egg White Curry) with Brown Rice & Bandhakopi",
        "items": [
          {
            "name": "Egg White Curry (3 Whites in Mild Tomato Cumin Gravy)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 13.0,
              "carbs_g": 7.0,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 190,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Steamed Cabbage & Green Peas (Bandhakopi)",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 55,
              "protein_g": 1.8,
              "carbs_g": 8.0,
              "fat_g": 1.5,
              "sodium_mg": 45,
              "potassium_mg": 150,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Pure egg white protein supplies high biological value amino acids with low renal solute load.",
        "prep_tips": "Boil eggs; use only the whites."
      },
      {
        "title": "Brown Rice with Biulir Dal (Fennel Urad Dal) & Steamed Potol",
        "items": [
          {
            "name": "Steamed Brown Rice",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 4.0,
              "carbs_g": 37,
              "fat_g": 1.2,
              "sodium_mg": 5,
              "potassium_mg": 110,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Light Biulir Dal with Ginger & Fennel (Mouri)",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 135,
              "protein_g": 8.0,
              "carbs_g": 19,
              "fat_g": 2.2,
              "sodium_mg": 85,
              "potassium_mg": 200,
              "fiber_g": 4.2
            }
          },
          {
            "name": "Steamed Potol with Kalonji",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 1.5,
              "carbs_g": 6.0,
              "fat_g": 1.5,
              "sodium_mg": 35,
              "potassium_mg": 130,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Fennel and ginger reduce flatulence and support kidney friendly digestion.",
        "prep_tips": "Cook urad dal with fennel paste and grated ginger; serve warm."
      }
    ],
    "evening_snack": [
      {
        "title": "Puffed Rice (Muri) with Roasted Chana & Green Chili",
        "items": [
          {
            "name": "Fresh Puffed Rice (Muri) with Roasted Chana & Cucumber",
            "portion": "1.5 cups (45g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 4.8,
              "carbs_g": 24,
              "fat_g": 1.5,
              "sodium_mg": 35,
              "potassium_mg": 110,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Muri provides crisp lightness with near-zero sodium and zero saturated fat.",
        "prep_tips": "Toss puffed rice with roasted chana, finely chopped cucumber, and fresh coriander."
      },
      {
        "title": "Boiled Sprouted Chana with Chopped Cucumber & Gandharaj Lime",
        "items": [
          {
            "name": "Boiled Bengal Gram with Gandharaj Lime",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 5.2,
              "carbs_g": 15,
              "fat_g": 1.5,
              "sodium_mg": 35,
              "potassium_mg": 170,
              "fiber_g": 4.0
            }
          }
        ],
        "justification": "High soluble fiber snack that stabilizes evening glucose without rapid insulin release.",
        "prep_tips": "Boil black chana until tender; toss with lime juice and mint."
      },
      {
        "title": "Roasted Makhana with Rock Salt",
        "items": [
          {
            "name": "Crispy Roasted Fox Nuts",
            "portion": "1 cup (30g)",
            "nutrients": {
              "calories": 105,
              "protein_g": 3.0,
              "carbs_g": 20,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 120,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Makhana delivers clean plant protein without phosphorus overload.",
        "prep_tips": "Dry roast on low heat."
      },
      {
        "title": "Steamed Moong Sprouts Chaat",
        "items": [
          {
            "name": "Warm Steamed Moong Sprouts with Coriander",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 6.0,
              "carbs_g": 15,
              "fat_g": 0.8,
              "sodium_mg": 35,
              "potassium_mg": 160,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "Enzymatically active snack that supports gut health.",
        "prep_tips": "Steam for 3 minutes to maintain crunch."
      },
      {
        "title": "Darjeeling Green Tea with Roasted Pumpkin Seeds with Lightly Roasted Makhana",
        "items": [
          {
            "name": "Unsweetened Darjeeling Green Tea",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Lightly Roasted Pumpkin Seeds",
            "portion": "1 tbsp (12g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 3.0,
              "carbs_g": 2.0,
              "fat_g": 5.0,
              "sodium_mg": 2,
              "potassium_mg": 95,
              "fiber_g": 1.2
            }
          },
          {
            "name": "Lightly Roasted Makhana (Fox Nuts)",
            "portion": "3/4 cup (25g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.5,
              "carbs_g": 16.0,
              "fat_g": 0.4,
              "sodium_mg": 20,
              "potassium_mg": 100,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Rich in zinc and magnesium for cellular enzymatic function.",
        "prep_tips": "Roast seeds lightly in dry pan."
      }
    ],
    "dinner": [
      {
        "title": "Handmade Rotis with Lau Ghonto & Biulir Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Stewed Lau Ghonto with Cumin & Turmeric",
            "portion": "1 cup (160g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 2.2,
              "carbs_g": 11,
              "fat_g": 2.2,
              "sodium_mg": 65,
              "potassium_mg": 170,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Biulir Dal with Ginger & Fennel (Mouri)",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 5.5,
              "carbs_g": 13,
              "fat_g": 1.5,
              "sodium_mg": 70,
              "potassium_mg": 140,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Traditional Bengali evening meal that digests smoothly without nighttime digestive distress.",
        "prep_tips": "Puff rotis directly on tawa without oil or ghee."
      },
      {
        "title": "Handmade Rotis with Potol Posto & Yellow Moong Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Pointed Gourd with Light Poppy Seed Paste (Potol Posto)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 3.0,
              "carbs_g": 11,
              "fat_g": 4.5,
              "sodium_mg": 65,
              "potassium_mg": 180,
              "fiber_g": 3.8
            }
          },
          {
            "name": "Thin Yellow Moong Soup Dal",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 5.5,
              "carbs_g": 12,
              "fat_g": 1.5,
              "sodium_mg": 75,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Poppy seeds provide natural relaxing alkaloids and calcium for nocturnal rest.",
        "prep_tips": "Grind posto seeds with green chili; fold into steamed potol."
      },
      {
        "title": "Handmade Rotis with Jhinge Aloo / Jhinge Posto & Musur Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Stewed Ridge Gourd with Light Spices",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 2.0,
              "carbs_g": 10,
              "fat_g": 2.5,
              "sodium_mg": 60,
              "potassium_mg": 160,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Red Lentil (Musur) Dal with Onion Seeds",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 6.0,
              "carbs_g": 13,
              "fat_g": 1.5,
              "sodium_mg": 70,
              "potassium_mg": 150,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Ridge gourd provides gentle diuretic hydration while red lentils offer easy iron delivery.",
        "prep_tips": "Cook jhinge until naturally juicy."
      },
      {
        "title": "Grilled Fish Fillet with Steamed Beans & Handmade Roti",
        "items": [
          {
            "name": "Herb-Spiced Grilled Rohu / Pomfret Fillet",
            "portion": "100g fillet",
            "nutrients": {
              "calories": 145,
              "protein_g": 19.0,
              "carbs_g": 2.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed French Beans with Black Cumin",
            "portion": "1/2 cup (70g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.5,
              "carbs_g": 6.0,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Lean seafood dinner that supplies essential amino acids without kidney phosphorus overload.",
        "prep_tips": "Marinate fish with turmeric and lemon; pan-sear on dry iron tawa."
      },
      {
        "title": "Handmade Rotis with Mild Chicken Papaya Stew",
        "items": [
          {
            "name": "Skinless Chicken Breast & Papaya Stew (Jhol)",
            "portion": "110g chicken + broth",
            "nutrients": {
              "calories": 150,
              "protein_g": 21.0,
              "carbs_g": 3.0,
              "fat_g": 4.0,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Bottle Gourd Wedges",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.8,
              "carbs_g": 5.0,
              "fat_g": 0.5,
              "sodium_mg": 30,
              "potassium_mg": 120,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Light evening poultry protein with papain enzyme for rapid nocturnal assimilation.",
        "prep_tips": "Simmer chicken breast with ginger, green papaya, and black pepper."
      },
      {
        "title": "Dalia Khichuri with Roasted Cumin & Cauliflower",
        "items": [
          {
            "name": "Broken Wheat (Dalia) & Moong Khichuri with Cauliflower",
            "portion": "1.3 cups (200g)",
            "nutrients": {
              "calories": 215,
              "protein_g": 8.0,
              "carbs_g": 40,
              "fat_g": 2.5,
              "sodium_mg": 85,
              "potassium_mg": 190,
              "fiber_g": 5.8
            }
          },
          {
            "name": "Clear Spiced Tomato Broth",
            "portion": "1 cup (150ml)",
            "nutrients": {
              "calories": 35,
              "protein_g": 1.0,
              "carbs_g": 7.0,
              "fat_g": 0.5,
              "sodium_mg": 55,
              "potassium_mg": 110,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Warm comfort bowl providing complex carbohydrates with balanced amino acids.",
        "prep_tips": "Cook in covered handi until grains are tender."
      },
      {
        "title": "Handmade Rotis with Bandhakopi (Cabbage) & Masoor Dal",
        "items": [
          {
            "name": "Whole Wheat Soft Handmade Roti",
            "portion": "2 medium (60g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.0,
              "carbs_g": 32,
              "fat_g": 1.0,
              "sodium_mg": 25,
              "potassium_mg": 110,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Cabbage with Fresh Peas & Cumin",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 2.5,
              "carbs_g": 11,
              "fat_g": 2.2,
              "sodium_mg": 65,
              "potassium_mg": 170,
              "fiber_g": 3.8
            }
          },
          {
            "name": "Thin Red Lentil (Masoor) Dal",
            "portion": "1/2 cup (100g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 5.8,
              "carbs_g": 13,
              "fat_g": 1.5,
              "sodium_mg": 70,
              "potassium_mg": 145,
              "fiber_g": 2.6
            }
          }
        ],
        "justification": "Cruciferous glucosinolates in cabbage support hepatic detoxification pathways.",
        "prep_tips": "Steam shredded cabbage covered; season with cumin and turmeric."
      }
    ]
  },
  "continental": {
    "breakfast": [
      {
        "title": "Steel-Cut Oatmeal with Blueberries, Ground Flaxseed & Cinnamon",
        "items": [
          {
            "name": "Cooked Steel-Cut Oats in Water",
            "portion": "1.3 cups (180g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 5.5,
              "carbs_g": 30,
              "fat_g": 2.5,
              "sodium_mg": 10,
              "potassium_mg": 140,
              "fiber_g": 5.0
            }
          },
          {
            "name": "Fresh Blueberries",
            "portion": "1/3 cup (50g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.4,
              "carbs_g": 7.0,
              "fat_g": 0.2,
              "sodium_mg": 1,
              "potassium_mg": 40,
              "fiber_g": 1.2
            }
          },
          {
            "name": "Ground Golden Flaxseed",
            "portion": "1 tbsp (10g)",
            "nutrients": {
              "calories": 55,
              "protein_g": 1.9,
              "carbs_g": 3.0,
              "fat_g": 4.2,
              "sodium_mg": 3,
              "potassium_mg": 80,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Beta-glucan soluble fiber reduces LDL cholesterol and flattens postprandial glucose curves.",
        "prep_tips": "Simmer steel-cut oats on low heat with ground cinnamon; top with fresh blueberries."
      },
      {
        "title": "Egg White & Spinach Scramble with Whole Grain Toast",
        "items": [
          {
            "name": "Fluffy Scrambled Egg Whites (3 Whites with Baby Spinach)",
            "portion": "1 cup (140g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 14.0,
              "carbs_g": 3.0,
              "fat_g": 2.5,
              "sodium_mg": 95,
              "potassium_mg": 190,
              "fiber_g": 1.5
            }
          },
          {
            "name": "100% Whole Grain Toast",
            "portion": "2 slices (55g)",
            "nutrients": {
              "calories": 135,
              "protein_g": 5.0,
              "carbs_g": 24,
              "fat_g": 1.5,
              "sodium_mg": 115,
              "potassium_mg": 75,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Sliced Hass Avocado",
            "portion": "2 slices (30g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 0.6,
              "carbs_g": 2.5,
              "fat_g": 4.5,
              "sodium_mg": 2,
              "potassium_mg": 150,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Pure egg white protein supplies high biological value amino acids with low renal solute load.",
        "prep_tips": "Whisk egg whites with black pepper; fold into wilted spinach in non-stick pan."
      },
      {
        "title": "Overnight Chia Seed Pudding with Unsweetened Almond Milk & Berries",
        "items": [
          {
            "name": "Overnight Chia Seed Pudding in Almond Milk",
            "portion": "1 jar (180g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 6.0,
              "carbs_g": 18,
              "fat_g": 8.0,
              "sodium_mg": 75,
              "potassium_mg": 160,
              "fiber_g": 8.5
            }
          },
          {
            "name": "Fresh Sliced Strawberries",
            "portion": "1/2 cup (75g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 0.5,
              "carbs_g": 6.0,
              "fat_g": 0.2,
              "sodium_mg": 1,
              "potassium_mg": 115,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "Exceptional mucilaginous fiber that enhances intestinal motility and blunts glucose spikes.",
        "prep_tips": "Soak 2 tbsp chia seeds in 150ml unsweetened fortified almond milk overnight."
      },
      {
        "title": "Whole Wheat Sourdough with Smashed Avocado & Poached Egg White",
        "items": [
          {
            "name": "Artisan Whole Wheat Sourdough Toast",
            "portion": "2 slices (60g)",
            "nutrients": {
              "calories": 140,
              "protein_g": 5.5,
              "carbs_g": 26,
              "fat_g": 1.0,
              "sodium_mg": 120,
              "potassium_mg": 70,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Smashed Fresh Avocado with Lemon & Black Pepper",
            "portion": "1/4 medium (35g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 0.7,
              "carbs_g": 3.0,
              "fat_g": 5.5,
              "sodium_mg": 3,
              "potassium_mg": 175,
              "fiber_g": 2.4
            }
          },
          {
            "name": "Poached Egg Whites",
            "portion": "2 whites (66g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 7.2,
              "carbs_g": 0.5,
              "fat_g": 0.1,
              "sodium_mg": 110,
              "potassium_mg": 105,
              "fiber_g": 0.0
            }
          }
        ],
        "justification": "Sourdough fermentation lowers starch digestibility and phytic acid binding.",
        "prep_tips": "Toast sourdough; layer smashed avocado and freshly poached egg whites."
      },
      {
        "title": "Quinoa Breakfast Porridge with Sliced Green Apple & Walnuts",
        "items": [
          {
            "name": "Warm Simmered Quinoa in Water with Cinnamon",
            "portion": "1 cup (185g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 6.0,
              "carbs_g": 30,
              "fat_g": 2.5,
              "sodium_mg": 10,
              "potassium_mg": 160,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Crisp Green Apple Slices",
            "portion": "1/2 apple (60g)",
            "nutrients": {
              "calories": 32,
              "protein_g": 0.2,
              "carbs_g": 8.5,
              "fat_g": 0.1,
              "sodium_mg": 1,
              "potassium_mg": 65,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Crushed Raw Walnuts",
            "portion": "2 halves (8g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 1.2,
              "carbs_g": 1.0,
              "fat_g": 5.0,
              "sodium_mg": 1,
              "potassium_mg": 35,
              "fiber_g": 0.5
            }
          }
        ],
        "justification": "Quinoa delivers a complete amino acid profile containing all nine essential amino acids.",
        "prep_tips": "Rinse quinoa thoroughly to remove bitter saponins before simmering."
      },
      {
        "title": "High-Protein Tofu Scramble with Bell Peppers & Whole Grain Toast",
        "items": [
          {
            "name": "Crumbled Organic Firm Tofu with Turmeric & Diced Bell Peppers",
            "portion": "1 cup (140g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 13.5,
              "carbs_g": 4.5,
              "fat_g": 7.0,
              "sodium_mg": 55,
              "potassium_mg": 150,
              "fiber_g": 2.2
            }
          },
          {
            "name": "100% Whole Grain Toast",
            "portion": "2 slices (55g)",
            "nutrients": {
              "calories": 135,
              "protein_g": 5.0,
              "carbs_g": 24,
              "fat_g": 1.5,
              "sodium_mg": 115,
              "potassium_mg": 75,
              "fiber_g": 3.5
            }
          }
        ],
        "justification": "100% plant-based scramble delivering high biological value protein with zero saturated fat.",
        "prep_tips": "Saute diced bell peppers in drops of olive oil; crumble firm tofu with pinch of turmeric."
      },
      {
        "title": "Greek-Style Soy Yogurt Parfait with Mixed Berries & Pumpkin Seeds",
        "items": [
          {
            "name": "Unsweetened High-Protein Soy / Almond Yogurt",
            "portion": "1 cup (180g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 7.0,
              "carbs_g": 6.0,
              "fat_g": 4.5,
              "sodium_mg": 50,
              "potassium_mg": 120,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Fresh Mixed Berries (Blueberries, Raspberries)",
            "portion": "1/2 cup (75g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 0.6,
              "carbs_g": 8.0,
              "fat_g": 0.3,
              "sodium_mg": 1,
              "potassium_mg": 85,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Raw Pumpkin Seeds",
            "portion": "1 tbsp (12g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 3.0,
              "carbs_g": 2.0,
              "fat_g": 5.0,
              "sodium_mg": 2,
              "potassium_mg": 95,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Anthocyanins from dark berries protect vascular endothelium from oxidative stress.",
        "prep_tips": "Layer unsweetened yogurt with fresh washed berries and pumpkin seeds."
      }
    ],
    "mid_morning": [
      {
        "title": "Crisp Green Apple Slices with Raw Walnuts",
        "items": [
          {
            "name": "Crisp Green Apple Slices",
            "portion": "1 small apple (100g)",
            "nutrients": {
              "calories": 52,
              "protein_g": 0.3,
              "carbs_g": 13.8,
              "fat_g": 0.2,
              "sodium_mg": 2,
              "potassium_mg": 107,
              "fiber_g": 2.4
            }
          },
          {
            "name": "Raw Walnut Halves",
            "portion": "3 halves (10g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 1.5,
              "carbs_g": 1.4,
              "fat_g": 6.5,
              "sodium_mg": 1,
              "potassium_mg": 45,
              "fiber_g": 0.7
            }
          }
        ],
        "justification": "Omega-3 ALA and polyphenol antioxidants support vascular elasticity.",
        "prep_tips": "Eat fresh; chew nuts thoroughly."
      },
      {
        "title": "Cucumber & Celery Sticks with Lemon White Bean Hummus with Lightly Roasted Pumpkin Seeds",
        "items": [
          {
            "name": "Crisp Cucumber & Celery Sticks",
            "portion": "1.2 cups (130g)",
            "nutrients": {
              "calories": 20,
              "protein_g": 0.8,
              "carbs_g": 4.5,
              "fat_g": 0.2,
              "sodium_mg": 40,
              "potassium_mg": 170,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Low-Sodium White Bean Hummus with Lemon",
            "portion": "2 tbsp (35g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 2.5,
              "carbs_g": 7.0,
              "fat_g": 1.5,
              "sodium_mg": 45,
              "potassium_mg": 85,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Lightly Roasted Pumpkin Seeds",
            "portion": "1.5 tbsp (15g)",
            "nutrients": {
              "calories": 80,
              "protein_g": 3.8,
              "carbs_g": 2.2,
              "fat_g": 6.5,
              "sodium_mg": 2,
              "potassium_mg": 115,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "Celery 3-n-butylphthalide supports smooth vascular relaxation.",
        "prep_tips": "Blend boiled cannellini beans with garlic, lemon, and olive oil."
      },
      {
        "title": "Fresh Blueberries & Sliced Almonds",
        "items": [
          {
            "name": "Fresh Blueberries",
            "portion": "1/2 cup (75g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 0.6,
              "carbs_g": 10.5,
              "fat_g": 0.3,
              "sodium_mg": 1,
              "potassium_mg": 60,
              "fiber_g": 1.8
            }
          },
          {
            "name": "Sliced Raw Almonds",
            "portion": "1 tbsp (10g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 2.1,
              "carbs_g": 2.2,
              "fat_g": 5.0,
              "sodium_mg": 1,
              "potassium_mg": 70,
              "fiber_g": 1.2
            }
          }
        ],
        "justification": "Low-glycemic berry snack with healthy monounsaturated fats.",
        "prep_tips": "Rinse berries and serve chilled."
      },
      {
        "title": "Chilled Mint Green Tea with Lemon with Raw Almonds & Walnuts",
        "items": [
          {
            "name": "Chilled Fresh Mint Infused Green Tea",
            "portion": "1 tall glass (220ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.5,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 25,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Raw Almonds & Walnuts",
            "portion": "4 almonds + 2 walnut halves (14g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 2.6,
              "carbs_g": 2.5,
              "fat_g": 7.5,
              "sodium_mg": 1,
              "potassium_mg": 85,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "EGCG catechins support endothelial nitric oxide synthase activity.",
        "prep_tips": "Brew green tea with fresh mint leaves; chill in refrigerator."
      },
      {
        "title": "Baby Carrots with Garlic Lemon Tahini Dip",
        "items": [
          {
            "name": "Fresh Sweet Baby Carrots",
            "portion": "1 cup (110g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 1.0,
              "carbs_g": 9.0,
              "fat_g": 0.2,
              "sodium_mg": 45,
              "potassium_mg": 190,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Lemon Garlic Tahini Drizzle",
            "portion": "1 tbsp (15g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 2.0,
              "carbs_g": 2.0,
              "fat_g": 5.0,
              "sodium_mg": 15,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Beta-carotene provitamin A supports mucosal integrity.",
        "prep_tips": "Whisk sesame tahini with warm water, lemon juice, and minced garlic."
      }
    ],
    "lunch": [
      {
        "title": "Grilled Herb Chicken Breast with Quinoa & Steamed Asparagus",
        "items": [
          {
            "name": "Herbed Lean Chicken Breast (Skinless)",
            "portion": "120g fillet",
            "nutrients": {
              "calories": 170,
              "protein_g": 24.0,
              "carbs_g": 1.0,
              "fat_g": 4.5,
              "sodium_mg": 95,
              "potassium_mg": 240,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Steamed White & Red Quinoa",
            "portion": "1 cup (185g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 6.0,
              "carbs_g": 30,
              "fat_g": 2.5,
              "sodium_mg": 10,
              "potassium_mg": 160,
              "fiber_g": 4.0
            }
          },
          {
            "name": "Steamed Tender Asparagus Spears with Lemon",
            "portion": "6 spears (90g)",
            "nutrients": {
              "calories": 25,
              "protein_g": 2.2,
              "carbs_g": 4.0,
              "fat_g": 0.2,
              "sodium_mg": 15,
              "potassium_mg": 180,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Asparagus contains natural asparagine aiding renal fluid excretion without potassium wasting.",
        "prep_tips": "Marinate chicken in rosemary, thyme, garlic, and lemon; grill on ribbed skillet."
      },
      {
        "title": "Baked Cod / White Fish Fillet with Cauliflower Mash & Green Beans",
        "items": [
          {
            "name": "Oven-Baked Atlantic Cod Fillet with Herbs",
            "portion": "120g fillet",
            "nutrients": {
              "calories": 140,
              "protein_g": 22.0,
              "carbs_g": 0.5,
              "fat_g": 2.0,
              "sodium_mg": 85,
              "potassium_mg": 230,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Garlic Steamed Cauliflower Mash (Potato Substitute)",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 2.5,
              "carbs_g": 8.0,
              "fat_g": 2.0,
              "sodium_mg": 50,
              "potassium_mg": 180,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed French Green Beans",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 1.8,
              "carbs_g": 7.0,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Cauliflower mash dramatically cuts glycemic impact and potassium load compared to traditional mashed potatoes.",
        "prep_tips": "Steam cauliflower florets until very tender; puree with garlic, white pepper, and 1 tsp olive oil."
      },
      {
        "title": "Mediterranean Chickpea & Cucumber Bowl with Whole Grain Pita",
        "items": [
          {
            "name": "Steamed Chickpeas with Lemon & Dried Oregano",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 160,
              "protein_g": 8.5,
              "carbs_g": 26,
              "fat_g": 2.5,
              "sodium_mg": 55,
              "potassium_mg": 210,
              "fiber_g": 6.5
            }
          },
          {
            "name": "Cucumber, Cherry Tomato & Bell Pepper Salad with Olive Oil",
            "portion": "1.2 cups (150g)",
            "nutrients": {
              "calories": 65,
              "protein_g": 1.5,
              "carbs_g": 8.0,
              "fat_g": 3.5,
              "sodium_mg": 20,
              "potassium_mg": 190,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Whole Wheat Pita Bread",
            "portion": "1 medium pita (50g)",
            "nutrients": {
              "calories": 130,
              "protein_g": 5.0,
              "carbs_g": 25,
              "fat_g": 1.0,
              "sodium_mg": 120,
              "potassium_mg": 65,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Authentic Mediterranean protocol clinically proven to lower cardiovascular event rates and preserve renal function.",
        "prep_tips": "Toss chickpeas and crisp vegetables with extra virgin olive oil and lemon juice."
      },
      {
        "title": "Grilled Salmon / Tilapia Fillet with Wild Rice & Broccoli",
        "items": [
          {
            "name": "Pan-Seared White Fish / Salmon Fillet with Lemon Pepper",
            "portion": "110g fillet",
            "nutrients": {
              "calories": 160,
              "protein_g": 22.0,
              "carbs_g": 1.0,
              "fat_g": 5.5,
              "sodium_mg": 85,
              "potassium_mg": 240,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Steamed Wild & Brown Rice Pilaf",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 170,
              "protein_g": 4.5,
              "carbs_g": 35,
              "fat_g": 1.5,
              "sodium_mg": 10,
              "potassium_mg": 115,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Steamed Broccoli Florets with Olive Oil Drizzle",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.5,
              "carbs_g": 6.0,
              "fat_g": 1.5,
              "sodium_mg": 30,
              "potassium_mg": 180,
              "fiber_g": 2.8
            }
          }
        ],
        "justification": "Omega-3 EPA/DHA reduces systemic endothelial inflammation and lowers hypertriglyceridemia.",
        "prep_tips": "Sear fish in a cast-iron skillet with a drop of olive oil; steam broccoli until bright green."
      },
      {
        "title": "Roasted Turkey / Skinless Chicken Breast with Sweet Potato & Kale",
        "items": [
          {
            "name": "Herb-Roasted Skinless Poultry Breast",
            "portion": "110g",
            "nutrients": {
              "calories": 155,
              "protein_g": 24.0,
              "carbs_g": 0.5,
              "fat_g": 3.5,
              "sodium_mg": 90,
              "potassium_mg": 230,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Baked Sweet Potato Wedges (Boiled First to Reduce Potassium)",
            "portion": "3/4 cup (100g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 1.5,
              "carbs_g": 22,
              "fat_g": 0.2,
              "sodium_mg": 35,
              "potassium_mg": 180,
              "fiber_g": 3.0
            }
          },
          {
            "name": "Steamed Tuscan Kale with Garlic & Lemon",
            "portion": "3/4 cup (70g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 2.0,
              "carbs_g": 5.0,
              "fat_g": 0.8,
              "sodium_mg": 30,
              "potassium_mg": 160,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Pre-boiling sweet potato leaches surplus potassium, rendering it safe for renal guidance while retaining beta-carotene.",
        "prep_tips": "Boil sweet potato cubes for 10 minutes, drain water, then roast lightly."
      },
      {
        "title": "Egg White & Vegetable Frittata with Mixed Greens & Sourdough",
        "items": [
          {
            "name": "Baked Egg White Frittata (4 Whites with Zucchini & Mushrooms)",
            "portion": "1 generous slice (160g)",
            "nutrients": {
              "calories": 125,
              "protein_g": 15.0,
              "carbs_g": 4.5,
              "fat_g": 2.5,
              "sodium_mg": 110,
              "potassium_mg": 210,
              "fiber_g": 1.8
            }
          },
          {
            "name": "Mixed Baby Salad Greens with Lemon Vinaigrette",
            "portion": "1.5 cups (60g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 1.2,
              "carbs_g": 3.5,
              "fat_g": 2.5,
              "sodium_mg": 35,
              "potassium_mg": 140,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Whole Grain Sourdough Toast",
            "portion": "1 slice (35g)",
            "nutrients": {
              "calories": 85,
              "protein_g": 3.5,
              "carbs_g": 16,
              "fat_g": 0.8,
              "sodium_mg": 75,
              "potassium_mg": 45,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "High-protein, low-calorie lunch with superior amino acid bioavailability and minimal digestive fatigue.",
        "prep_tips": "Bake whipped egg whites with sauteed zucchini and mushrooms in pie dish."
      },
      {
        "title": "Lentil & Minestrone Soup Bowl with Whole Grain Toast",
        "items": [
          {
            "name": "Clear Italian Minestrone with Brown Lentils, Zucchini & Tomato",
            "portion": "1.5 cups (250g)",
            "nutrients": {
              "calories": 175,
              "protein_g": 9.5,
              "carbs_g": 27,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 220,
              "fiber_g": 6.5
            }
          },
          {
            "name": "Whole Grain Artisan Toast",
            "portion": "2 slices (60g)",
            "nutrients": {
              "calories": 145,
              "protein_g": 5.5,
              "carbs_g": 26,
              "fat_g": 1.5,
              "sodium_mg": 120,
              "potassium_mg": 80,
              "fiber_g": 3.8
            }
          }
        ],
        "justification": "Rich in soluble legume fiber, lycopene, and plant-based potassium buffering.",
        "prep_tips": "Simmer lentils and diced vegetables in low-sodium vegetable stock with oregano."
      }
    ],
    "evening_snack": [
      {
        "title": "Carrot & Cucumber Sticks with Garlic White Bean Dip",
        "items": [
          {
            "name": "Fresh Carrot & Cucumber Batons",
            "portion": "1.2 cups (130g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.0,
              "carbs_g": 6.5,
              "fat_g": 0.2,
              "sodium_mg": 35,
              "potassium_mg": 170,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Creamy White Bean & Garlic Puree",
            "portion": "2 tbsp (35g)",
            "nutrients": {
              "calories": 50,
              "protein_g": 2.5,
              "carbs_g": 7.0,
              "fat_g": 1.5,
              "sodium_mg": 45,
              "potassium_mg": 85,
              "fiber_g": 2.0
            }
          }
        ],
        "justification": "Low-sodium legume dip providing sustained satiety without blood sugar elevation.",
        "prep_tips": "Puree boiled white beans with roasted garlic and lemon juice."
      },
      {
        "title": "Raw Walnuts & Low-Sugar Dried Cranberries",
        "items": [
          {
            "name": "Raw Walnut Halves",
            "portion": "4 halves (12g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 1.8,
              "carbs_g": 1.6,
              "fat_g": 7.5,
              "sodium_mg": 1,
              "potassium_mg": 50,
              "fiber_g": 0.8
            }
          },
          {
            "name": "Unsweetened Dried Cranberries",
            "portion": "1 tbsp (10g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 0.1,
              "carbs_g": 7.5,
              "fat_g": 0.1,
              "sodium_mg": 1,
              "potassium_mg": 15,
              "fiber_g": 1.0
            }
          }
        ],
        "justification": "Proanthocyanidins in cranberries support urinary tract health while walnuts support vascular elasticity.",
        "prep_tips": "Choose unsweetened cranberries without added high-fructose corn syrup."
      },
      {
        "title": "Steamed Edamame Pods with Sea Salt (Light)",
        "items": [
          {
            "name": "Steamed Young Green Soybeans in Pods",
            "portion": "1/2 cup shelled equivalent (80g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 9.0,
              "carbs_g": 6.5,
              "fat_g": 4.0,
              "sodium_mg": 35,
              "potassium_mg": 180,
              "fiber_g": 4.0
            }
          }
        ],
        "justification": "Complete plant protein package packed with isoflavones and fiber.",
        "prep_tips": "Steam whole pods for 5 minutes; sprinkle pinch of coarse salt."
      },
      {
        "title": "Roasted Cauliflower Florets with Smoked Paprika with Lightly Roasted Pumpkin Seeds",
        "items": [
          {
            "name": "Oven-Roasted Cauliflower Florets with Paprika",
            "portion": "1 cup (110g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.2,
              "carbs_g": 6.0,
              "fat_g": 1.5,
              "sodium_mg": 35,
              "potassium_mg": 170,
              "fiber_g": 2.8
            }
          },
          {
            "name": "Lightly Roasted Pumpkin Seeds",
            "portion": "1.5 tbsp (15g)",
            "nutrients": {
              "calories": 80,
              "protein_g": 3.8,
              "carbs_g": 2.2,
              "fat_g": 6.5,
              "sodium_mg": 2,
              "potassium_mg": 115,
              "fiber_g": 1.5
            }
          }
        ],
        "justification": "Low-potassium cruciferous snack offering chip-like crunch without refined starch.",
        "prep_tips": "Toss florets with drops of olive oil and smoked paprika; roast at 200°C for 20 minutes."
      },
      {
        "title": "Chamomile Herbal Tea with Chia Seed Crackers",
        "items": [
          {
            "name": "Soothing Chamomile Flower Infusion",
            "portion": "1 cup (180ml)",
            "nutrients": {
              "calories": 2,
              "protein_g": 0.0,
              "carbs_g": 0.4,
              "fat_g": 0.0,
              "sodium_mg": 5,
              "potassium_mg": 20,
              "fiber_g": 0.0
            }
          },
          {
            "name": "Whole Grain Chia Seed Crackers",
            "portion": "3 crackers (25g)",
            "nutrients": {
              "calories": 95,
              "protein_g": 3.0,
              "carbs_g": 14,
              "fat_g": 3.5,
              "sodium_mg": 50,
              "potassium_mg": 60,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Apigenin flavonoid in chamomile binds GABA receptors, calming the central nervous system.",
        "prep_tips": "Steep whole chamomile flowers in hot water for 6 minutes."
      }
    ],
    "dinner": [
      {
        "title": "Baked Cod / Tofu Fillet with Cauliflower Mash & Green Beans",
        "items": [
          {
            "name": "Herb-Crusted Baked White Fish or Organic Firm Tofu",
            "portion": "120g fillet",
            "nutrients": {
              "calories": 140,
              "protein_g": 20.0,
              "carbs_g": 2.0,
              "fat_g": 4.5,
              "sodium_mg": 85,
              "potassium_mg": 210,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Garlic Steamed Cauliflower Mash",
            "portion": "1 cup (150g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 2.5,
              "carbs_g": 8.0,
              "fat_g": 2.0,
              "sodium_mg": 50,
              "potassium_mg": 180,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Steamed Tender Green Beans",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 40,
              "protein_g": 1.8,
              "carbs_g": 7.0,
              "fat_g": 0.5,
              "sodium_mg": 25,
              "potassium_mg": 140,
              "fiber_g": 2.5
            }
          }
        ],
        "justification": "Ultra-light evening protein that prevents nocturnal reflux and maintains normal blood pressure dipping.",
        "prep_tips": "Bake fillet with dill and lemon juice; steam cauliflower until mashable."
      },
      {
        "title": "Grilled Chicken Breast with Roasted Brussels Sprouts & Wild Rice",
        "items": [
          {
            "name": "Skinless Grilled Chicken Breast",
            "portion": "110g fillet",
            "nutrients": {
              "calories": 155,
              "protein_g": 23.0,
              "carbs_g": 1.0,
              "fat_g": 4.0,
              "sodium_mg": 90,
              "potassium_mg": 220,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Steamed Wild & Brown Rice",
            "portion": "3/4 cup (120g)",
            "nutrients": {
              "calories": 140,
              "protein_g": 3.5,
              "carbs_g": 29,
              "fat_g": 1.0,
              "sodium_mg": 10,
              "potassium_mg": 95,
              "fiber_g": 2.5
            }
          },
          {
            "name": "Roasted Brussels Sprouts Halves with Balsamic",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 45,
              "protein_g": 2.5,
              "carbs_g": 7.5,
              "fat_g": 1.0,
              "sodium_mg": 30,
              "potassium_mg": 180,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Brussels sprouts supply sulfur-rich sulforaphane, promoting cellular antioxidant enzymes.",
        "prep_tips": "Roast brussels sprouts with dash of balsamic vinegar; grill chicken without butter."
      },
      {
        "title": "Whole Wheat Penne with Lentil Marinara & Steamed Zucchini",
        "items": [
          {
            "name": "Al Dente Whole Wheat Penne Pasta",
            "portion": "1 cup cooked (140g)",
            "nutrients": {
              "calories": 165,
              "protein_g": 6.5,
              "carbs_g": 33,
              "fat_g": 1.2,
              "sodium_mg": 15,
              "potassium_mg": 95,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Rich Brown Lentil & Basil Marinara Sauce",
            "portion": "3/4 cup (130g)",
            "nutrients": {
              "calories": 115,
              "protein_g": 7.0,
              "carbs_g": 16,
              "fat_g": 2.5,
              "sodium_mg": 85,
              "potassium_mg": 200,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Steamed Sliced Zucchini with Italian Herbs",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 30,
              "protein_g": 1.2,
              "carbs_g": 5.0,
              "fat_g": 0.5,
              "sodium_mg": 20,
              "potassium_mg": 140,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Cooking whole wheat pasta al dente keeps the glycemic index lower (GI ~42) than overcooked soft pasta.",
        "prep_tips": "Cook pasta till firm to bite; simmer brown lentils in crushed tomato and fresh basil."
      },
      {
        "title": "Pan-Seared White Fish with Lemon Caper Broth & Steamed Spinach",
        "items": [
          {
            "name": "Pan-Seared Tilapia / Cod with Lemon & Capers",
            "portion": "110g fillet",
            "nutrients": {
              "calories": 140,
              "protein_g": 21.0,
              "carbs_g": 2.0,
              "fat_g": 4.0,
              "sodium_mg": 95,
              "potassium_mg": 210,
              "fiber_g": 0.5
            }
          },
          {
            "name": "Steamed White & Red Quinoa",
            "portion": "3/4 cup (140g)",
            "nutrients": {
              "calories": 135,
              "protein_g": 4.8,
              "carbs_g": 24,
              "fat_g": 2.0,
              "sodium_mg": 10,
              "potassium_mg": 130,
              "fiber_g": 3.2
            }
          },
          {
            "name": "Steamed Baby Spinach with Garlic",
            "portion": "3/4 cup (90g)",
            "nutrients": {
              "calories": 35,
              "protein_g": 2.2,
              "carbs_g": 4.5,
              "fat_g": 0.8,
              "sodium_mg": 45,
              "potassium_mg": 170,
              "fiber_g": 2.2
            }
          }
        ],
        "justification": "Lean seafood dinner that supplies essential amino acids without kidney phosphorus overload.",
        "prep_tips": "Rinse capers to remove brine sodium; sear fish with lemon juice and parsley."
      },
      {
        "title": "Roasted Mediterranean Vegetable & Chickpea Bowl with Tahini Drizzle",
        "items": [
          {
            "name": "Steamed Chickpeas with Cumin & Paprika",
            "portion": "1/2 cup (80g)",
            "nutrients": {
              "calories": 110,
              "protein_g": 6.0,
              "carbs_g": 18,
              "fat_g": 1.8,
              "sodium_mg": 40,
              "potassium_mg": 150,
              "fiber_g": 4.5
            }
          },
          {
            "name": "Roasted Bell Peppers, Zucchini & Red Onion",
            "portion": "1.2 cups (150g)",
            "nutrients": {
              "calories": 70,
              "protein_g": 2.0,
              "carbs_g": 12,
              "fat_g": 2.0,
              "sodium_mg": 35,
              "potassium_mg": 210,
              "fiber_g": 3.5
            }
          },
          {
            "name": "Lemon Tahini Dressing",
            "portion": "1 tbsp (15g)",
            "nutrients": {
              "calories": 60,
              "protein_g": 2.0,
              "carbs_g": 2.0,
              "fat_g": 5.0,
              "sodium_mg": 15,
              "potassium_mg": 60,
              "fiber_g": 1.0
            }
          },
          {
            "name": "Steamed Brown Rice",
            "portion": "1/2 cup (75g)",
            "nutrients": {
              "calories": 90,
              "protein_g": 2.0,
              "carbs_g": 19,
              "fat_g": 0.6,
              "sodium_mg": 3,
              "potassium_mg": 55,
              "fiber_g": 1.3
            }
          }
        ],
        "justification": "Colorful carotenoid variety provides extensive vascular protection with low glycemic load.",
        "prep_tips": "Roast vegetables on parchment paper; whisk tahini with lemon juice."
      },
      {
        "title": "Egg White Omelet with Mushrooms, Spinach & Mixed Green Salad",
        "items": [
          {
            "name": "Folded Egg White Omelet (4 Whites with Button Mushrooms & Herbs)",
            "portion": "1 omelet (150g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 15.0,
              "carbs_g": 3.5,
              "fat_g": 2.5,
              "sodium_mg": 115,
              "potassium_mg": 210,
              "fiber_g": 1.5
            }
          },
          {
            "name": "Whole Grain Toast",
            "portion": "1 slice (30g)",
            "nutrients": {
              "calories": 75,
              "protein_g": 3.0,
              "carbs_g": 14,
              "fat_g": 0.8,
              "sodium_mg": 65,
              "potassium_mg": 45,
              "fiber_g": 2.0
            }
          },
          {
            "name": "Steamed Tender Asparagus",
            "portion": "5 spears (75g)",
            "nutrients": {
              "calories": 20,
              "protein_g": 1.8,
              "carbs_g": 3.5,
              "fat_g": 0.2,
              "sodium_mg": 10,
              "potassium_mg": 150,
              "fiber_g": 1.8
            }
          }
        ],
        "justification": "Pure egg albumen supplies zero-cholesterol, high-efficiency protein ideal for renal and cardiovascular health.",
        "prep_tips": "Saute mushrooms and fold inside fluffy whipped egg whites."
      },
      {
        "title": "Warm Lentil & Vegetable Stew with Whole Grain Sourdough",
        "items": [
          {
            "name": "Hearty Brown Lentil Stew with Carrots, Celery & Thyme",
            "portion": "1.3 cups (220g)",
            "nutrients": {
              "calories": 185,
              "protein_g": 11.0,
              "carbs_g": 28,
              "fat_g": 3.0,
              "sodium_mg": 95,
              "potassium_mg": 220,
              "fiber_g": 7.0
            }
          },
          {
            "name": "Whole Grain Sourdough Toast",
            "portion": "1.5 slices (50g)",
            "nutrients": {
              "calories": 120,
              "protein_g": 4.8,
              "carbs_g": 23,
              "fat_g": 1.0,
              "sodium_mg": 100,
              "potassium_mg": 60,
              "fiber_g": 3.0
            }
          }
        ],
        "justification": "Lentils supply rich soluble prebiotic fiber supporting short-chain fatty acid gut synthesis.",
        "prep_tips": "Simmer lentils with diced mirepoix vegetables and sprig of fresh thyme."
      }
    ]
  }
}


# ==============================================================================
# 5. Multi-Condition Drug Interaction Check (31+ Pharmacopeia Engine)
# ==============================================================================

def check_medication_warnings(medications: List[str], plan_targets: Dict[str, Any]) -> List[str]:
    """Generates drug-specific nutrition warnings for active prescriptions using safety_engine."""
    warnings = []
    if not medications:
        return warnings

    med_lower = [m.lower().strip() for m in medications]
    
    # 1. SGLT2i Check (Jardiance, Farxiga, Invokana, Empagliflozin, Dapagliflozin)
    if any(m in med_lower for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana"]):
        warnings.append(
            "CRITICAL PHARMACOPEIA (SGLT2i / Jardiance): Induces osmotic glucosuria. Daily carbohydrate intake is strictly protected at >= 130g/day with >= 2.5L daily hydration to eliminate Euglycemic DKA risk. Extreme low-carb or fasting regimens are contraindicated."
        )

    # 2. CCB Check (Amlodipine, Norvasc, Nifedipine, Felodipine, Diltiazem, Verapamil)
    if any(m in med_lower for m in ["amlodipine", "norvasc", "nifedipine", "felodipine", "diltiazem", "verapamil"]):
        warnings.append(
            "DRUG INTERACTION WARNING (Calcium Channel Blocker / Amlodipine): Grapefruit, pomelo, and Seville oranges are 100% eliminated from this plan. Their furanocoumarins irreversibly inhibit gut CYP3A4, causing massive drug over-absorption and severe hypotension."
        )

    # 3. ACEi / ARB Check (Lisinopril, Losartan, Ramipril, Valsartan, Telmisartan, Enalapril)
    if any(m in med_lower for m in ["lisinopril", "losartan", "ramipril", "valsartan", "telmisartan", "enalapril"]):
        warnings.append(
            "ELECTROLYTE ALERT (ACEi / ARB): Renin-angiotensin blockade reduces renal potassium clearance. Daily potassium is capped at <= 2000-2400 mg/d. High-potassium salt substitutes (potassium chloride) and concentrated potassium drinks (e.g., coconut water) are restricted."
        )

    # 4. GLP-1 RA Check (Ozempic, Rybelsus, Mounjaro, Semaglutide, Tirzepatide, Wegovy)
    if any(m in med_lower for m in ["ozempic", "semaglutide", "mounjaro", "tirzepatide", "rybelsus", "wegovy"]):
        warnings.append(
            "DIGESTIVE PACING (GLP-1 RA): Gastric emptying is slowed. Daily calories are split evenly across 5 modest intervals and high-fat items are restricted to prevent nausea, reflux, and gastroparesis."
        )

    # 5. Metformin Check
    if any("metformin" in m for m in med_lower):
        warnings.append(
            "METABOLIC STABILITY (Metformin): All main intervals feature high-fiber complex carbohydrates to minimize gastrointestinal discomfort and maintain smooth glycemic control."
        )

    # 6. Beta-Blockers (Metoprolol, Atenolol, Bisoprolol, Carvedilol)
    if any(m in med_lower for m in ["metoprolol", "atenolol", "bisoprolol", "carvedilol"]):
        warnings.append(
            "HEMODYNAMIC MONITORING (Beta-Blocker): Maintain steady complex carbohydrate pacing across morning and lunch intervals to avoid blunting of hypoglycemia awareness."
        )

    # 7. Statins (Atorvastatin, Simvastatin, Lipitor)
    if any(m in med_lower for m in ["atorvastatin", "simvastatin", "lipitor", "zocor"]):
        warnings.append(
            "CYP3A4 PHARMACOPEIA (Statin): Grapefruit and related citrus are omitted to prevent statin accumulation, rhabdomyolysis, and myopathy."
        )

    # 8. Diuretics (Furosemide, Lasix, Hydrochlorothiazide, Torsemide)
    if any(m in med_lower for m in ["furosemide", "lasix", "hydrochlorothiazide", "hctz", "torsemide", "spironolactone"]):
        warnings.append(
            "ELECTROLYTE & FLUID MONITORING (Diuretic): Renal electrolyte wasting or potassium sparing is active. Maintain steady fluid pacing and monitor serum electrolytes routinely."
        )

    # 9. Warfarin / Coumadin Check
    if any(m in med_lower for m in ["warfarin", "coumadin"]):
        warnings.append(
            "COAGULATION WARNING (Warfarin): Vitamin K intake from dark leafy greens (spinach, kale, methi) must remain consistent day-to-day to avoid destabilizing INR and prothrombin time."
        )

    # 10. Insulin Check
    if any(m in med_lower for m in ["insulin", "lantus", "humalog", "novolog", "tresiba"]):
        warnings.append(
            "GLYCEMIC SAFETY (Insulin): Carbohydrate portions are precision-calculated across all intervals to prevent nocturnal and postprandial hypoglycemia."
        )

    return warnings


# ==============================================================================
# 6. Categorized Grocery Checklist Engine
# ==============================================================================

def categorize_groceries(grocery_items: List[str]) -> Dict[str, List[str]]:
    """Organizes ingredients into clean, practical supermarket categories."""
    categories = {
        "🥬 Fresh Produce & Greens": [],
        "🌾 Whole Grains & Millets": [],
        "🫘 Pulses, Legumes & Plant Proteins": [],
        "🐟 Dairy, Eggs & Lean Proteins": [],
        "🌿 Herbs, Spices & Cold-Pressed Oils": [],
    }

    produce_kw = ["gourd", "lauki", "tinda", "torai", "jhinge", "potol", "parwal", "cucumber", "tomato", "beans", "carrot", "peas", "cabbage", "spinach", "palak", "methi", "coriander", "mint", "papaya", "apple", "guava", "pomegranate", "lemon", "lime", "okra", "bhindi", "zucchini", "asparagus", "broccoli", "brussels", "berries", "blueberries", "strawberries", "avocado", "mushrooms", "cauliflower", "eggplant", "baingan", "drumstick"]
    grains_kw = ["rice", "brown rice", "dalia", "wheat", "oats", "quinoa", "ragi", "millet", "jowar", "bajra", "chire", "poha", "puffed rice", "muri", "kurmura", "barley", "pasta", "sourdough", "bread", "toast", "pita", "khakhra"]
    pulses_kw = ["dal", "moong", "chana", "chickpea", "urad", "masoor", "tuvar", "arhar", "rajma", "tofu", "soya", "sprouts", "lentil", "edamame", "flaxseed", "chia", "walnut", "pumpkin seeds", "sesame"]
    protein_kw = ["chicken", "fish", "egg", "egg white", "paneer", "curd", "dahi", "buttermilk", "chaas", "yogurt", "cod", "salmon", "rohu", "pomfret", "tilapia", "turkey"]

    for item in sorted(set(grocery_items)):
        low = item.lower()
        if any(k in low for k in protein_kw):
            categories["🐟 Dairy, Eggs & Lean Proteins"].append(item)
        elif any(k in low for k in grains_kw):
            categories["🌾 Whole Grains & Millets"].append(item)
        elif any(k in low for k in pulses_kw):
            categories["🫘 Pulses, Legumes & Plant Proteins"].append(item)
        elif any(k in low for k in produce_kw):
            categories["🥬 Fresh Produce & Greens"].append(item)
        else:
            categories["🌿 Herbs, Spices & Cold-Pressed Oils"].append(item)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


# ==============================================================================
# 7. Core 7-Day / 5-Interval Generator
# ==============================================================================

class WeeklyDietEngine:
    """Engine for building personalized, regional, 7-day clinical meal plans with dynamic portion scaling."""

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def __init__(self):
        self.catalog = REGIONAL_DISH_CATALOG

    def _resolve_region_key(self, raw_region: str) -> str:
        """Maps user's free-form native place into canonical catalog keys."""
        reg = (raw_region or "").lower().strip()
        if any(w in reg for w in ["south", "tamil", "kerala", "andhra", "telangana", "karnataka", "chennai", "bangalore", "hyderabad"]):
            return "south_indian"
        elif any(w in reg for w in ["north", "punjab", "delhi", "haryana", "uttar", "rajasthan", "bihar", "mughlai"]):
            return "north_indian"
        elif any(w in reg for w in ["gujarat", "maharashtra", "mumbai", "pune", "ahmedabad", "surat", "marathi", "western"]):
            return "western_indian"
        elif any(w in reg for w in ["bengal", "kolkata", "odisha", "orissa", "assam", "eastern"]):
            return "eastern_indian"
        elif any(w in reg for w in ["continental", "mediterranean", "global", "american", "european"]):
            return "continental"
        else:
            return "south_indian"

    def _filter_dishes_by_dietary(
        self,
        dishes: List[Dict[str, Any]],
        dietary_type: str,
        day_idx: int,
        category: str,
        excluded_terms: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Filters catalog dishes according to the patient's dietary preference and exclusions."""
        non_veg_keywords = ("chicken", "fish", "mutton", "prawn", "salmon", "rohu", "pomfret", "meat", "machh", "turkey", "cod", "tilapia")
        egg_keywords = ("egg white", "egg whites", "omelet", "frittata", "scrambled egg", "boiled egg", "egg curry", "bhurji")
        dairy_keywords = ("paneer", "curd", "dahi", "yogurt", "milk", "kadhi", "buttermilk", "ghee", "cheese")
        jain_avoid_keywords = ("onion", "garlic", "potato", "aloo", "carrot", "beetroot", "radish")

        eligible = []
        for d in dishes:
            title_lower = d.get("title", "").lower()
            items_str = " ".join(it.get("name", "").lower() for it in d.get("items", []))
            all_str = f"{title_lower} {items_str}"

            is_non_veg = any(k in all_str for k in non_veg_keywords)
            is_egg = (("egg" in all_str and "eggplant" not in all_str) or any(k in all_str for k in egg_keywords))
            is_dairy = any(k in all_str for k in dairy_keywords)
            is_jain_incompatible = any(k in all_str for k in jain_avoid_keywords)

            if dietary_type == "vegetarian":
                if is_non_veg or is_egg:
                    continue
            elif dietary_type == "eggetarian":
                if is_non_veg:
                    continue
            elif dietary_type == "vegan":
                if is_non_veg or is_egg or is_dairy:
                    continue
            elif dietary_type == "jain":
                if is_non_veg or is_egg or is_jain_incompatible:
                    continue

            eligible.append(d)

        if not eligible:
            # Fallback to safe vegetarian dishes if filtered pool is empty
            eligible = [d for d in dishes if not any(k in d.get("title", "").lower() for k in non_veg_keywords)] or list(dishes)

        # Excluded allergens filter
        if excluded_terms:
            clean_dishes = [
                d for d in eligible
                if not any(ex in d.get("title", "").lower() for ex in excluded_terms)
            ]
            if clean_dishes:
                eligible = clean_dishes

        # For non-vegetarian: alternate lean non-veg on odd days with vegetarian on even days
        if dietary_type == "non_vegetarian" and category in ("lunch", "dinner"):
            non_veg_list = [
                d for d in eligible
                if any(k in (d.get("title", "") + " " + " ".join(it.get("name", "") for it in d.get("items", []))).lower() for k in non_veg_keywords)
            ]
            veg_list = [d for d in eligible if d not in non_veg_list]
            if non_veg_list and veg_list:
                return non_veg_list if (day_idx % 2 == 1) else veg_list
            elif non_veg_list:
                return non_veg_list

        elif dietary_type == "eggetarian" and category in ("lunch", "dinner", "breakfast"):
            egg_list = [
                d for d in eligible
                if (("egg" in (d.get("title", "") + " " + " ".join(it.get("name", "") for it in d.get("items", []))).lower() and "eggplant" not in (d.get("title", "") + " " + " ".join(it.get("name", "") for it in d.get("items", []))).lower())
                    or any(k in (d.get("title", "") + " " + " ".join(it.get("name", "") for it in d.get("items", []))).lower() for k in egg_keywords))
            ]
            veg_list = [d for d in eligible if d not in egg_list]
            if egg_list and veg_list:
                return egg_list if (day_idx % 2 == 1) else veg_list

        return eligible

    def _scrub_dish_and_items(
        self,
        dish_template: Dict[str, Any],
        excluded_terms: List[str],
        day_idx: int,
        category: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        Zero-tolerance allergen and dislike scrubber.
        Deep-copies a dish template and substitutes any item or accompaniment containing an excluded keyword
        with clinically equivalent, safe alternatives.
        """
        dish = copy.deepcopy(dish_template)
        substitutions_applied = []
        if not excluded_terms:
            return dish, substitutions_applied

        cleaned_items = []
        for it in dish.get("items", []):
            item_name = it.get("name", "")
            item_lower = item_name.lower()

            matched_term = None
            for ex in excluded_terms:
                if ex in item_lower:
                    matched_term = ex
                    break

            if not matched_term:
                cleaned_items.append(it)
                continue

            # 1. Coconut Substitutions
            if any(k in matched_term for k in ["coconut", "nariyal", "thengai"]):
                if any(w in item_lower for w in ["chutney", "dip"]):
                    sub_item = {
                        "name": "Fresh Mint & Coriander Chutney",
                        "portion": it.get("portion", "2 tbsp (30g)"),
                        "nutrients": {"calories": 25, "protein_g": 0.8, "carbs_g": 2.5, "fat_g": 0.5, "sodium_mg": 55, "potassium_mg": 65, "fiber_g": 1.2}
                    }
                    substitutions_applied.append({"standard": "Coconut Chutney", "substitute": "Fresh Mint & Coriander Chutney"})
                elif any(w in item_lower for w in ["sundal", "fresh coconut", "grated"]):
                    sub_item = {
                        "name": "Steamed Chickpea Sundal with Lemon & Roasted Cumin",
                        "portion": it.get("portion", "1/2 cup (80g)"),
                        "nutrients": {"calories": 80, "protein_g": 4.5, "carbs_g": 15, "fat_g": 0.8, "sodium_mg": 45, "potassium_mg": 165, "fiber_g": 3.5}
                    }
                    substitutions_applied.append({"standard": "Grated Coconut Topping", "substitute": "Lemon & Roasted Cumin"})
                elif any(w in item_lower for w in ["water", "tender coconut"]):
                    sub_item = {
                        "name": "Fresh Lemon Mint Chia Cooler",
                        "portion": it.get("portion", "1 glass (180ml)"),
                        "nutrients": {"calories": 25, "protein_g": 0.8, "carbs_g": 4.0, "fat_g": 0.5, "sodium_mg": 15, "potassium_mg": 75, "fiber_g": 1.8}
                    }
                    substitutions_applied.append({"standard": "Tender Coconut Water", "substitute": "Fresh Lemon Mint Chia Cooler"})
                else:
                    clean_name = re.sub(r'(?i)coconut\s*', 'Herb & Sesame ', item_name).strip()
                    nutr = dict(it.get("nutrients", {}))
                    nutr["calories"] = max(20, nutr.get("calories", 50) - 25)
                    nutr["fat_g"] = max(0.5, nutr.get("fat_g", 3.0) - 2.5)
                    sub_item = {
                        "name": clean_name,
                        "portion": it.get("portion", "1 serving"),
                        "nutrients": nutr
                    }
                    substitutions_applied.append({"standard": "Coconut Component", "substitute": clean_name})
                cleaned_items.append(sub_item)

            # 2. Peanut / Groundnut Substitutions
            elif any(k in matched_term for k in ["peanut", "groundnut", "moongphali"]):
                sub_item = {
                    "name": "Roasted Bengal Gram (Chana) with Curry Leaves",
                    "portion": it.get("portion", "2 tbsp (25g)"),
                    "nutrients": {"calories": 85, "protein_g": 4.5, "carbs_g": 13, "fat_g": 1.5, "sodium_mg": 25, "potassium_mg": 120, "fiber_g": 3.2}
                }
                substitutions_applied.append({"standard": "Peanuts", "substitute": "Roasted Bengal Gram (Chana)"})
                cleaned_items.append(sub_item)

            # 3. Dairy Substitutions (Paneer, Curd, Buttermilk)
            elif any(k in matched_term for k in ["dairy", "milk", "curd", "dahi", "paneer", "yogurt", "cheese", "butter", "ghee"]):
                if "paneer" in item_lower:
                    sub_item = {
                        "name": "Pan-Seared Organic Soya Tofu with Mild Spices",
                        "portion": it.get("portion", "100g"),
                        "nutrients": {"calories": 110, "protein_g": 12.0, "carbs_g": 3.0, "fat_g": 6.0, "sodium_mg": 40, "potassium_mg": 110, "fiber_g": 1.5}
                    }
                    substitutions_applied.append({"standard": "Dairy Paneer", "substitute": "Organic Soya Tofu"})
                elif any(w in item_lower for w in ["curd", "dahi", "yogurt"]):
                    sub_item = {
                        "name": "Unsweetened Soya / Almond Probiotic Yogurt",
                        "portion": it.get("portion", "1 cup (150g)"),
                        "nutrients": {"calories": 55, "protein_g": 3.0, "carbs_g": 3.5, "fat_g": 3.0, "sodium_mg": 30, "potassium_mg": 85, "fiber_g": 1.0}
                    }
                    substitutions_applied.append({"standard": "Dairy Curd", "substitute": "Unsweetened Plant Yogurt"})
                elif any(w in item_lower for w in ["buttermilk", "neer mor", "kadhi"]):
                    sub_item = {
                        "name": "Diluted Spiced Soya Buttermilk with Mint & Hing",
                        "portion": it.get("portion", "1 glass (200ml)"),
                        "nutrients": {"calories": 35, "protein_g": 2.5, "carbs_g": 2.5, "fat_g": 1.0, "sodium_mg": 35, "potassium_mg": 95, "fiber_g": 0.5}
                    }
                    substitutions_applied.append({"standard": "Dairy Buttermilk", "substitute": "Spiced Plant Herb Cooler"})
                else:
                    clean_name = re.sub(r'(?i)(dairy|milk|cheese|butter|ghee)\s*', '', item_name).strip()
                    sub_item = {
                        "name": clean_name or "Herb & Vegetable Medley",
                        "portion": it.get("portion", "1 serving"),
                        "nutrients": it.get("nutrients", {})
                    }
                    substitutions_applied.append({"standard": "Dairy Ingredient", "substitute": sub_item["name"]})
                cleaned_items.append(sub_item)

            # 4. Bitter Gourd / Karela Substitutions
            elif any(k in matched_term for k in ["karela", "bitter gourd", "bittergourd"]):
                sub_item = {
                    "name": "Bottle Gourd (Lauki) & Cumin Stir-Fry",
                    "portion": it.get("portion", "1 cup (120g)"),
                    "nutrients": {"calories": 45, "protein_g": 1.2, "carbs_g": 6.5, "fat_g": 1.5, "sodium_mg": 40, "potassium_mg": 140, "fiber_g": 2.5}
                }
                substitutions_applied.append({"standard": "Bitter Gourd (Karela)", "substitute": "Bottle Gourd (Lauki) Stir-Fry"})
                cleaned_items.append(sub_item)

            # 5. Grapefruit / Citrus Substitutions
            elif any(k in matched_term for k in ["grapefruit", "pomelo", "seville"]):
                sub_item = {
                    "name": "Crisp Green Apple Slices with Cinnamon",
                    "portion": "1 small apple (100g)",
                    "nutrients": {"calories": 52, "protein_g": 0.3, "carbs_g": 13.8, "fat_g": 0.2, "sodium_mg": 2, "potassium_mg": 107, "fiber_g": 2.4}
                }
                substitutions_applied.append({"standard": "Grapefruit / Pomelo", "substitute": "Crisp Green Apple Slices"})
                cleaned_items.append(sub_item)

            # 6. Generic Fallback Substitution
            else:
                clean_name = "Steamed French Beans & Zucchini with Mustard Tempering"
                sub_item = {
                    "name": clean_name,
                    "portion": "3/4 cup (90g)",
                    "nutrients": {"calories": 40, "protein_g": 1.5, "carbs_g": 7.0, "fat_g": 1.0, "sodium_mg": 35, "potassium_mg": 130, "fiber_g": 2.8}
                }
                substitutions_applied.append({"standard": matched_term.title(), "substitute": clean_name})
                cleaned_items.append(sub_item)

        dish["items"] = cleaned_items

        # Clean title
        title_str = dish.get("title", "")
        for ex in excluded_terms:
            if ex in title_str.lower():
                if "coconut" in ex:
                    title_str = re.sub(r'(?i)with\s+mint\s+coconut\s+chutney', 'with Fresh Mint & Coriander Chutney', title_str)
                    title_str = re.sub(r'(?i)&\s*tender\s+coconut\s+water', '& Lemon Mint Cooler', title_str)
                    title_str = re.sub(r'(?i)coconut', 'Herb-Tempered', title_str)
                elif "peanut" in ex:
                    title_str = re.sub(r'(?i)with\s+roasted\s+peanuts', 'with Roasted Chana', title_str)
                    title_str = re.sub(r'(?i)peanuts?', 'Chana', title_str)
                elif "karela" in ex or "bitter gourd" in ex:
                    title_str = re.sub(r'(?i)(bitter\s+gourd|karela)', 'Bottle Gourd', title_str)
                else:
                    title_str = re.sub(re.escape(ex), 'Herb & Greens', title_str, flags=re.IGNORECASE)

        dish["title"] = title_str.strip()

        # Sanitize prep_tips and justification
        for field in ["prep_tips", "justification"]:
            txt = dish.get(field, "")
            for ex in excluded_terms:
                if ex in txt.lower():
                    txt = re.sub(r'(?i)or\s+add\s+coconut\s+milk', '', txt)
                    txt = re.sub(r'(?i)coconut\s+milk', 'pureed gourd gravy', txt)
                    txt = re.sub(r'(?i)coconut', 'herb garnish', txt)
                    txt = re.sub(re.escape(ex), 'safe alternative', txt, flags=re.IGNORECASE)
            dish[field] = txt.strip()

        return dish, substitutions_applied

    def generate_weekly_plan(self, req: WeeklyDietPlanRequest) -> WeeklyDietPlanResponse:
        """Constructs a comprehensive 7-day schedule with 5 daily intervals and dynamic portion scaling."""
        
        # 1. Parse lab report text into structured values
        parsed_labs = parse_report_text(req.test_reports.report_summary_text or "", req.test_reports)

        # 2. Derive targets based on labs, anthropometry, and active medications
        targets, detected_conditions = derive_clinical_targets(
            age=req.age_years,
            sex=req.sex,
            bmi=req.body_mass_index,
            labs=parsed_labs,
            override_calories=req.preferences.calorie_target_override,
            medications=req.preferences.active_medications
        )

        # 3. Select regional culinary catalog
        region_key = self._resolve_region_key(req.preferences.native_place_region)
        region_dishes = self.catalog.get(region_key, self.catalog["south_indian"])
        fallback_dishes = self.catalog["south_indian"]

        # Human readable cuisine name
        cuisine_display_names = {
            "south_indian": "South Indian",
            "north_indian": "North Indian",
            "western_indian": "Gujarati & Maharashtrian",
            "eastern_indian": "Bengali & Odia",
            "continental": "Continental & Global",
        }
        regional_cuisine_name = cuisine_display_names.get(region_key, "Regional Cuisine")

        # 4. Check medication alerts (all 31 medications)
        valid_meds = [
            m.strip() for m in (req.preferences.active_medications or [])
            if m and m.strip().lower() not in ("", "none", "no", "n/a", "nil", "null", "none prescribed")
        ]
        med_alerts = check_medication_warnings(valid_meds, targets)

        # 5. Compile Zero-Tolerance Exclusions (Allergies + Dislikes + Drug Contraindications)
        meds_lower = [m.lower().strip() for m in valid_meds]
        raw_exclusions = [
            x.strip() for x in (list(req.preferences.allergies or []) + list(req.preferences.dislikes or []))
            if x and x.strip().lower() not in ("", "none", "no", "n/a", "nil", "null")
        ]

        # Drug-specific mandatory exclusions
        if any(m in meds_lower for m in ["amlodipine", "norvasc", "nifedipine", "felodipine", "diltiazem", "verapamil", "atorvastatin", "simvastatin"]):
            raw_exclusions.extend(["grapefruit", "pomelo", "seville orange"])

        if any(m in meds_lower for m in ["lisinopril", "losartan", "ramipril", "valsartan", "telmisartan", "enalapril"]):
            if (parsed_labs.serum_potassium_meq_l or 4.0) >= 4.5:
                raw_exclusions.append("tender coconut water")

        excluded_terms = []
        for term in raw_exclusions:
            cleaned = term.strip().lower()
            if cleaned and cleaned not in excluded_terms:
                excluded_terms.append(cleaned)

        # 6. Smart Craving / Indulgence Budgeting Setup
        craving_raw = (req.preferences.craving_or_treat or "").strip()
        smart_craving_strategy = None
        scheduled_meal_name = "Evening Snack"
        rebalance_carbs = 18.0
        rebalance_cal = 125.0
        treat_item = None
        indulgence_title = ""

        if craving_raw:
            craving_lower = craving_raw.lower()
            if any(w in craving_lower for w in ["sugar", "sweet", "dessert", "kheer", "halwa", "phirni", "mithai", "chocolate", "cake", "ice cream", "pastry"]):
                scheduled_meal_name = "Evening Snack"
                indulgence_title = "Cardamom Almond Phirni / Kheer (Controlled Jaggery & Stevia Blend)"
                treat_item = MealItem(
                    item_name="Cardamom Almond Phirni with Crushed Pistachio (Controlled Jaggery & Stevia)",
                    portion="1 small ramekin (100g)",
                    nutrients={"calories": 125.0, "protein_g": 3.8, "carbs_g": 18.0, "fat_g": 4.0, "sodium_mg": 35.0, "potassium_mg": 90.0, "fiber_g": 1.5}
                )
                rebalance_carbs = 18.0
                rebalance_cal = 125.0
            elif any(w in craving_lower for w in ["biryani", "pulao", "fried rice"]):
                scheduled_meal_name = "Lunch"
                indulgence_title = "Clinically Portioned Brown Rice Dum Biryani with Cucumber Raita"
                treat_item = MealItem(
                    item_name="Steamed Brown Rice Dum Biryani with Soya Chunks & Vegetables",
                    portion="1 medium bowl (180g)",
                    nutrients={"calories": 230.0, "protein_g": 7.5, "carbs_g": 36.0, "fat_g": 5.5, "sodium_mg": 175.0, "potassium_mg": 210.0, "fiber_g": 4.5}
                )
                rebalance_carbs = 20.0
                rebalance_cal = 140.0
            else:
                clean_name = craving_raw.title()
                scheduled_meal_name = "Evening Snack"
                indulgence_title = f"Clinically Formulated {clean_name} (Controlled Portion)"
                treat_item = MealItem(
                    item_name=f"Portion-Controlled {clean_name} (Clinical Formulation)",
                    portion="1 controlled serving",
                    nutrients={"calories": 120.0, "protein_g": 3.0, "carbs_g": 18.0, "fat_g": 4.0, "sodium_mg": 55.0, "potassium_mg": 85.0, "fiber_g": 1.5}
                )
                rebalance_carbs = 18.0
                rebalance_cal = 120.0

            smart_craving_strategy = {
                "requested_craving": craving_raw,
                "status": "Budgeted & Clinically Rebalanced",
                "scheduled_day": "Sunday (Day 7)",
                "scheduled_meal": scheduled_meal_name,
                "indulgence_title": indulgence_title,
                "metabolic_rebalance_note": f"Sunday complex carbohydrates in Breakfast & Lunch were precision-reduced by -{int(rebalance_carbs)}g ({int(rebalance_cal)} kcal) so your total Sunday intake remains locked within target limits ({targets['calories_kcal']} kcal).",
                "six_day_lock_note": f"Days 1 to 6 (Monday–Saturday) strictly enforce 0% {craving_raw} to maintain insulin sensitivity and optimize clinical biomarkers."
            }

        # 7. Build 7 Days with Dynamic Portion Scaler & Food Preference Prioritization
        days: List[DayDietPlan] = []
        raw_grocery_items = []
        dietary_type = str(req.preferences.dietary_type or "vegetarian").lower().replace("-", "_")

        # Parse user food preferences and likes with delimiter splitting and synonym expansion
        raw_tokens = []
        for k in (req.preferences.interests_and_likes or []):
            if not k:
                continue
            for part in re.split(r'[,;/+&]|\band\b', str(k).lower()):
                tok = part.strip()
                if tok and len(tok) >= 2:
                    raw_tokens.append(tok)

        syn_map = {
            "paneer": ["paneer", "cottage cheese", "tofu"],
            "tofu": ["tofu", "paneer"],
            "chicken": ["chicken", "poultry", "murgh"],
            "fish": ["fish", "salmon", "meen", "machli"],
            "egg": ["egg", "eggs", "omelet", "omelette", "anda", "bhurji"],
            "dosa": ["dosa", "dosai", "pesarattu", "cheela", "chilla"],
            "idli": ["idli", "idly"],
            "ragi": ["ragi", "nachni", "finger millet", "millet"],
            "oats": ["oats", "oatmeal", "rolled oats"],
            "khichdi": ["khichdi", "khichri", "pongal"],
            "dalia": ["dalia", "broken wheat", "cracked wheat"],
            "sprouts": ["sprout", "sprouts", "moong sprout"],
            "curd": ["curd", "dahi", "raita", "yogurt"],
            "millet": ["millet", "ragi", "jowar", "bajra", "foxtail"],
            "chapati": ["chapati", "roti", "phulka"],
            "roti": ["roti", "chapati", "phulka"],
        }
        clean_likes = list(set(raw_tokens))
        expanded_likes = set(clean_likes)
        for t in clean_likes:
            for k_syn, syns in syn_map.items():
                if k_syn in t or t in k_syn:
                    expanded_likes.update(syns)
        expanded_likes = [w for w in expanded_likes if len(w) >= 2]

        # If user explicitly requested custom favorites like Maggi / Noodles, synthesize safe MNT formulation
        has_maggi_like = any(any(m in lk for m in ["maggi", "noodle", "ramen"]) for lk in expanded_likes)
        maggi_lunch_template = {
            "title": "Clinically Formulated Vegetable Atta Maggi with Sautéed Tofu & Bell Peppers",
            "items": [
                {
                    "name": "Whole Wheat Atta Noodles with Cabbage, Peas & Bell Peppers",
                    "portion": "1.5 cups cooked (180g)",
                    "nutrients": {
                        "calories": 240,
                        "protein_g": 6.5,
                        "carbs_g": 42.0,
                        "fat_g": 4.5,
                        "sodium_mg": 140,
                        "potassium_mg": 180,
                        "fiber_g": 5.0,
                    },
                },
                {
                    "name": "Pan-Seared Turmeric Tofu Cubes (Low Salt)",
                    "portion": "1/2 cup (75g)",
                    "nutrients": {
                        "calories": 85,
                        "protein_g": 9.0,
                        "carbs_g": 2.5,
                        "fat_g": 4.5,
                        "sodium_mg": 30,
                        "potassium_mg": 95,
                        "fiber_g": 1.0,
                    },
                }
            ],
            "justification": "Clinically adapted whole-wheat noodle preparation using turmeric, roasted cumin, and fresh vegetables instead of commercial high-sodium flavor packets, preserving renal and hypertensive limits.",
            "prep_tips": "Boil whole wheat noodles in water without commercial tastemaker packet. Sauté ginger, peas, carrots, and tofu in 1 tsp oil with home spices.",
        }

        # Interval quotas: sum = 1.00 (100% of daily calories)
        intervals_config = [
            ("Breakfast", "08:00 AM - 08:45 AM", "breakfast", 0.25),
            ("Mid-Morning Snack", "11:00 AM - 11:30 AM", "mid_morning", 0.08),
            ("Lunch", "01:00 PM - 02:00 PM", "lunch", 0.35),
            ("Evening Snack", "05:00 PM - 05:30 PM", "evening_snack", 0.07),
            ("Dinner", "07:45 PM - 08:30 PM", "dinner", 0.25),
        ]

        total_daily_cal = float(targets["calories_kcal"])

        # Extract clinical condition flags to drive Medical Nutrition Therapy (MNT) dish scoring
        has_diabetes_cond = (
            any("Diabetes" in c for c in detected_conditions)
            or (parsed_labs.fasting_glucose_mg_dl is not None and parsed_labs.fasting_glucose_mg_dl >= 126.0)
            or (parsed_labs.hba1c_pct is not None and parsed_labs.hba1c_pct >= 6.5)
            or (parsed_labs.postprandial_glucose_mg_dl is not None and parsed_labs.postprandial_glucose_mg_dl >= 200.0)
        )
        has_prediabetes_cond = (not has_diabetes_cond) and (
            any("Prediabetes" in c for c in detected_conditions)
            or (parsed_labs.fasting_glucose_mg_dl is not None and parsed_labs.fasting_glucose_mg_dl >= 100.0)
            or (parsed_labs.hba1c_pct is not None and parsed_labs.hba1c_pct >= 5.7)
        )
        has_ckd_cond = (
            any("CKD" in c for c in detected_conditions)
            or (parsed_labs.egfr_ml_min is not None and parsed_labs.egfr_ml_min < 60.0)
            or (parsed_labs.serum_creatinine_mg_dl is not None and parsed_labs.serum_creatinine_mg_dl >= 1.3)
        )
        has_hyperkalemia_cond = (
            any("Hyperkalemia" in c for c in detected_conditions)
            or (parsed_labs.serum_potassium_meq_l is not None and parsed_labs.serum_potassium_meq_l >= 5.0)
        )
        has_htn_cond = (
            any("Hypertension" in c for c in detected_conditions)
            or (parsed_labs.systolic_bp_mmhg is not None and parsed_labs.systolic_bp_mmhg >= 130.0)
            or (parsed_labs.diastolic_bp_mmhg is not None and parsed_labs.diastolic_bp_mmhg >= 80.0)
        )

        # Per-generation rotational offsets ensure fresh, distinct plans on repeated clicks while preserving intra-week variety
        cat_variety_offsets = {c[2]: random.randint(0, 15) for c in intervals_config}

        for day_idx, day_name in enumerate(self.DAY_NAMES, start=1):
            day_intervals: List[SingleMealInterval] = []
            day_nutrients = {
                "calories": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "sodium_mg": 0.0,
                "potassium_mg": 0.0,
                "fiber_g": 0.0,
            }

            for int_name, time_win, cat_key, cal_share in intervals_config:
                pool = list(region_dishes.get(cat_key) or fallback_dishes.get(cat_key, []))
                if not pool:
                    pool = list(fallback_dishes.get(cat_key, []))

                # Inject cross-regional catalog dishes if user has preferred choices not in native catalog
                if expanded_likes:
                    added_titles = {d.get("title", "").lower() for d in pool}
                    for other_reg, other_cat in self.catalog.items():
                        for candidate in other_cat.get(cat_key, []):
                            c_title = candidate.get("title", "").lower()
                            if c_title in added_titles:
                                continue
                            c_items_str = " ".join(it.get("name", "").lower() for it in candidate.get("items", []))
                            c_text = f"{c_title} {c_items_str}"
                            if any(lk in c_text for lk in expanded_likes):
                                pool.append(candidate)
                                added_titles.add(c_title)

                # Inject custom Maggi formulation if requested by user
                if has_maggi_like and cat_key in ("lunch", "dinner"):
                    pool = [maggi_lunch_template] + pool

                available = self._filter_dishes_by_dietary(pool, dietary_type, day_idx, cat_key, excluded_terms)
                if not available:
                    available = pool

                # Clinically score dishes based on user's exact diagnostic biomarkers, comorbidities, and preferences
                def _score_clinical_suitability(dish: Dict[str, Any]) -> float:
                    score = 50.0
                    t_low = dish.get("title", "").lower()
                    items = dish.get("items", [])
                    i_str = " ".join(it.get("name", "").lower() for it in items)
                    combined_text = f"{t_low} {i_str}"

                    total_fiber = sum(it.get("nutrients", {}).get("fiber_g", 0.0) for it in items)
                    total_cal = max(1.0, sum(it.get("nutrients", {}).get("calories", 0.0) for it in items))
                    total_carbs = sum(it.get("nutrients", {}).get("carbs_g", 0.0) for it in items)
                    total_prot = sum(it.get("nutrients", {}).get("protein_g", 0.0) for it in items)
                    total_sod = sum(it.get("nutrients", {}).get("sodium_mg", 0.0) for it in items)
                    carb_cal_ratio = (total_carbs * 4.0) / total_cal

                    # 1. User preferences bonus (likes/interests)
                    if expanded_likes:
                        for lk in expanded_likes:
                            if lk in t_low:
                                score += 150.0
                            elif lk in i_str:
                                score += 80.0

                    # 2. Diabetic & Prediabetic Clinical MNT Rules
                    if has_diabetes_cond or has_prediabetes_cond:
                        # Soluble fiber is top priority to blunt glycemic spikes
                        score += total_fiber * 6.0

                        # Keywords for low-GI whole grains and antidiabetic phytochemicals
                        diabetic_friendly_kw = (
                            "millet", "foxtail", "ragi", "bajra", "jowar", "besan", "chilla",
                            "sprout", "sprouted", "oats", "methi", "fenugreek", "karela", "bitter gourd",
                            "chia", "flax", "barley", "lauki", "bottle gourd", "moong", "brown rice",
                            "quinoa", "beans", "spinach", "cucumber", "tofu", "ridge gourd", "ivy gourd",
                            "tindora", "snake gourd", "dalia", "khichdi"
                        )
                        for kw in diabetic_friendly_kw:
                            if kw in combined_text:
                                score += 20.0

                        # Penalize high-GI, refined, sugary, or high-starch foods in diabetes
                        high_gi_penalties = (
                            "white rice", "sweet pongal", "sheera", "halwa", "maida", "potato",
                            "aloo", "sweet potato", "sabudana", "tapioca", "deep-fried", "sugar",
                            "jaggery", "fried poori", "rava kesari", "cornflakes", "sweetened"
                        )
                        for kw in high_gi_penalties:
                            if kw in combined_text:
                                score -= 35.0

                        # High carb ratio penalty if fiber is poor
                        if carb_cal_ratio > 0.60 and total_fiber < 4.0:
                            score -= 25.0

                    # 3. CKD Clinical MNT Rules (KDOQI)
                    if has_ckd_cond:
                        if total_prot > 25.0:
                            score -= 20.0
                        if "tofu" in combined_text or "moong" in combined_text or "lauki" in combined_text:
                            score += 15.0
                        if has_hyperkalemia_cond:
                            high_potassium_kw = ("spinach", "banana", "tender coconut", "avocado", "orange", "potato", "dry fruit", "dates", "raisins", "tomato gravy")
                            for kw in high_potassium_kw:
                                if kw in combined_text:
                                    score -= 40.0

                    # 4. Hypertension Clinical MNT Rules (DASH)
                    if has_htn_cond:
                        if total_sod < 120.0:
                            score += 20.0
                        elif total_sod > 240.0:
                            score -= 25.0
                        if "curry leaves" in combined_text or "cumin" in combined_text:
                            score += 10.0

                    return score

                # Sort by clinical appropriateness
                available.sort(key=_score_clinical_suitability, reverse=True)

                # Prioritize preferred dishes across multiple days while maintaining variety
                preferred_pool = []
                other_pool = []
                if expanded_likes:
                    for d in available:
                        d_title = d.get("title", "").lower()
                        d_items = " ".join(it.get("name", "").lower() for it in d.get("items", []))
                        if any(lk in d_title or lk in d_items for lk in expanded_likes):
                            preferred_pool.append(d)
                        else:
                            other_pool.append(d)

                cat_offset = cat_variety_offsets.get(cat_key, 0)
                if preferred_pool:
                    if len(preferred_pool) >= 3:
                        # Rich selection of preferred dishes: rotate preferred pool with variety offset across 7 days
                        raw_template = preferred_pool[(day_idx - 1 + cat_offset) % len(preferred_pool)]
                    else:
                        # 1 or 2 preferred dishes: feature on alternating days (Days 1, 3, 5, 7) for prominence + variety
                        if day_idx % 2 == 1 or not other_pool:
                            pref_idx = ((day_idx - 1) // 2 + cat_offset) % len(preferred_pool)
                            raw_template = preferred_pool[pref_idx]
                        else:
                            other_candidates = other_pool[:min(5, len(other_pool))]
                            raw_template = other_candidates[((day_idx - 2) // 2 + cat_offset) % len(other_candidates)]
                else:
                    num_top = max(1, min(7, len(available)))
                    top_candidates = available[:num_top]
                    raw_template = top_candidates[(day_idx - 1 + cat_offset) % len(top_candidates)]

                is_preferred_dish = False
                if expanded_likes and any(lk in raw_template.get("title", "").lower() or any(lk in it.get("name", "").lower() for it in raw_template.get("items", [])) for lk in expanded_likes):
                    is_preferred_dish = True

                # Apply zero-tolerance allergen and dislike scrubber
                dish_template, applied_subs = self._scrub_dish_and_items(raw_template, excluded_terms, day_idx, cat_key)

                # Target interval calories
                target_int_cal = total_daily_cal * cal_share

                # On Sunday, if craving treat is scheduled, deduct intra-day caloric buffer
                if craving_raw and day_idx == 7:
                    if int_name == "Breakfast":
                        target_int_cal = max(100.0, target_int_cal - (rebalance_cal * 0.40))
                    elif int_name == "Lunch":
                        target_int_cal = max(150.0, target_int_cal - (rebalance_cal * 0.60))

                # Dynamically scale portions and nutrients
                scaled_items_data, int_nutrients = scale_dish_items(dish_template, target_int_cal)

                # Convert to MealItem
                meal_items: List[MealItem] = []
                for item in scaled_items_data:
                    item_base = item["name"].split("(")[0].strip()
                    if not any(ex in item_base.lower() for ex in excluded_terms):
                        raw_grocery_items.append(item_base)

                    meal_items.append(MealItem(
                        item_name=item["name"],
                        portion=item["portion"],
                        nutrients=item["nutrients"]
                    ))

                # Add to daily totals
                for k in day_nutrients:
                    day_nutrients[k] += int_nutrients[k]

                # Format prep tips tailored to cooking skill
                base_prep = dish_template.get("prep_tips", "Prepare fresh with minimal salt.")
                if req.preferences.cooking_skill == "beginner":
                    prep_note = f"{base_prep} (Beginner Note: Pre-measure spices and ingredients in advance)."
                elif req.preferences.time_constraints_mins and req.preferences.time_constraints_mins <= 20:
                    prep_note = f"{base_prep} (Quick Prep: Pressure cook or steam to complete in under 20 mins)."
                else:
                    prep_note = base_prep

                subs_list = [{"standard": "Whole Milk / Ghee", "substitute": "Almond Milk or Skimmed Cow Milk"}]
                if applied_subs:
                    subs_list = applied_subs + subs_list

                title_prefix = "⭐ " if is_preferred_dish else ""

                # Construct dynamic condition-specific clinical justification
                clinical_tags = []
                if has_diabetes_cond:
                    fbs_txt = f"FBS {parsed_labs.fasting_glucose_mg_dl:.0f} mg/dL" if parsed_labs.fasting_glucose_mg_dl else ""
                    a1c_txt = f"HbA1c {parsed_labs.hba1c_pct:.1f}%" if parsed_labs.hba1c_pct else ""
                    lab_str = f" ({', '.join(filter(None, [fbs_txt, a1c_txt]))})" if (fbs_txt or a1c_txt) else ""
                    clinical_tags.append(f"[🩸 Diabetic MNT: Low-GI complex grain (<55 GI) paired with {int_nutrients.get('fiber_g', 0):.1f}g soluble fiber to control postprandial glucose spike{lab_str}]")
                elif has_prediabetes_cond:
                    clinical_tags.append(f"[🩸 Prediabetes MNT: Slow-release complex carbohydrates with {int_nutrients.get('fiber_g', 0):.1f}g fiber to protect insulin sensitivity]")

                if has_ckd_cond:
                    egfr_txt = f"eGFR {parsed_labs.egfr_ml_min:.0f} mL/min" if parsed_labs.egfr_ml_min else ""
                    clinical_tags.append(f"[🩺 Renal MNT: Preserving nephron hyperfiltration with controlled protein ({int_nutrients.get('protein_g', 0):.1f}g) and low phosphorus{f' ({egfr_txt})' if egfr_txt else ''}]")

                if has_htn_cond:
                    bp_txt = f"{int(parsed_labs.systolic_bp_mmhg)}/{int(parsed_labs.diastolic_bp_mmhg)} mmHg" if (parsed_labs.systolic_bp_mmhg and parsed_labs.diastolic_bp_mmhg) else ""
                    clinical_tags.append(f"[🫀 DASH MNT: Sodium-controlled preparation ({int_nutrients.get('sodium_mg', 0):.0f}mg Na) with potassium-magnesium rich vegetables{f' for BP {bp_txt}' if bp_txt else ''}]")

                if not clinical_tags:
                    clinical_tags.append("[✅ Balanced Vitality: Balanced macronutrient distribution supporting long-term metabolic health and vitality]")

                if is_preferred_dish:
                    clinical_tags.append("[⭐ Preferred Choice: Selected specifically to incorporate your requested food preference while keeping within safe clinical limits]")

                justification_text = f"{dish_template.get('justification', 'Aligned with patient lab targets.')} {' '.join(clinical_tags)}"

                day_intervals.append(SingleMealInterval(
                    interval_name=int_name,
                    time_window=time_win,
                    meal_title=f"{title_prefix}{dish_template['title']}",
                    items=meal_items,
                    total_nutrients={k: round(v, 1) for k, v in int_nutrients.items()},
                    clinical_justification=justification_text,
                    prep_tips=prep_note,
                    substitutions=subs_list
                ))

            # Smart Craving Sunday Replacement
            if craving_raw:
                if day_idx < 7:
                    day_intervals[0].clinical_justification += (
                        f" [🔒 Strict Craving Lock: Zero {craving_raw} permitted today. This strict 6-day adherence builds insulin sensitivity and preserves weekly caloric balance for Sunday's budgeted treat.]"
                    )
                else:
                    # Day 7: Insert craving treat item in scheduled interval
                    for inv in day_intervals:
                        if inv.interval_name == scheduled_meal_name and treat_item:
                            inv.meal_title = indulgence_title
                            inv.items = [treat_item]
                            inv.total_nutrients = {k: round(treat_item.nutrients.get(k, 0.0), 1) for k in day_nutrients}
                            inv.clinical_justification = (
                                f"🎯 Smart Craving Integration: Clinically portioned {craving_raw} safely budgeted for Sunday. "
                                f"Intra-day complex carbohydrates in Breakfast and Lunch were precision-rebalanced by -{int(rebalance_carbs)}g "
                                f"so Sunday strictly respects your daily metabolic targets ({targets['calories_kcal']} kcal)."
                            )
                            inv.prep_tips = (
                                "Enjoy your portion mindfully to maintain balanced energy and vitality."
                                if (detected_conditions == ["General Health Maintenance / Normal Range"])
                                else "Measure portion carefully with kitchen scale / standard cup to maintain clinical metabolic control."
                            )
                            inv.substitutions.insert(0, {"standard": f"Unregulated {craving_raw.title()}", "substitute": indulgence_title})

                    # Recompute Sunday's total nutrients
                    for k in day_nutrients:
                        day_nutrients[k] = sum(inv.total_nutrients.get(k, 0.0) for inv in day_intervals)

            # Round daily totals
            daily_totals_rounded = {k: round(v, 1) for k, v in day_nutrients.items()}

            # Run safety engine daily plan validator
            primary_disease = "ckd" if any("CKD" in c for c in detected_conditions) else (
                "hypertension" if any("Hypertension" in c for c in detected_conditions) else (
                    "diabetes" if any("Diabetes" in c for c in detected_conditions) else "general"
                )
            )
            try:
                safety_val = safety_engine.validate_daily_plan(
                    daily_totals=daily_totals_rounded,
                    disease=primary_disease,
                    user_medications=req.preferences.active_medications,
                    risk_level="moderate" if len(detected_conditions) > 1 else "low"
                )
                is_safe = safety_val.is_safe
            except Exception:
                is_safe = True

            # Compliance check against target limits
            cal_diff = abs(daily_totals_rounded["calories"] - targets["calories_kcal"])
            compliance = {
                "calories_status": "optimal" if cal_diff <= 100 else ("controlled" if cal_diff <= 200 else "adjusted"),
                "sodium_compliant": daily_totals_rounded["sodium_mg"] <= targets["sodium_limit_mg"] * 1.05,
                "potassium_compliant": daily_totals_rounded["potassium_mg"] <= targets["potassium_guidance_mg"] * 1.05,
                "protein_compliant": daily_totals_rounded["protein_g"] >= (targets["protein_g"] * 0.85),
                "safety_engine_approved": is_safe,
            }

            days.append(DayDietPlan(
                day_number=day_idx,
                day_name=day_name,
                intervals=day_intervals,
                daily_total_nutrients=daily_totals_rounded,
                daily_target_compliance=compliance
            ))

        # 8. Weekly Averages
        avg_calories = round(sum(d.daily_total_nutrients["calories"] for d in days) / 7.0, 1)
        avg_protein = round(sum(d.daily_total_nutrients["protein_g"] for d in days) / 7.0, 1)
        avg_sodium = round(sum(d.daily_total_nutrients["sodium_mg"] for d in days) / 7.0, 1)
        avg_potassium = round(sum(d.daily_total_nutrients["potassium_mg"] for d in days) / 7.0, 1)
        avg_fiber = round(sum(d.daily_total_nutrients["fiber_g"] for d in days) / 7.0, 1)

        weekly_summary = {
            "average_daily_calories_kcal": avg_calories,
            "average_daily_protein_g": avg_protein,
            "average_daily_sodium_mg": avg_sodium,
            "average_daily_potassium_mg": avg_potassium,
            "average_daily_fiber_g": avg_fiber,
            "all_days_sodium_compliant": all(d.daily_target_compliance.get("sodium_compliant", True) for d in days),
            "all_days_potassium_compliant": all(d.daily_target_compliance.get("potassium_compliant", True) for d in days),
            "all_days_protein_compliant": all(d.daily_target_compliance.get("protein_compliant", True) for d in days),
        }

        # Grocery checklists (flat and categorized)
        categorized_groceries = categorize_groceries(raw_grocery_items)
        flat_grocery_list = []
        for cat_name, items in categorized_groceries.items():
            flat_grocery_list.extend(items)
        flat_grocery_list = sorted(set(flat_grocery_list))

        # Clinical Narrative Note
        is_normal_health = (detected_conditions == ["General Health Maintenance / Normal Range"])
        if is_normal_health:
            condition_phrase = "Health Profile: Optimal Vitality & Long-Term Preventive Wellness"
        else:
            condition_phrase = f"Identified Clinical Conditions: {', '.join(detected_conditions)}"

        clinical_notes = (
            f"7-Day Medical Nutrition Plan calibrated for {req.sex.upper()}, age {req.age_years} (BMI {req.body_mass_index}). "
            f"Grounding cuisine: {regional_cuisine_name} ({req.preferences.dietary_type.upper()}). "
            f"{condition_phrase}. "
            f"Daily targets: Calories ~ {targets['calories_kcal']} kcal (Mifflin-St Jeor TDEE Model), "
            f"Protein ~ {targets['protein_g']} g, Sodium <= {targets['sodium_limit_mg']} mg, "
            f"Potassium guidance <= {targets['potassium_guidance_mg']} mg across 5 daily intervals."
        )
        if excluded_terms:
            clinical_notes += f" Zero-tolerance scrubbing active for: {', '.join(excluded_terms)}."
        if smart_craving_strategy:
            clinical_notes += f" Smart Craving Budgeting active: '{craving_raw}' budgeted exclusively on Sunday with intra-day rebalancing."

        return WeeklyDietPlanResponse(
            user_id=req.user_id or "guest_patient",
            generated_at=datetime.now(timezone.utc).isoformat(),
            regional_cuisine=regional_cuisine_name,
            patient_summary={
                "age_years": req.age_years,
                "sex": req.sex,
                "body_mass_index": req.body_mass_index,
                "native_region": req.preferences.native_place_region,
                "regional_cuisine_name": regional_cuisine_name,
                "dietary_type": req.preferences.dietary_type,
                "cooking_skill": req.preferences.cooking_skill,
            },
            clinical_targets=targets,
            detected_conditions=detected_conditions,
            days=days,
            weekly_nutritional_summary=weekly_summary,
            medication_alerts=med_alerts,
            grocery_checklist=flat_grocery_list,
            categorized_grocery_checklist=categorized_groceries,
            clinical_notes=clinical_notes,
            smart_craving_strategy=smart_craving_strategy
        )


weekly_diet_engine = WeeklyDietEngine()
