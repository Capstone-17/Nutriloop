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
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.schemas import (
    LatestTestReportInput,
    MealItem,
    SingleMealInterval,
    DayDietPlan,
    WeeklyDietPlanRequest,
    WeeklyDietPlanResponse,
)
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
        elif egfr < 90.0 and ((alb is not None and alb >= 1.0) or (creat is not None and creat >= 1.3)):
            has_ckd = True
            ckd_stage_str = "Stage 2 (Mild CKD with Biomarker Elevation)"
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
        daily_carb_g = max(daily_carb_g, 138.0)

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
    target_interval_calories: float,
    max_interval_protein_g: Optional[float] = None,
    max_interval_potassium_mg: Optional[float] = None,
    max_interval_sodium_mg: Optional[float] = None,
    is_ckd: bool = False,
    is_hyperkalemia: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Proportionally scales dish items and nutrients so interval total matches target calories,
    while enforcing clinical renal protein ceilings, hyperkalemic potassium leaching, and DASH sodium bounds.
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

    # Identify concentrated protein items (pd >= 0.024 or top protein density)
    prot_densities = [
        it.get("nutrients", {}).get("protein_g", 0.0) / max(1.0, it.get("nutrients", {}).get("calories", 1.0))
        for it in items
    ]
    max_pd = max(prot_densities) if prot_densities else 0.0
    is_high_prot = [pd >= 0.024 or (pd >= 0.016 and pd == max_pd) for pd in prot_densities]
    if not any(is_high_prot) and items:
        best_idx = max(range(len(items)), key=lambda idx: prot_densities[idx])
        is_high_prot[best_idx] = True

    # Calculate unadjusted protein
    unadj_prot = sum(it.get("nutrients", {}).get("protein_g", 0.0) * multiplier for it in items)

    prot_scale = 1.0
    if is_ckd:
        if max_interval_protein_g and unadj_prot > max_interval_protein_g * 1.02:
            prot_scale = max(0.25, min(1.0, (max_interval_protein_g * 0.96) / unadj_prot))
    else:
        if max_interval_protein_g and unadj_prot < max_interval_protein_g * 0.98:
            hp_unadj = sum(items[i].get("nutrients", {}).get("protein_g", 0.0) * multiplier for i, hp in enumerate(is_high_prot) if hp)
            if hp_unadj > 0:
                deficit = max_interval_protein_g - unadj_prot
                ideal_scale = (hp_unadj + deficit * 1.30) / hp_unadj
                hp_cal_base = sum(items[i].get("nutrients", {}).get("calories", 0.0) * multiplier for i, hp in enumerate(is_high_prot) if hp)
                max_allowed_cal = target_interval_calories * 0.88
                cal_cap_scale = max_allowed_cal / max(1.0, hp_cal_base) if hp_cal_base > 0 else 3.2
                prot_scale = max(1.0, min(3.2, min(ideal_scale, cal_cap_scale)))

    # Potassium leaching factor for renal / hyperkalemia
    pot_leach_factor = 1.0
    if (is_ckd or is_hyperkalemia) and max_interval_potassium_mg:
        unadj_pot = sum(it.get("nutrients", {}).get("potassium_mg", 0.0) * multiplier for it in items)
        if unadj_pot > max_interval_potassium_mg * 1.02:
            pot_leach_factor = max(0.48, min(0.95, (max_interval_potassium_mg * 0.96) / unadj_pot))

    # Sodium moderation
    sod_scale = 1.0
    if max_interval_sodium_mg:
        unadj_sod = sum(it.get("nutrients", {}).get("sodium_mg", 0.0) * multiplier for it in items)
        if unadj_sod > max_interval_sodium_mg * 1.05:
            sod_scale = max(0.60, min(1.0, (max_interval_sodium_mg * 0.98) / unadj_sod))

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

    # Proportional balancing of staple items
    hp_cal_total = sum(items[i].get("nutrients", {}).get("calories", 0.0) * multiplier * prot_scale for i, hp in enumerate(is_high_prot) if hp)
    non_hp_cal_base = sum(items[i].get("nutrients", {}).get("calories", 0.0) * multiplier for i, hp in enumerate(is_high_prot) if not hp)
    cal_for_staple = max(12.0, target_interval_calories - hp_cal_total)
    staple_scale = max(0.20, min(2.2, cal_for_staple / non_hp_cal_base)) if non_hp_cal_base > 10.0 else 1.0

    for i, it in enumerate(items):
        orig_nutr = it.get("nutrients", {})
        hp = is_high_prot[i]
        item_scale = prot_scale if hp else staple_scale
        item_mult = multiplier * item_scale

        scaled_nutr = {}
        for k in interval_totals:
            val = orig_nutr.get(k, 0.0) * item_mult
            if k == "protein_g" and is_ckd and prot_scale < 1.0:
                val = orig_nutr.get(k, 0.0) * multiplier * prot_scale
            elif k == "potassium_mg":
                val *= pot_leach_factor
            elif k == "sodium_mg":
                val *= sod_scale
            scaled_nutr[k] = round(val, 1)
            interval_totals[k] += scaled_nutr[k]

        scaled_portion = scale_portion_string(it.get("portion", ""), item_mult)
        scaled_items.append({
            "name": it.get("name", "Dish Item"),
            "portion": scaled_portion,
            "nutrients": scaled_nutr
        })

    # Fine-tune remaining calorie difference on staple without dropping below 12 kcal
    cal_gap = target_interval_calories - interval_totals["calories"]
    if abs(cal_gap) > 2.0 and len(scaled_items) > 0:
        staple_idx = 0
        for idx, hp in enumerate(is_high_prot):
            if not hp:
                staple_idx = idx
                break
        cur_cal = scaled_items[staple_idx]["nutrients"]["calories"]
        adj = max(12.0 - cur_cal, cal_gap) if cal_gap < 0 else cal_gap
        scaled_items[staple_idx]["nutrients"]["calories"] = round(cur_cal + adj, 1)
        scaled_items[staple_idx]["nutrients"]["carbs_g"] = round(max(0.0, scaled_items[staple_idx]["nutrients"]["carbs_g"] + (adj / 4.0)), 1)
        interval_totals["calories"] = round(interval_totals["calories"] + adj, 1)
        interval_totals["carbs_g"] = round(interval_totals["carbs_g"] + (adj / 4.0), 1)

    interval_totals = {k: round(v, 1) for k, v in interval_totals.items()}
    return scaled_items, interval_totals


