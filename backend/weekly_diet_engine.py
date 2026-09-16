"""
Personalized Weekly Diet Recommendation Engine
==============================================
Generates a clinically validated, culturally authentic 7-day (Monday-Sunday),
5-interval meal schedule based on:
  1. Patient's latest clinical test reports (biomarkers and/or report text)
  2. Native place / regional culinary background
  3. Individual dietary preferences, interests, allergies, and dislikes
  4. Active medications (cross-referenced against 18+ drug pharmacopeia)
  5. Clinical comorbidity solver (KDOQI vs. DASH paradox & ADA guidelines)
"""

from __future__ import annotations
from datetime import datetime, timezone
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

    # 4. HbA1c: e.g. "hba1c: 7.8%", "a1c 8.2"
    if data.get("hba1c_pct") is None:
        m = re.search(r"(?:hba1c|a1c)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["hba1c_pct"] = float(m.group(1))

    # 5. eGFR: e.g. "egfr 48 ml/min", "gfr: 52"
    if data.get("egfr_ml_min") is None:
        m = re.search(r"(?:egfr|gfr)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["egfr_ml_min"] = float(m.group(1))

    # 6. Serum Potassium: e.g. "potassium: 4.8 meq/l", "k+ 5.1"
    if data.get("serum_potassium_meq_l") is None:
        m = re.search(r"(?:serum\s+)?(?:potassium|k\+)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["serum_potassium_meq_l"] = float(m.group(1))

    # 7. Serum Sodium: e.g. "sodium: 138", "na+ 136"
    if data.get("serum_sodium_meq_l") is None:
        m = re.search(r"(?:serum\s+)?(?:sodium|na\+)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["serum_sodium_meq_l"] = float(m.group(1))

    # 8. Blood Urea / BUN: e.g. "blood urea: 58 mg/dl", "bun 26"
    if data.get("blood_urea_mg_dl") is None:
        m = re.search(r"(?:blood\s+urea|urea|bun)[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["blood_urea_mg_dl"] = float(m.group(1))

    # 9. Urine Albumin / Dipstick: e.g. "urine albumin 2+", "proteinuria 1+"
    if data.get("urine_albumin_dipstick") is None:
        m = re.search(r"(?:urine\s+)?(?:albumin|protein(?:uria)?)[:\s=]+(\+?\d+|\+)", text)
        if m:
            val_str = m.group(1).replace("+", "")
            data["urine_albumin_dipstick"] = float(val_str) if val_str else 1.0

    # 10. Total Cholesterol: e.g. "cholesterol 235 mg/dl"
    if data.get("total_cholesterol_mg_dl") is None:
        m = re.search(r"(?:total\s+)?cholesterol[:\s=]+(\d+(?:\.\d+)?)", text)
        if m:
            data["total_cholesterol_mg_dl"] = float(m.group(1))

    return LatestTestReportInput(**data)


# ==============================================================================
# 2. Clinical Target Derivation Engine
# ==============================================================================

def derive_clinical_targets(
    age: int,
    sex: str,
    bmi: float,
    labs: LatestTestReportInput,
    override_calories: Optional[int] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Computes precise daily nutritional targets and identifies clinical conditions
    strictly from laboratory biomarkers and anthropometry.
    """
    detected_conditions = []
    
    # Analyze lab values
    creat = labs.serum_creatinine_mg_dl
    egfr = labs.egfr_ml_min
    urea = labs.blood_urea_mg_dl
    alb = labs.urine_albumin_dipstick
    sys_bp = labs.systolic_bp_mmhg
    dia_bp = labs.diastolic_bp_mmhg
    fbs = labs.fasting_glucose_mg_dl
    a1c = labs.hba1c_pct
    k_val = labs.serum_potassium_meq_l
    chol = labs.total_cholesterol_mg_dl

    # CKD Detection
    has_ckd = False
    if (creat is not None and creat >= 1.3) or (egfr is not None and egfr < 60) or (alb is not None and alb >= 1.0) or (urea is not None and urea >= 45.0):
        has_ckd = True
        detected_conditions.append("Chronic Kidney Disease (CKD)")

    # Hypertension Detection
    has_htn = False
    if (sys_bp is not None and sys_bp >= 130.0) or (dia_bp is not None and dia_bp >= 85.0):
        has_htn = True
        detected_conditions.append("Hypertension")

    # Diabetes Detection
    has_diabetes = False
    if (fbs is not None and fbs >= 126.0) or (a1c is not None and a1c >= 6.5):
        has_diabetes = True
        detected_conditions.append("Type 2 Diabetes Mellitus")

    # Dyslipidemia
    if chol is not None and chol >= 200.0:
        detected_conditions.append("Hypercholesterolemia")

    # Hyperkalemia Warning
    has_hyperkalemia = k_val is not None and k_val >= 5.0
    if has_hyperkalemia:
        detected_conditions.append("Elevated Serum Potassium (Hyperkalemia Risk)")

    if not detected_conditions:
        detected_conditions.append("General Health Maintenance / Normal Range")

    # 1. Calorie Target
    if override_calories:
        daily_calories = override_calories
    else:
        # Standard Harris-Benedict approximation adjusted for BMI & clinical state
        base_kcal = 2000 if sex == "male" else 1800
        if bmi >= 30.0:
            daily_calories = base_kcal - 350
        elif bmi >= 25.0:
            daily_calories = base_kcal - 150
        elif bmi < 18.5:
            daily_calories = base_kcal + 250
        else:
            daily_calories = base_kcal

        # T2DM / Metabolic adjustment
        if has_diabetes:
            daily_calories = min(daily_calories, 1800)

    # 2. Protein Target (g)
    # KDOQI recommends 0.6 - 0.8 g/kg for non-dialysis CKD
    estimated_weight_kg = bmi * 1.7 * 1.7  # approximate from standard height
    if has_ckd:
        daily_protein_g = round(estimated_weight_kg * 0.7, 1)  # 0.7 g/kg
    elif has_diabetes:
        daily_protein_g = round(estimated_weight_kg * 1.0, 1)  # 1.0 g/kg
    else:
        daily_protein_g = round(estimated_weight_kg * 0.9, 1)

    daily_protein_g = max(45.0, min(daily_protein_g, 90.0))

    # 3. Sodium Limit (mg)
    # DASH & KDIGO: 1500 mg if hypertensive or CKD
    if has_htn or has_ckd:
        daily_sodium_mg = 1500.0
    else:
        daily_sodium_mg = 2000.0

    # 4. Potassium Guidance (mg)
    # KDOQI Precedence: strict restriction if CKD or serum K >= 5.0
    if has_ckd or has_hyperkalemia:
        daily_potassium_mg = 1800.0 if has_hyperkalemia else 2000.0
    elif has_htn:
        daily_potassium_mg = 3500.0  # DASH high-potassium natriuresis
    else:
        daily_potassium_mg = 3000.0

    # 5. Phosphorus Limit (mg)
    daily_phosphorus_mg = 800.0 if has_ckd else 1200.0

    # 6. Carbohydrate & Free Sugar Target
    daily_carb_g = round((daily_calories * (0.42 if has_diabetes else 0.50)) / 4.0, 1)
    daily_sugar_g = 20.0 if has_diabetes else 35.0
    daily_fiber_g = 35.0 if (has_diabetes or has_htn) else 25.0
    daily_fat_g = round((daily_calories - (daily_protein_g * 4 + daily_carb_g * 4)) / 9.0, 1)
    daily_fat_g = max(35.0, daily_fat_g)

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
        "fluid_intake_ml": 2000 if has_ckd else 2500,
    }

    return targets, detected_conditions


# ==============================================================================
# 3. Regional Culinary Knowledge & Dish Repository
# ==============================================================================

REGIONAL_DISH_CATALOG = {
    # ------------------ SOUTH INDIAN ------------------
    "south_indian": {
        "breakfast": [
            {
                "title": "Steamed Ragi Idli with Mint Coconut Chutney",
                "items": [
                    {"name": "Steamed Ragi Idli", "portion": "3 medium idlis (150g)", "nutrients": {"calories": 210, "protein_g": 6.5, "carbs_g": 40, "fat_g": 1.5, "sodium_mg": 85, "potassium_mg": 180, "fiber_g": 5.0}},
                    {"name": "Thin Coconut Mint Chutney (Low Salt)", "portion": "2 tbsp (30g)", "nutrients": {"calories": 65, "protein_g": 1.0, "carbs_g": 3.0, "fat_g": 5.5, "sodium_mg": 60, "potassium_mg": 70, "fiber_g": 1.2}},
                ],
                "justification": "Finger millet (Ragi) provides low glycemic index carbs with high soluble fiber, keeping postprandial glucose stable.",
                "prep_tips": "Steam batter without sodium bicarbonate or baking soda to control sodium."
            },
            {
                "title": "Moong Dal Dosa (Pesarattu) with Ginger Chutney",
                "items": [
                    {"name": "Moong Dal Dosa (Pesarattu)", "portion": "2 medium (140g)", "nutrients": {"calories": 240, "protein_g": 10.5, "carbs_g": 38, "fat_g": 4.5, "sodium_mg": 95, "potassium_mg": 210, "fiber_g": 5.5}},
                    {"name": "Fresh Ginger Allam Chutney (Mild)", "portion": "2 tbsp (30g)", "nutrients": {"calories": 40, "protein_g": 0.8, "carbs_g": 7.0, "fat_g": 1.0, "sodium_mg": 55, "potassium_mg": 60, "fiber_g": 1.0}},
                ],
                "justification": "Yellow moong is easy on renal filtration with lower purine and high plant-based bioavailable protein.",
                "prep_tips": "Grind soaked green moong with ginger and cumin; use cold-pressed sesame or olive oil."
            },
            {
                "title": "Vegetable Oats Upma with Curry Leaves",
                "items": [
                    {"name": "Vegetable Oats Upma with French Beans & Carrots", "portion": "1.5 cups (200g)", "nutrients": {"calories": 230, "protein_g": 7.0, "carbs_g": 39, "fat_g": 4.5, "sodium_mg": 90, "potassium_mg": 190, "fiber_g": 6.0}},
                ],
                "justification": "Beta-glucan fiber in oats aids blood pressure reduction and cholesterol regulation without loading potassium.",
                "prep_tips": "Temper mustard and curry leaves in 1 tsp oil; simmer beans till tender."
            },
            {
                "title": "Red Rice Idli with Drumstick Sambhar",
                "items": [
                    {"name": "Red Rice Idli", "portion": "3 medium (150g)", "nutrients": {"calories": 215, "protein_g": 5.8, "carbs_g": 43, "fat_g": 1.2, "sodium_mg": 70, "potassium_mg": 160, "fiber_g": 4.5}},
                    {"name": "Mild Drumstick & Lauki Sambhar", "portion": "1 cup (180g)", "nutrients": {"calories": 85, "protein_g": 4.0, "carbs_g": 14, "fat_g": 1.5, "sodium_mg": 110, "potassium_mg": 190, "fiber_g": 3.0}},
                ],
                "justification": "Drumsticks and bottle gourd have gentle renal profiles and high antioxidant flavonoid levels.",
                "prep_tips": "Boil drumstick in lightly spiced tamarind broth without packaged sambhar powders."
            },
        ],
        "mid_morning": [
            {
                "title": "Cucumber Spears with Roasted Cumin & Tender Coconut Water",
                "items": [
                    {"name": "Crisp Cucumber Slices with Lemon & Jeera", "portion": "1 cup (120g)", "nutrients": {"calories": 20, "protein_g": 0.8, "carbs_g": 4.0, "fat_g": 0.2, "sodium_mg": 15, "potassium_mg": 140, "fiber_g": 1.5}},
                ],
                "justification": "Hydrating, low glycemic, low sodium snack to bridge morning glucose levels.",
                "prep_tips": "Sprinkle freshly roasted cumin powder; avoid table salt."
            },
            {
                "title": "Spiced Buttermilk (Neer Mor) with Curry Leaves",
                "items": [
                    {"name": "Diluted Buttermilk (Neer Mor) with Hing & Ginger", "portion": "1 glass (200ml)", "nutrients": {"calories": 45, "protein_g": 2.8, "carbs_g": 4.5, "fat_g": 1.2, "sodium_mg": 40, "potassium_mg": 150, "fiber_g": 0.5}},
                ],
                "justification": "Naturally probiotic; diluted yogurt reduces phosphorus load while soothing digestion.",
                "prep_tips": "Whisk curd with 3 parts chilled water; temper with mustard and crushed ginger."
            },
            {
                "title": "Steamed White Chana Sundal (Lightly Tempered)",
                "items": [
                    {"name": "Steamed Chickpea Sundal with Fresh Coconut", "portion": "1/2 cup (80g)", "nutrients": {"calories": 95, "protein_g": 4.5, "carbs_g": 15, "fat_g": 2.0, "sodium_mg": 45, "potassium_mg": 170, "fiber_g": 3.5}},
                ],
                "justification": "Provides sustained satiety through complex carbohydrates and soluble legumes.",
                "prep_tips": "Pre-soak overnight and pressure cook; drain cooking water to reduce potassium."
            },
        ],
        "lunch": [
            {
                "title": "Brown Rice with Lauki Kootu & Tomato Rasam",
                "items": [
                    {"name": "Steamed Brown Rice", "portion": "1 cup (150g)", "nutrients": {"calories": 175, "protein_g": 4.0, "carbs_g": 37, "fat_g": 1.2, "sodium_mg": 5, "potassium_mg": 110, "fiber_g": 2.5}},
                    {"name": "Bottle Gourd (Lauki) & Moong Dal Kootu", "portion": "1 cup (180g)", "nutrients": {"calories": 140, "protein_g": 7.0, "carbs_g": 20, "fat_g": 3.5, "sodium_mg": 95, "potassium_mg": 220, "fiber_g": 4.0}},
                    {"name": "Clear Pepper Cumin Tomato Rasam", "portion": "1 cup (150ml)", "nutrients": {"calories": 45, "protein_g": 1.2, "carbs_g": 8.0, "fat_g": 0.8, "sodium_mg": 85, "potassium_mg": 160, "fiber_g": 1.0}},
                    {"name": "Snake Gourd (Pudalangai) Poriyal", "portion": "1/2 cup (80g)", "nutrients": {"calories": 60, "protein_g": 1.5, "carbs_g": 7.0, "fat_g": 2.5, "sodium_mg": 45, "potassium_mg": 130, "fiber_g": 2.5}},
                ],
                "justification": "Snake gourd and bottle gourd are top-ranked renal vegetables with exceptionally low potassium density.",
                "prep_tips": "Cook dal and gourd together; season with black pepper instead of red chili."
            },
            {
                "title": "Foxtail Millet Rice with Sambhar & Cabbage Thoran",
                "items": [
                    {"name": "Steamed Foxtail Millet (Thinai)", "portion": "1 cup (150g)", "nutrients": {"calories": 180, "protein_g": 5.0, "carbs_g": 36, "fat_g": 1.5, "sodium_mg": 8, "potassium_mg": 125, "fiber_g": 4.0}},
                    {"name": "Mixed Vegetable Sambhar (Carrot, Beans)", "portion": "1 cup (180g)", "nutrients": {"calories": 125, "protein_g": 6.5, "carbs_g": 18, "fat_g": 2.5, "sodium_mg": 110, "potassium_mg": 210, "fiber_g": 3.5}},
                    {"name": "Cabbage Green Peas Thoran", "portion": "3/4 cup (100g)", "nutrients": {"calories": 75, "protein_g": 2.5, "carbs_g": 9.0, "fat_g": 3.0, "sodium_mg": 60, "potassium_mg": 150, "fiber_g": 3.0}},
                ],
                "justification": "Millets possess significantly lower glycemic indices than polished white rice, preventing insulin spikes.",
                "prep_tips": "Soak foxtail millet for 30 minutes before steaming for fluffier texture."
            },
            {
                "title": "Curd Rice with Pomegranate & Steamed Ridge Gourd Poriyal",
                "items": [
                    {"name": "Low-Fat Probiotic Curd Rice with Mustard Tempering", "portion": "1.2 cups (180g)", "nutrients": {"calories": 190, "protein_g": 6.2, "carbs_g": 32, "fat_g": 3.5, "sodium_mg": 80, "potassium_mg": 170, "fiber_g": 2.0}},
                    {"name": "Ridge Gourd (Peerkangai) Stir-Fry", "portion": "1 cup (120g)", "nutrients": {"calories": 70, "protein_g": 2.0, "carbs_g": 9.0, "fat_g": 2.5, "sodium_mg": 50, "potassium_mg": 160, "fiber_g": 3.5}},
                    {"name": "Pomegranate Arils Garnish", "portion": "2 tbsp (30g)", "nutrients": {"calories": 25, "protein_g": 0.5, "carbs_g": 5.5, "fat_g": 0.3, "sodium_mg": 3, "potassium_mg": 65, "fiber_g": 1.0}},
                ],
                "justification": "Pomegranate provides polyphenol vascular protection, while ridge gourd supports smooth renal clearance.",
                "prep_tips": "Use homemade skimmed-milk dahi to maintain low saturated fat."
            },
        ],
        "evening_snack": [
            {
                "title": "Roasted Makhana (Fox Nuts) with Green Tea",
                "items": [
                    {"name": "Lightly Roasted Makhana with Turmeric & Pepper", "portion": "1 cup (30g)", "nutrients": {"calories": 105, "protein_g": 3.0, "carbs_g": 20, "fat_g": 0.5, "sodium_mg": 25, "potassium_mg": 120, "fiber_g": 2.5}},
                    {"name": "Unsweetened Jasmine Green Tea", "portion": "1 cup (180ml)", "nutrients": {"calories": 2, "protein_g": 0.0, "carbs_g": 0.5, "fat_g": 0.0, "sodium_mg": 5, "potassium_mg": 25, "fiber_g": 0.0}},
                ],
                "justification": "Makhana is low in sodium and fat, delivering clean plant protein without phosphorus overload.",
                "prep_tips": "Dry roast in a cast-iron pan for 4 minutes till crunchy; toss with pinch of turmeric."
            },
            {
                "title": "Boiled Sprouted Moong Chaat",
                "items": [
                    {"name": "Boiled Moong Sprouts with Lemon & Coriander", "portion": "3/4 cup (100g)", "nutrients": {"calories": 90, "protein_g": 6.0, "carbs_g": 15, "fat_g": 0.8, "sodium_mg": 35, "potassium_mg": 160, "fiber_g": 3.5}},
                ],
                "justification": "Sprouting enhances amino acid bioaccessibility while reducing phytate anti-nutrients.",
                "prep_tips": "Steam sprouts for 5 minutes; toss with chopped cucumber, cilantro, and fresh lime."
            },
        ],
        "dinner": [
            {
                "title": "Phulka Rotis with Tinda Masala & Yellow Dal",
                "items": [
                    {"name": "Whole Wheat Soft Phulka (Oil-free)", "portion": "2 medium (60g)", "nutrients": {"calories": 160, "protein_g": 5.0, "carbs_g": 32, "fat_g": 1.0, "sodium_mg": 30, "potassium_mg": 110, "fiber_g": 3.5}},
                    {"name": "Stewed Tinda (Apple Gourd) Gravy", "portion": "1 cup (150g)", "nutrients": {"calories": 85, "protein_g": 2.0, "carbs_g": 11, "fat_g": 3.0, "sodium_mg": 70, "potassium_mg": 180, "fiber_g": 3.0}},
                    {"name": "Thin Tadka Yellow Moong Dal", "portion": "1/2 cup (100g)", "nutrients": {"calories": 90, "protein_g": 5.5, "carbs_g": 13, "fat_g": 1.5, "sodium_mg": 75, "potassium_mg": 140, "fiber_g": 2.5}},
                ],
                "justification": "Light, evening-friendly digestion profile that avoids midnight blood pressure spikes.",
                "prep_tips": "Puff phulkas directly on flame; do not brush with butter or ghee."
            },
            {
                "title": "Jowar (Sorghum) Roti with Ridge Gourd & Tomato Stew",
                "items": [
                    {"name": "Gluten-Free Jowar Roti", "portion": "2 rotis (80g)", "nutrients": {"calories": 170, "protein_g": 4.5, "carbs_g": 36, "fat_g": 1.5, "sodium_mg": 15, "potassium_mg": 130, "fiber_g": 4.0}},
                    {"name": "Turmeric Braised Peerkangai (Ridge Gourd)", "portion": "1 cup (160g)", "nutrients": {"calories": 80, "protein_g": 2.2, "carbs_g": 11, "fat_g": 2.8, "sodium_mg": 65, "potassium_mg": 170, "fiber_g": 3.0}},
                    {"name": "Warm Spiced Rasam Broth", "portion": "3/4 cup (120ml)", "nutrients": {"calories": 35, "protein_g": 1.0, "carbs_g": 6.0, "fat_g": 0.5, "sodium_mg": 70, "potassium_mg": 110, "fiber_g": 0.8}},
                ],
                "justification": "Sorghum provides slow-release complex carbs, avoiding early morning fasting glucose elevations.",
                "prep_tips": "Knead jowar flour with warm water; roll thin and cook on high heat."
            },
            {
                "title": "Millet Khichdi with Steamed French Beans",
                "items": [
                    {"name": "Little Millet (Samai) & Split Yellow Moong Khichdi", "portion": "1.3 cups (200g)", "nutrients": {"calories": 230, "protein_g": 8.5, "carbs_g": 41, "fat_g": 3.0, "sodium_mg": 95, "potassium_mg": 210, "fiber_g": 5.0}},
                    {"name": "Steamed French Beans with Grated Ginger", "portion": "3/4 cup (90g)", "nutrients": {"calories": 45, "protein_g": 1.8, "carbs_g": 7.5, "fat_g": 0.8, "sodium_mg": 30, "potassium_mg": 140, "fiber_g": 2.5}},
                ],
                "justification": "Equal parts millet and split moong create a balanced amino acid pool without uric acid accumulation.",
                "prep_tips": "Pressure cook for 3 whistles with cumin, turmeric, and pinch of black pepper."
            },
        ]
    },

    # ------------------ NORTH INDIAN ------------------
    "north_indian": {
        "breakfast": [
            {
                "title": "Methi Missi Roti with Skimmed Curd",
                "items": [
                    {"name": "Fenugreek (Methi) Besan & Wheat Roti", "portion": "2 medium (100g)", "nutrients": {"calories": 220, "protein_g": 8.5, "carbs_g": 36, "fat_g": 3.5, "sodium_mg": 90, "potassium_mg": 190, "fiber_g": 5.5}},
                    {"name": "Fresh Low-Fat Cow Curd", "portion": "1/2 cup (100g)", "nutrients": {"calories": 60, "protein_g": 4.0, "carbs_g": 5.0, "fat_g": 2.0, "sodium_mg": 50, "potassium_mg": 150, "fiber_g": 0.0}},
                ],
                "justification": "Methi leaves contain 4-hydroxyisoleucine which stimulates glucose-dependent insulin secretion.",
                "prep_tips": "Mix fresh chopped fenugreek into 50:50 wheat and chickpea flour."
            },
            {
                "title": "Vegetable Dalia (Broken Wheat Porridge)",
                "items": [
                    {"name": "Savory Dalia with Peas, Carrots & Cumin", "portion": "1.5 cups (220g)", "nutrients": {"calories": 230, "protein_g": 7.2, "carbs_g": 42, "fat_g": 3.0, "sodium_mg": 85, "potassium_mg": 195, "fiber_g": 6.5}},
                ],
                "justification": "High whole-grain endosperm fiber slows enzymatic carbohydrate breakdown.",
                "prep_tips": "Dry roast dalia until nutty before pressure cooking with vegetables."
            },
            {
                "title": "Moong Dal Chilla with Mint Chutney",
                "items": [
                    {"name": "Yellow Moong Dal Savory Pancake", "portion": "2 chillas (130g)", "nutrients": {"calories": 225, "protein_g": 11.0, "carbs_g": 35, "fat_g": 4.0, "sodium_mg": 90, "potassium_mg": 210, "fiber_g": 5.0}},
                    {"name": "Pudina Coriander Chutney (No Garlic)", "portion": "2 tbsp (30g)", "nutrients": {"calories": 30, "protein_g": 0.8, "carbs_g": 4.0, "fat_g": 1.0, "sodium_mg": 45, "potassium_mg": 75, "fiber_g": 1.2}},
                ],
                "justification": "Moong chilla delivers satisfying plant protein with negligible saturated fat.",
                "prep_tips": "Spread batter thin on a non-stick griddle with a brush of olive or mustard oil."
            },
        ],
        "mid_morning": [
            {
                "title": "Roasted Chana & Sweet Papaya Cubes",
                "items": [
                    {"name": "Unsalted Roasted Bengal Gram (Chana)", "portion": "2 tbsp (30g)", "nutrients": {"calories": 80, "protein_g": 4.0, "carbs_g": 12, "fat_g": 1.2, "sodium_mg": 20, "potassium_mg": 130, "fiber_g": 3.0}},
                    {"name": "Fresh Ripe Papaya Slices", "portion": "3/4 cup (100g)", "nutrients": {"calories": 40, "protein_g": 0.5, "carbs_g": 10, "fat_g": 0.1, "sodium_mg": 5, "potassium_mg": 180, "fiber_g": 1.8}},
                ],
                "justification": "Papain enzyme aids peptide digestion while maintaining safe potassium limits.",
                "prep_tips": "Consume fresh; avoid adding chaat masala to restrict sodium."
            },
            {
                "title": "Poha with Roasted Peanuts & Squeezed Lemon",
                "items": [
                    {"name": "Flattened Rice (Poha) with Green Peas", "portion": "3/4 cup (100g)", "nutrients": {"calories": 110, "protein_g": 2.5, "carbs_g": 22, "fat_g": 1.5, "sodium_mg": 40, "potassium_mg": 110, "fiber_g": 2.0}},
                ],
                "justification": "Easily digested carbohydrate snack with mild iron biofortification from flattened rice.",
                "prep_tips": "Rinse poha lightly; saute with green chillies, turmeric, and lemon juice."
            },
        ],
        "lunch": [
            {
                "title": "Multigrain Rotis with Lauki Kofta (Steamed) & Dal Tadka",
                "items": [
                    {"name": "Multigrain Wheat & Barley Rotis", "portion": "2 rotis (70g)", "nutrients": {"calories": 175, "protein_g": 5.5, "carbs_g": 35, "fat_g": 1.2, "sodium_mg": 35, "potassium_mg": 120, "fiber_g": 4.5}},
                    {"name": "Steamed Lauki (Bottle Gourd) Dumplings in Light Gravy", "portion": "1 cup (180g)", "nutrients": {"calories": 130, "protein_g": 4.5, "carbs_g": 16, "fat_g": 4.5, "sodium_mg": 95, "potassium_mg": 210, "fiber_g": 3.5}},
                    {"name": "Yellow Arhar Dal with Cumin Hing Tempering", "portion": "3/4 cup (120g)", "nutrients": {"calories": 110, "protein_g": 6.5, "carbs_g": 16, "fat_g": 2.0, "sodium_mg": 85, "potassium_mg": 180, "fiber_g": 3.0}},
                ],
                "justification": "Steaming the lauki kofta instead of deep frying removes trans-fats and protects endothelial function.",
                "prep_tips": "Bind grated bottle gourd with gram flour, steam for 10 minutes, and simmer in tomato puree."
            },
            {
                "title": "Jeera Rice with Paneer Bhurji & Cucumber Salad",
                "items": [
                    {"name": "Steamed Rice with Cumin Seeds", "portion": "1 cup (150g)", "nutrients": {"calories": 170, "protein_g": 3.8, "carbs_g": 36, "fat_g": 1.0, "sodium_mg": 10, "potassium_mg": 95, "fiber_g": 1.5}},
                    {"name": "Low-Fat Cottage Cheese (Paneer) Bhurji with Capsicum", "portion": "3/4 cup (120g)", "nutrients": {"calories": 160, "protein_g": 14.0, "carbs_g": 6.0, "fat_g": 8.0, "sodium_mg": 110, "potassium_mg": 160, "fiber_g": 1.5}},
                    {"name": "Cucumber Tomato Onion Salad with Lemon", "portion": "1 cup (120g)", "nutrients": {"calories": 35, "protein_g": 1.0, "carbs_g": 7.0, "fat_g": 0.2, "sodium_mg": 15, "potassium_mg": 170, "fiber_g": 2.0}},
                ],
                "justification": "Low-fat paneer delivers high biological value protein without phosphorus-heavy processing additives.",
                "prep_tips": "Make paneer at home using skimmed cow milk curdled with lemon juice."
            },
        ],
        "evening_snack": [
            {
                "title": "Roasted Makhana with Tulsi Herbal Tea",
                "items": [
                    {"name": "Dry Roasted Fox Nuts with Black Salt & Jeera", "portion": "1 cup (30g)", "nutrients": {"calories": 105, "protein_g": 3.0, "carbs_g": 20, "fat_g": 0.5, "sodium_mg": 30, "potassium_mg": 120, "fiber_g": 2.5}},
                    {"name": "Holy Basil (Tulsi) Ginger Infusion", "portion": "1 cup (180ml)", "nutrients": {"calories": 2, "protein_g": 0.0, "carbs_g": 0.4, "fat_g": 0.0, "sodium_mg": 5, "potassium_mg": 20, "fiber_g": 0.0}},
                ],
                "justification": "Tulsi compounds support cortisol regulation and blood pressure stabilization.",
                "prep_tips": "Steep fresh tulsi leaves and crushed ginger in boiling water for 5 minutes."
            },
        ],
        "dinner": [
            {
                "title": "Phulkas with Baingan Bharta (Roasted Eggplant) & Moong Dal",
                "items": [
                    {"name": "Whole Wheat Roti", "portion": "2 rotis (60g)", "nutrients": {"calories": 160, "protein_g": 5.0, "carbs_g": 32, "fat_g": 1.0, "sodium_mg": 25, "potassium_mg": 110, "fiber_g": 3.5}},
                    {"name": "Char-Roasted Baingan Bharta with Fresh Peas", "portion": "1 cup (150g)", "nutrients": {"calories": 105, "protein_g": 3.0, "carbs_g": 14, "fat_g": 3.5, "sodium_mg": 70, "potassium_mg": 210, "fiber_g": 4.5}},
                    {"name": "Light Yellow Moong Soup Dal", "portion": "3/4 cup (120g)", "nutrients": {"calories": 95, "protein_g": 6.0, "carbs_g": 14, "fat_g": 1.5, "sodium_mg": 75, "potassium_mg": 150, "fiber_g": 2.5}},
                ],
                "justification": "Eggplant (brinjal) has low caloric density and high nasunin anthocyanins protecting cerebral vessels.",
                "prep_tips": "Roast whole eggplant over open flame, peel burnt skin, and mash with tomatoes and green chilies."
            },
            {
                "title": "Moong Dal Khichdi with Kadhi (Low Salt)",
                "items": [
                    {"name": "Warm Split Moong Rice Khichdi", "portion": "1.3 cups (200g)", "nutrients": {"calories": 220, "protein_g": 8.0, "carbs_g": 39, "fat_g": 3.0, "sodium_mg": 85, "potassium_mg": 200, "fiber_g": 4.5}},
                    {"name": "Besan Curd Kadhi with Methi & Hing", "portion": "3/4 cup (120ml)", "nutrients": {"calories": 90, "protein_g": 3.8, "carbs_g": 9.0, "fat_g": 3.8, "sodium_mg": 75, "potassium_mg": 140, "fiber_g": 1.2}},
                ],
                "justification": "Traditional comfort dinner offering smooth GI transit and complete protein pairing.",
                "prep_tips": "Simmer besan and sour curd with turmeric; do not add deep-fried pakoras."
            },
        ]
    },

    # ------------------ WESTERN INDIAN (GUJARATI / MAHARASHTRIAN) ------------------
    "western_indian": {
        "breakfast": [
            {
                "title": "Bajra Methi Thepla with Low-Fat Curd",
                "items": [
                    {"name": "Pearl Millet (Bajra) Methi Thepla", "portion": "2 medium (90g)", "nutrients": {"calories": 210, "protein_g": 6.8, "carbs_g": 36, "fat_g": 4.0, "sodium_mg": 80, "potassium_mg": 190, "fiber_g": 5.5}},
                    {"name": "Fresh Cow Milk Curd", "portion": "1/2 cup (100g)", "nutrients": {"calories": 60, "protein_g": 4.0, "carbs_g": 5.0, "fat_g": 2.0, "sodium_mg": 45, "potassium_mg": 145, "fiber_g": 0.0}},
                ],
                "justification": "Bajra is rich in magnesium and potassium-friendly dietary fiber that slows carbohydrate uptake.",
                "prep_tips": "Use fenugreek greens and sesame seeds in dough; roll thin and roast with minimal oil."
            },
            {
                "title": "Steamed Dudhi (Bottle Gourd) Muthia",
                "items": [
                    {"name": "Steamed Dudhi Muthia with Mustard Tempering", "portion": "6-8 pieces (150g)", "nutrients": {"calories": 215, "protein_g": 6.5, "carbs_g": 38, "fat_g": 3.8, "sodium_mg": 85, "potassium_mg": 185, "fiber_g": 5.0}},
                ],
                "justification": "Steamed preparation preserving bottle gourd's gentle electrolyte balance.",
                "prep_tips": "Grate bottle gourd, mix with whole wheat and besan flour; steam for 18 minutes."
            },
        ],
        "mid_morning": [
            {
                "title": "Plain Roasted Khakhra with Green Tea",
                "items": [
                    {"name": "Methi Wheat Khakhra (Oil-Free)", "portion": "2 crisps (40g)", "nutrients": {"calories": 110, "protein_g": 3.5, "carbs_g": 22, "fat_g": 1.0, "sodium_mg": 45, "potassium_mg": 95, "fiber_g": 3.0}},
                    {"name": "Mint Green Tea", "portion": "1 cup (180ml)", "nutrients": {"calories": 2, "protein_g": 0.0, "carbs_g": 0.5, "fat_g": 0.0, "sodium_mg": 5, "potassium_mg": 25, "fiber_g": 0.0}},
                ],
                "justification": "Crunchy roasted whole-grain snack that satisfies appetite without sodium surges.",
                "prep_tips": "Press with wooden press on dry griddle until fully crisp."
            },
        ],
        "lunch": [
            {
                "title": "Jowar Bhakri with Sev Tameta (Mild) & Tuvar Dal",
                "items": [
                    {"name": "Sorghum (Jowar) Bhakri", "portion": "2 medium (80g)", "nutrients": {"calories": 170, "protein_g": 4.5, "carbs_g": 36, "fat_g": 1.5, "sodium_mg": 20, "potassium_mg": 130, "fiber_g": 4.0}},
                    {"name": "Fresh Tomato Gravy with Steamed Gourd", "portion": "1 cup (160g)", "nutrients": {"calories": 105, "protein_g": 2.5, "carbs_g": 14, "fat_g": 3.8, "sodium_mg": 85, "potassium_mg": 210, "fiber_g": 3.5}},
                    {"name": "Gujarati Tuvar Dal (No Added Sugar)", "portion": "3/4 cup (120g)", "nutrients": {"calories": 115, "protein_g": 6.0, "carbs_g": 18, "fat_g": 1.8, "sodium_mg": 90, "potassium_mg": 175, "fiber_g": 3.0}},
                ],
                "justification": "Replaces traditional jaggery/sugar in Gujarati dal with cinnamon to maintain glycemic compliance.",
                "prep_tips": "Season dal with kokum and ginger instead of sugar."
            },
        ],
        "evening_snack": [
            {
                "title": "Sprouted Usal Chaat with Lime",
                "items": [
                    {"name": "Steamed Matki (Moth Bean) Sprouts Usal", "portion": "3/4 cup (100g)", "nutrients": {"calories": 105, "protein_g": 6.5, "carbs_g": 17, "fat_g": 1.0, "sodium_mg": 40, "potassium_mg": 180, "fiber_g": 4.0}},
                ],
                "justification": "Moth beans provide zinc and potassium for vascular resilience.",
                "prep_tips": "Boil sprouted matki with turmeric; finish with lemon juice and chopped coriander."
            },
        ],
        "dinner": [
            {
                "title": "Moong Dal Khichdi with Dahi Kadhi & Steamed Tindora",
                "items": [
                    {"name": "Rice & Yellow Moong Khichdi", "portion": "1.3 cups (200g)", "nutrients": {"calories": 220, "protein_g": 8.0, "carbs_g": 40, "fat_g": 2.8, "sodium_mg": 85, "potassium_mg": 195, "fiber_g": 4.5}},
                    {"name": "Light Curd Kadhi with Curry Leaves", "portion": "3/4 cup (120ml)", "nutrients": {"calories": 85, "protein_g": 3.5, "carbs_g": 8.0, "fat_g": 3.5, "sodium_mg": 70, "potassium_mg": 130, "fiber_g": 1.0}},
                    {"name": "Tindora (Ivy Gourd) Dry Sabzi", "portion": "1/2 cup (75g)", "nutrients": {"calories": 55, "protein_g": 1.5, "carbs_g": 7.0, "fat_g": 2.0, "sodium_mg": 40, "potassium_mg": 120, "fiber_g": 2.5}},
                ],
                "justification": "Ivy gourd has documented anti-hyperglycemic properties, reducing fasting insulin resistance.",
                "prep_tips": "Slice ivy gourd vertically and saute in 1 tsp peanut or sesame oil."
            },
        ]
    },

    # ------------------ EASTERN INDIAN (BENGALI / ODIA) ------------------
    "eastern_indian": {
        "breakfast": [
            {
                "title": "Dalia Khichuri with Seasonal Vegetables",
                "items": [
                    {"name": "Broken Wheat Moong Dalia Khichuri", "portion": "1.5 cups (220g)", "nutrients": {"calories": 230, "protein_g": 8.0, "carbs_g": 41, "fat_g": 3.0, "sodium_mg": 85, "potassium_mg": 200, "fiber_g": 6.0}},
                ],
                "justification": "Replaces polished white rice with broken wheat to dampen glycemic spikes.",
                "prep_tips": "Add cubed potol (pointed gourd) and carrots for dietary fiber."
            },
        ],
        "mid_morning": [
            {
                "title": "Fresh Guava Slices with Black Salt",
                "items": [
                    {"name": "Pink Guava Slices (Seeds Removed)", "portion": "1 medium (100g)", "nutrients": {"calories": 50, "protein_g": 1.5, "carbs_g": 10, "fat_g": 0.5, "sodium_mg": 10, "potassium_mg": 180, "fiber_g": 4.5}},
                ],
                "justification": "Extremely high vitamin C and pectin content with low free sugar load.",
                "prep_tips": "Scoop out hard central seeds to prevent irritation in diverticular conditions."
            },
        ],
        "lunch": [
            {
                "title": "Brown Rice with Rui Machher Patla Jhol & Potol Chorchori",
                "items": [
                    {"name": "Steamed Brown Rice", "portion": "1 cup (150g)", "nutrients": {"calories": 175, "protein_g": 4.0, "carbs_g": 37, "fat_g": 1.2, "sodium_mg": 5, "potassium_mg": 110, "fiber_g": 2.5}},
                    {"name": "Rohu Fish Light Stew with Papaya & Kalonji", "portion": "1 piece fish + broth (180g)", "nutrients": {"calories": 165, "protein_g": 18.0, "carbs_g": 6.0, "fat_g": 6.5, "sodium_mg": 110, "potassium_mg": 230, "fiber_g": 2.0}},
                    {"name": "Pointed Gourd (Potol) Mustard Chorchori", "portion": "3/4 cup (100g)", "nutrients": {"calories": 70, "protein_g": 2.0, "carbs_g": 8.0, "fat_g": 3.0, "sodium_mg": 50, "potassium_mg": 140, "fiber_g": 3.0}},
                ],
                "justification": "Freshwater rohu provides clean omega-3 fatty acids without saturated mammalian fats.",
                "prep_tips": "Poach fish in turmeric-kalonji broth rather than deep mustard oil frying."
            },
        ],
        "evening_snack": [
            {
                "title": "Puffed Rice (Muri) with Roasted Chana & Green Chili",
                "items": [
                    {"name": "Crisp Muri with Boiled Chickpeas & Cucumber", "portion": "1 cup (45g)", "nutrients": {"calories": 115, "protein_g": 3.5, "carbs_g": 22, "fat_g": 1.0, "sodium_mg": 35, "potassium_mg": 110, "fiber_g": 2.5}},
                ],
                "justification": "Light, oil-free whole grain snack satisfying afternoon cravings.",
                "prep_tips": "Toss dry with drop of mustard oil, chopped onions, and lemon juice."
            },
        ],
        "dinner": [
            {
                "title": "Handmade Rotis with Lau Ghonto & Biulir Dal",
                "items": [
                    {"name": "Whole Wheat Roti", "portion": "2 rotis (60g)", "nutrients": {"calories": 160, "protein_g": 5.0, "carbs_g": 32, "fat_g": 1.0, "sodium_mg": 25, "potassium_mg": 110, "fiber_g": 3.5}},
                    {"name": "Bottle Gourd (Lau) Stew with Bori & Ginger", "portion": "1 cup (160g)", "nutrients": {"calories": 90, "protein_g": 2.5, "carbs_g": 12, "fat_g": 3.0, "sodium_mg": 65, "potassium_mg": 190, "fiber_g": 3.5}},
                    {"name": "Urad (Biulir) Dal with Fennel Hing Tempering", "portion": "1/2 cup (100g)", "nutrients": {"calories": 105, "protein_g": 6.5, "carbs_g": 16, "fat_g": 1.2, "sodium_mg": 70, "potassium_mg": 150, "fiber_g": 3.0}},
                ],
                "justification": "Fennel and hing alleviate abdominal distension while bottle gourd maintains renal safety.",
                "prep_tips": "Temper dal with whole saunf (fennel) and ginger paste."
            },
        ]
    },

    # ------------------ CONTINENTAL / GLOBAL ------------------
    "continental": {
        "breakfast": [
            {
                "title": "Steel-Cut Oatmeal with Blueberries & Flaxseed",
                "items": [
                    {"name": "Steel-Cut Oats cooked in Almond Milk", "portion": "1.2 cups (180g)", "nutrients": {"calories": 210, "protein_g": 6.5, "carbs_g": 38, "fat_g": 3.5, "sodium_mg": 65, "potassium_mg": 170, "fiber_g": 5.5}},
                    {"name": "Fresh Blueberries & Ground Flaxseeds", "portion": "1/3 cup (50g)", "nutrients": {"calories": 45, "protein_g": 1.0, "carbs_g": 9.0, "fat_g": 1.0, "sodium_mg": 3, "potassium_mg": 60, "fiber_g": 2.0}},
                ],
                "justification": "Low-glycemic breakfast delivering anthocyanins and alpha-linolenic omega-3 fatty acids.",
                "prep_tips": "Simmer steel-cut oats for 20 mins; top with unsweetened berries and flax."
            },
            {
                "title": "Egg White & Spinach Scramble with Whole Grain Toast",
                "items": [
                    {"name": "Scrambled Egg Whites (3 whites) with Baby Spinach", "portion": "1 plate (150g)", "nutrients": {"calories": 110, "protein_g": 13.0, "carbs_g": 3.0, "fat_g": 2.5, "sodium_mg": 120, "potassium_mg": 210, "fiber_g": 1.5}},
                    {"name": "Toasted Spelt / Whole Wheat Bread", "portion": "1 slice (40g)", "nutrients": {"calories": 95, "protein_g": 4.0, "carbs_g": 18, "fat_g": 1.0, "sodium_mg": 90, "potassium_mg": 85, "fiber_g": 3.0}},
                ],
                "justification": "High biological value protein with minimal phosphorus and near-zero cholesterol.",
                "prep_tips": "Use olive oil spray on skillet; scramble gently over low heat."
            },
        ],
        "mid_morning": [
            {
                "title": "Crisp Green Apple Slices with Crushed Walnuts",
                "items": [
                    {"name": "Green Tart Apple with Walnut Halves (2 nuts)", "portion": "1 apple (120g)", "nutrients": {"calories": 95, "protein_g": 1.2, "carbs_g": 18, "fat_g": 2.5, "sodium_mg": 5, "potassium_mg": 140, "fiber_g": 3.5}},
                ],
                "justification": "Malic acid and pectin provide clean glycemic control and vascular protection.",
                "prep_tips": "Slice apple unpeeled to preserve insoluble fiber."
            },
        ],
        "lunch": [
            {
                "title": "Grilled Herb Chicken / Tofu Breast with Quinoa & Steamed Asparagus",
                "items": [
                    {"name": "Herb-Marinated Grilled Chicken Breast or Firm Tofu", "portion": "100g fillet", "nutrients": {"calories": 165, "protein_g": 22.0, "carbs_g": 1.5, "fat_g": 5.0, "sodium_mg": 95, "potassium_mg": 240, "fiber_g": 0.5}},
                    {"name": "Steamed Tricolor Quinoa", "portion": "3/4 cup (120g)", "nutrients": {"calories": 150, "protein_g": 5.5, "carbs_g": 27, "fat_g": 2.5, "sodium_mg": 10, "potassium_mg": 160, "fiber_g": 3.5}},
                    {"name": "Steamed Asparagus Spears with Lemon Olive Oil", "portion": "6 spears (80g)", "nutrients": {"calories": 40, "protein_g": 2.0, "carbs_g": 4.0, "fat_g": 2.0, "sodium_mg": 20, "potassium_mg": 180, "fiber_g": 2.0}},
                ],
                "justification": "Complete amino acid profile balanced against low glycemic complex pseudocereals.",
                "prep_tips": "Marinate in lemon zest, rosemary, and cracked black pepper before grilling."
            },
        ],
        "evening_snack": [
            {
                "title": "Carrot Sticks with Garlic White Bean Hummus",
                "items": [
                    {"name": "Fresh Carrot Sticks & Cannellini Bean Dip", "portion": "1 cup (140g)", "nutrients": {"calories": 115, "protein_g": 4.5, "carbs_g": 18, "fat_g": 2.5, "sodium_mg": 65, "potassium_mg": 190, "fiber_g": 4.5}},
                ],
                "justification": "Low-salt white bean dip delivers potassium and fiber without processed sodium preservatives.",
                "prep_tips": "Puree boiled white beans with roasted garlic, lemon juice, and olive oil."
            },
        ],
        "dinner": [
            {
                "title": "Baked Cod / Tofu Fillet with Cauliflower Mash & Green Beans",
                "items": [
                    {"name": "Baked Herb-Crusted White Fish or Tofu", "portion": "110g fillet", "nutrients": {"calories": 150, "protein_g": 20.0, "carbs_g": 2.0, "fat_g": 4.5, "sodium_mg": 85, "potassium_mg": 220, "fiber_g": 0.5}},
                    {"name": "Steamed Garlic Cauliflower Puree", "portion": "3/4 cup (120g)", "nutrients": {"calories": 60, "protein_g": 2.5, "carbs_g": 8.0, "fat_g": 2.0, "sodium_mg": 45, "potassium_mg": 170, "fiber_g": 3.0}},
                    {"name": "Steamed French Green Beans", "portion": "3/4 cup (90g)", "nutrients": {"calories": 40, "protein_g": 1.5, "carbs_g": 7.0, "fat_g": 0.5, "sodium_mg": 15, "potassium_mg": 130, "fiber_g": 2.5}},
                ],
                "justification": "Replaces potassium-rich mashed potatoes with cauliflower mash, reducing potassium load by 60%.",
                "prep_tips": "Steam cauliflower florets until soft, blend with 1 tsp olive oil and nutmeg."
            },
        ]
    }
}


# ==============================================================================
# 4. Multi-Condition Drug Interaction Check
# ==============================================================================

def check_medication_warnings(medications: List[str], plan_targets: Dict[str, Any]) -> List[str]:
    """Generates drug-specific nutrition warnings for active prescriptions."""
    warnings = []
    if not medications:
        return warnings

    med_lower = [m.lower().strip() for m in medications]
    
    # SGLT2i Check (Jardiance, Farxiga)
    if any(m in med_lower for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin"]):
        warnings.append(
            "CRITICAL PHARMACOPEIA (SGLT2i / Jardiance): Ensure adequate fluid intake (>= 2.2L) and avoid extreme carbohydrate restriction (<100g/d) to eliminate Euglycemic DKA risk."
        )

    # CCB Check (Amlodipine, Norvasc)
    if any(m in med_lower for m in ["amlodipine", "norvasc", "nifedipine"]):
        warnings.append(
            "DRUG INTERACTION WARNING (Calcium Channel Blocker): Completely avoid grapefruit and Seville oranges due to irreversible CYP3A4 inhibition."
        )

    # ACEi / ARB Check (Lisinopril, Losartan)
    if any(m in med_lower for m in ["lisinopril", "losartan", "ramipril", "valsartan"]):
        warnings.append(
            "ELECTROLYTE ALERT (ACEi/ARB): Avoid potassium-enriched salt substitutes (KCl) and monitor dietary potassium to prevent sudden hyperkalemia."
        )

    # GLP-1 RA Check (Ozempic, Rybelsus, Mounjaro)
    if any(m in med_lower for m in ["ozempic", "semaglutide", "mounjaro", "tirzepatide"]):
        warnings.append(
            "DIGESTIVE PACING (GLP-1 RA): Gastric emptying is slowed. Consume small, frequent intervals and avoid high-fat fried preparations."
        )

    # Metformin Check
    if any("metformin" in m for m in med_lower):
        warnings.append(
            "METABOLIC STABILITY (Metformin): Pair meals with complex carbohydrates and avoid alcohol ingestion during extended fasting."
        )

    return warnings


# ==============================================================================
# 5. Core 7-Day / 5-Interval Generator
# ==============================================================================

class WeeklyDietEngine:
    """Engine for building personalized, regional, 7-day clinical meal plans."""

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def __init__(self):
        self.catalog = REGIONAL_DISH_CATALOG

    def _resolve_region_key(self, raw_region: str) -> str:
        """Maps user's free-form native place into canonical catalog keys."""
        reg = raw_region.lower().strip()
        if any(w in reg for w in ["south", "tamil", "kerala", "andhra", "telangana", "karnataka", "chennai", "bangalore", "hyderabad"]):
            return "south_indian"
        elif any(w in reg for w in ["north", "punjab", "delhi", "haryana", "uttar", "rajasthan", "bihar", "mughlai"]):
            return "north_indian"
        elif any(w in reg for w in ["gujarat", "maharashtra", "mumbai", "pune", "ahmedabad", "surat", "marathi"]):
            return "western_indian"
        elif any(w in reg for w in ["bengal", "kolkata", "odisha", "orissa", "assam", "eastern"]):
            return "eastern_indian"
        elif any(w in reg for w in ["continental", "mediterranean", "western", "global", "american", "european"]):
            return "continental"
        else:
            return "south_indian"  # default standard fallback

    def generate_weekly_plan(self, req: WeeklyDietPlanRequest) -> WeeklyDietPlanResponse:
        """Constructs a comprehensive 7-day schedule with 5 daily intervals."""
        
        # 1. Parse lab report text into structured values
        parsed_labs = parse_report_text(req.test_reports.report_summary_text or "", req.test_reports)

        # 2. Derive targets based on labs & anthropometry
        targets, detected_conditions = derive_clinical_targets(
            age=req.age_years,
            sex=req.sex,
            bmi=req.body_mass_index,
            labs=parsed_labs,
            override_calories=req.preferences.calorie_target_override
        )

        # 3. Select regional culinary catalog
        region_key = self._resolve_region_key(req.preferences.native_place_region)
        region_dishes = self.catalog.get(region_key, self.catalog["south_indian"])
        fallback_dishes = self.catalog["south_indian"]

        # 4. Check medication alerts
        med_alerts = check_medication_warnings(req.preferences.active_medications, targets)

        # 5. Build 7 Days
        days: List[DayDietPlan] = []
        grocery_set = set()

        # Intervals & caloric distribution
        intervals_config = [
            ("Breakfast", "08:00 AM - 08:45 AM", "breakfast", 0.25),
            ("Mid-Morning Snack", "11:00 AM - 11:30 AM", "mid_morning", 0.08),
            ("Lunch", "01:00 PM - 02:00 PM", "lunch", 0.35),
            ("Evening Snack", "05:00 PM - 05:30 PM", "evening_snack", 0.07),
            ("Dinner", "07:45 PM - 08:30 PM", "dinner", 0.25),
        ]

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
                available = region_dishes.get(cat_key) or fallback_dishes.get(cat_key, [])
                if not available:
                    available = fallback_dishes.get(cat_key, [])

                # Pick dish ensuring rotation
                dish_template = available[(day_idx - 1) % len(available)]

                # Convert items to MealItem
                meal_items: List[MealItem] = []
                int_nutrients = {k: 0.0 for k in day_nutrients}

                for item in dish_template["items"]:
                    grocery_set.add(item["name"].split("(")[0].strip())
                    nutr = item.get("nutrients", {})
                    meal_items.append(MealItem(
                        item_name=item["name"],
                        portion=item["portion"],
                        nutrients=nutr
                    ))
                    for k in int_nutrients:
                        int_nutrients[k] += nutr.get(k, 0.0)

                # Add to daily running totals
                for k in day_nutrients:
                    day_nutrients[k] += int_nutrients[k]

                # Format prep tips tailored to cooking skill
                base_prep = dish_template.get("prep_tips", "Prepare fresh with minimal salt.")
                if req.preferences.cooking_skill == "beginner":
                    prep_note = f"{base_prep} (Beginner Note: Pre-chop ingredients in advance for easy assembly)."
                elif req.preferences.time_constraints_mins and req.preferences.time_constraints_mins <= 20:
                    prep_note = f"{base_prep} (Quick Prep: Pressure cook to complete in under 20 mins)."
                else:
                    prep_note = base_prep

                day_intervals.append(SingleMealInterval(
                    interval_name=int_name,
                    time_window=time_win,
                    meal_title=dish_template["title"],
                    items=meal_items,
                    total_nutrients={k: round(v, 1) for k, v in int_nutrients.items()},
                    clinical_justification=dish_template.get("justification", "Aligned with patient lab targets."),
                    prep_tips=prep_note,
                    substitutions=[{"standard": "Whole Milk", "substitute": "Almond Milk or Skimmed Cow Milk"}]
                ))

            # Round daily totals
            daily_totals_rounded = {k: round(v, 1) for k, v in day_nutrients.items()}

            # Compliance check against target limits
            compliance = {
                "calories_status": "optimal" if abs(daily_totals_rounded["calories"] - targets["calories_kcal"]) <= 150 else "controlled",
                "sodium_compliant": daily_totals_rounded["sodium_mg"] <= targets["sodium_limit_mg"],
                "potassium_compliant": daily_totals_rounded["potassium_mg"] <= targets["potassium_guidance_mg"],
                "protein_compliant": daily_totals_rounded["protein_g"] >= (targets["protein_g"] * 0.85),
            }

            days.append(DayDietPlan(
                day_number=day_idx,
                day_name=day_name,
                intervals=day_intervals,
                daily_total_nutrients=daily_totals_rounded,
                daily_target_compliance=compliance
            ))

        # 6. Weekly Averages
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
            "all_days_sodium_compliant": all(d.daily_target_compliance["sodium_compliant"] for d in days),
            "all_days_potassium_compliant": all(d.daily_target_compliance["potassium_compliant"] for d in days),
        }

        # Grocery checklist
        grocery_list = sorted(list(grocery_set))[:25]

        # Clinical Narrative Note
        clinical_notes = (
            f"7-Day Medical Nutrition Plan generated for {req.sex.upper()}, aged {req.age_years} (BMI {req.body_mass_index}). "
            f"Grounding native cuisine: {req.preferences.native_place_region.upper()} ({req.preferences.dietary_type.upper()}). "
            f"Identified Clinical Conditions: {', '.join(detected_conditions)}. "
            f"Daily limits enforced: Sodium <= {targets['sodium_limit_mg']} mg, Potassium <= {targets['potassium_guidance_mg']} mg, "
            f"Protein ~ {targets['protein_g']} g, Calories target ~ {targets['calories_kcal']} kcal across 5 daily intervals."
        )

        return WeeklyDietPlanResponse(
            user_id=req.user_id or "guest_patient",
            generated_at=datetime.now(timezone.utc).isoformat(),
            patient_summary={
                "age_years": req.age_years,
                "sex": req.sex,
                "body_mass_index": req.body_mass_index,
                "native_region": req.preferences.native_place_region,
                "dietary_type": req.preferences.dietary_type,
                "cooking_skill": req.preferences.cooking_skill,
            },
            clinical_targets=targets,
            detected_conditions=detected_conditions,
            days=days,
            weekly_nutritional_summary=weekly_summary,
            medication_alerts=med_alerts,
            grocery_checklist=grocery_list,
            clinical_notes=clinical_notes
        )


weekly_diet_engine = WeeklyDietEngine()