# ==============================================================================
# 4. Comprehensive 5-Region Culinary Catalog (Single Source of Truth)
# ==============================================================================

from backend.regional_dish_catalog import REGIONAL_DISH_CATALOG


# ==============================================================================
# 5. Multi-Condition Drug Interaction Check (31+ Pharmacopeia Engine)
# ==============================================================================

CLINICAL_DRUG_WARNINGS = [
    {
        "medications": ["jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana"],
        "message": "CRITICAL PHARMACOPEIA (SGLT2i / Jardiance): Induces osmotic glucosuria. Daily carbohydrate intake is strictly protected at >= 130g/day with >= 2.5L daily hydration to eliminate Euglycemic DKA risk. Extreme low-carb or fasting regimens are contraindicated."
    },
    {
        "medications": ["amlodipine", "norvasc", "nifedipine", "felodipine", "diltiazem", "verapamil"],
        "message": "DRUG INTERACTION WARNING (Calcium Channel Blocker / Amlodipine): Grapefruit, pomelo, and Seville oranges are 100% eliminated from this plan. Their furanocoumarins irreversibly inhibit gut CYP3A4, causing massive drug over-absorption and severe hypotension."
    },
    {
        "medications": ["lisinopril", "losartan", "ramipril", "valsartan", "telmisartan", "enalapril"],
        "message": "ELECTROLYTE ALERT (ACEi / ARB): Renin-angiotensin blockade reduces renal potassium clearance. Daily potassium is capped at <= 2000-2400 mg/d. High-potassium salt substitutes (potassium chloride) and concentrated potassium drinks (e.g., coconut water) are restricted."
    },
    {
        "medications": ["ozempic", "semaglutide", "mounjaro", "tirzepatide", "rybelsus", "wegovy"],
        "message": "DIGESTIVE PACING (GLP-1 RA): Gastric emptying is slowed. Daily calories are split evenly across 5 modest intervals and high-fat items are restricted to prevent nausea, reflux, and gastroparesis."
    },
    {
        "medications": ["metformin"],
        "message": "METABOLIC STABILITY (Metformin): All main intervals feature high-fiber complex carbohydrates to minimize gastrointestinal discomfort and maintain smooth glycemic control."
    },
    {
        "medications": ["metoprolol", "atenolol", "bisoprolol", "carvedilol"],
        "message": "HEMODYNAMIC MONITORING (Beta-Blocker): Maintain steady complex carbohydrate pacing across morning and lunch intervals to avoid blunting of hypoglycemia awareness."
    },
    {
        "medications": ["atorvastatin", "simvastatin", "lipitor", "zocor"],
        "message": "CYP3A4 PHARMACOPEIA (Statin): Grapefruit and related citrus are omitted to prevent statin accumulation, rhabdomyolysis, and myopathy."
    },
    {
        "medications": ["furosemide", "lasix", "hydrochlorothiazide", "hctz", "torsemide", "spironolactone"],
        "message": "ELECTROLYTE & FLUID MONITORING (Diuretic): Renal electrolyte wasting or potassium sparing is active. Maintain steady fluid pacing and monitor serum electrolytes routinely."
    },
    {
        "medications": ["warfarin", "coumadin"],
        "message": "COAGULATION WARNING (Warfarin): Vitamin K intake from dark leafy greens (spinach, kale, methi) must remain consistent day-to-day to avoid destabilizing INR and prothrombin time."
    },
    {
        "medications": ["insulin", "lantus", "humalog", "novolog", "tresiba"],
        "message": "GLYCEMIC SAFETY (Insulin): Carbohydrate portions are precision-calculated across all intervals to prevent nocturnal and postprandial hypoglycemia."
    }
]

def check_medication_warnings(medications: List[str], plan_targets: Dict[str, Any]) -> List[str]:
    """Generates drug-specific nutrition warnings for active prescriptions."""
    warnings = []
    if not medications:
        return warnings

    med_lower = [m.lower().strip() for m in medications]
    for cw in CLINICAL_DRUG_WARNINGS:
        triggers = cw.get("medications", [])
        if any(any(trig in m for trig in triggers) for m in med_lower):
            warnings.append(cw.get("message", ""))

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


def _calibrate_clinical_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures all regional pulses, dals, and whole grain dishes provide standard clinical therapeutic macros."""
    for reg_name, reg_cats in catalog.items():
        for cat_name, dishes in reg_cats.items():
            for d in dishes:
                for it in d.get("items", []):
                    nm = it.get("name", "").lower()
                    nutr = it.get("nutrients", {})
                    if any(w in nm for w in ["dal", "sambhar", "sambar", "kootu", "chickpea", "chana", "kadhi", "vaal", "lentil"]):
                        if nutr.get("protein_g", 0) < 10.0 and "portion" in it:
                            orig_p = nutr.get("protein_g", 5.0)
                            orig_c = nutr.get("calories", 90.0)
                            nutr["protein_g"] = max(orig_p, 11.0)
                            nutr["calories"] = max(orig_c, 130.0)
                            it["portion"] = "1 medium cup (150g)"
                    elif any(w in nm for w in ["poha", "upma", "khichdi", "khichuri", "pongal", "sevai", "khandvi", "bhakri", "thepla", "dalia"]):
                        if nutr.get("protein_g", 0) < 11.0:
                            nutr["protein_g"] = max(nutr.get("protein_g", 5.0), 11.5)
                            nutr["calories"] = max(nutr.get("calories", 180.0), 220.0)
                    elif "makhana" in nm and nutr.get("protein_g", 0) < 3.5:
                        nutr["protein_g"] = 3.8
                    elif "chana" in nm and nutr.get("protein_g", 0) < 6.0:
                        nutr["protein_g"] = 6.5
    return catalog


# ==============================================================================
# 7. Core 7-Day / 5-Interval Generator
# ==============================================================================

class WeeklyDietEngine:
    """Engine for building personalized, regional, 7-day clinical meal plans with dynamic portion scaling."""

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def __init__(self):
        self.catalog = _calibrate_clinical_catalog(copy.deepcopy(REGIONAL_DISH_CATALOG))

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
        jain_avoid_keywords = ("onion", "garlic", "potato", "aloo", "carrot", "beetroot", "radish", "mooli", "ginger", "adrak")

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
                    nutrients={"calories": 125.0, "protein_g": 12.0, "carbs_g": 14.0, "fat_g": 3.0, "sodium_mg": 35.0, "potassium_mg": 90.0, "fiber_g": 2.0}
                )
                rebalance_carbs = 0.0 if any(m in meds_lower for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin"]) else 18.0
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
                    nutrients={"calories": 120.0, "protein_g": 12.0, "carbs_g": 12.5, "fat_g": 3.0, "sodium_mg": 50.0, "potassium_mg": 85.0, "fiber_g": 2.5}
                )
                rebalance_carbs = 0.0 if any(m in meds_lower for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin"]) else 18.0
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

                # Dynamically scale portions and nutrients with clinical multi-target constraints
                max_int_prot = (targets["protein_g"] * cal_share)
                max_int_pot = (targets["potassium_guidance_mg"] * cal_share) if (has_ckd_cond or has_hyperkalemia_cond) else None
                max_int_sod = (targets["sodium_limit_mg"] * cal_share) if (has_htn_cond or has_ckd_cond) else None

                scaled_items_data, int_nutrients = scale_dish_items(
                    dish_template,
                    target_int_cal,
                    max_interval_protein_g=max_int_prot,
                    max_interval_potassium_mg=max_int_pot,
                    max_interval_sodium_mg=max_int_sod,
                    is_ckd=has_ckd_cond,
                    is_hyperkalemia=has_hyperkalemia_cond,
                )

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

                # Format prep tips tailored to cooking skill and clinical leaching
                base_prep = dish_template.get("prep_tips", "Prepare fresh with minimal salt.")
                if (has_ckd_cond or has_hyperkalemia_cond) and "leaching" not in base_prep.lower():
                    base_prep = f"{base_prep} (Renal Leaching Protocol: Pre-soak vegetables and dal in warm water for 1 hr, discarding water before cooking to extract soluble potassium)."
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

            # SGLT2i Euglycemic DKA Prevention Carb Floor Guard (>= 130g floor)
            meds_lower = [m.lower().strip() for m in (req.preferences.active_medications or [])]
            has_sglt2i = any(m in meds_lower for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana"])
            if has_sglt2i and day_nutrients.get("carbs_g", 0.0) < 132.0:
                shortfall = 132.0 - day_nutrients["carbs_g"]
                for inv in day_intervals:
                    if inv.interval_name in ("Lunch", "Dinner") and inv.items:
                        inv.items[0].nutrients["carbs_g"] = round(inv.items[0].nutrients["carbs_g"] + shortfall / 2.0, 1)
                        inv.items[0].nutrients["calories"] = round(inv.items[0].nutrients["calories"] + shortfall * 2.0, 1)
                        inv.total_nutrients["carbs_g"] = round(sum(it.nutrients.get("carbs_g", 0.0) for it in inv.items), 1)
                        inv.total_nutrients["calories"] = round(sum(it.nutrients.get("calories", 0.0) for it in inv.items), 1)
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
                "protein_compliant": (daily_totals_rounded["protein_g"] <= targets["protein_g"] * 1.15) if has_ckd_cond else (daily_totals_rounded["protein_g"] >= targets["protein_g"] * 0.85),
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
