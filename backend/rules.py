from typing import Any, Dict, Optional, List


def classify_risk_level(risk_score: float, thresholds: Optional[Dict] = None) -> str:
    t = thresholds or {}
    moderate = float(t.get("moderate", 0.4))
    high = float(t.get("high", 0.75))

    if risk_score >= high:
        return "high"
    if risk_score >= moderate:
        return "moderate"
    return "low"


def build_calibration_context(
    disease: str,
    risk_score: float,
    thresholds: Optional[Dict],
    top_factors: Optional[List[Dict[str, Any]]] = None,
    transformed_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t = thresholds or {}
    moderate = float(t.get("moderate", 0.4))
    high = float(t.get("high", 0.75))
    risk_level = classify_risk_level(risk_score, t)
    if risk_score >= high:
        threshold_band = "above_high"
    elif risk_score >= moderate:
        threshold_band = "moderate_to_high"
    else:
        threshold_band = "below_moderate"

    candidates = top_factors or []
    feature_values = transformed_features or {}
    highlighted: List[str] = []
    for item in candidates[:6]:
        feature = str(item.get("feature", "")).strip()
        if not feature:
            continue
        value = float(feature_values.get(feature, 0.0))
        rel_importance = float(item.get("relative_importance", 0.0))
        if value >= 0.5 or rel_importance >= 0.20:
            highlighted.append(feature)

    strictness = {"low": 1.0, "moderate": 1.1, "high": 1.25}.get(risk_level, 1.0)
    return {
        "disease": disease,
        "risk_level": risk_level,
        "threshold_band": threshold_band,
        "strictness_multiplier": strictness,
        "major_risk_factors": highlighted[:4],
    }


def build_comorbid_plan(
    diseases: List[str],
    risk_scores: Dict[str, float],
    profile: Dict,
    thresholds_dict: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Builds a personalized nutrition plan for a patient with multiple overlapping conditions
    (e.g., CKD + Hypertension + Diabetes), applying clinical priority precedence rules.
    """
    clean_diseases = [d.strip().lower() for d in diseases if d.strip().lower() in {"ckd", "hypertension", "diabetes"}]
    if not clean_diseases:
        clean_diseases = ["ckd"]

    has_ckd = "ckd" in clean_diseases
    has_htn = "hypertension" in clean_diseases
    has_diabetes = "diabetes" in clean_diseases

    base_calories = int(profile.get("calories_target", 2000))
    
    # Assess overall severity
    highest_risk = "low"
    for d in clean_diseases:
        score = risk_scores.get(d, 0.5)
        thresh = (thresholds_dict or {}).get(d, {})
        lvl = classify_risk_level(score, thresh)
        if lvl == "high":
            highest_risk = "high"
        elif lvl == "moderate" and highest_risk != "high":
            highest_risk = "moderate"

    # 1. Calorie targets
    if highest_risk == "high":
        calories_target = max(1200, base_calories - 300)
    elif highest_risk == "moderate":
        calories_target = max(1300, base_calories - 150)
    else:
        calories_target = base_calories

    # 2. Sodium: Strictest upper bound across guidelines
    if has_htn:
        sodium_limit = 1500 if highest_risk in ["moderate", "high"] else 1800
    elif has_ckd:
        sodium_limit = 1800 if highest_risk in ["moderate", "high"] else 2000
    else:
        sodium_limit = 2000

    # 3. Potassium: Clinical Precedence Rule (Renal safety overrides DASH potassium loading)
    if has_ckd:
        potassium_limit = 1800 if highest_risk == "high" else 2000
    elif has_htn:
        potassium_limit = 3500  # DASH high potassium target
    else:
        potassium_limit = 3000

    # 4. Phosphorus: CKD restriction
    phosphorus_limit_mg = 800 if (has_ckd and highest_risk == "high") else (1000 if has_ckd else None)

    # 5. Sugars & Carbs: Diabetes restriction
    sugar_limit_g = 20 if (has_diabetes and highest_risk == "high") else (30 if has_diabetes else None)
    fiber_target_g = 35 if (has_htn or has_diabetes) and highest_risk == "high" else 30 if (has_htn or has_diabetes) else 25
    fluid_target_ml = 1800 if (has_ckd and highest_risk == "high") else (2200 if has_ckd else None)

    protein_ratio = 0.18 if has_ckd else 0.20
    carb_ratio = 0.40 if has_diabetes else 0.45
    fat_ratio = max(0.25, 1.0 - protein_ratio - carb_ratio)

    diet_focus = []
    if has_ckd and has_htn:
        diet_focus.append("Strict dual sodium control with renal potassium safety override (<2,000 mg/d)")
    elif has_htn:
        diet_focus.append("DASH sodium restriction (<1,500 mg/d) with potassium support")
    elif has_ckd:
        diet_focus.append("KDOQI renal electrolyte and phosphorus moderation")

    if has_diabetes:
        diet_focus.append("ADA glycemic index regulation & sugar restriction (<20g/d)")
    if fiber_target_g >= 30:
        diet_focus.append("High dietary soluble fiber for metabolic and vascular protection")

    note = (
        f"Multi-condition comorbidity plan for {', '.join([d.upper() for d in clean_diseases])} "
        f"at {highest_risk.upper()} composite risk. Clinical precedence applied across KDOQI, DASH, and ADA protocols."
    )

    return {
        "calories_target": calories_target,
        "protein_target_g": int(calories_target * protein_ratio / 4),
        "carb_target_g": int(calories_target * carb_ratio / 4),
        "fat_target_g": int(calories_target * fat_ratio / 9),
        "sodium_limit_mg": sodium_limit,
        "potassium_limit_mg": potassium_limit,
        "sugar_limit_g": sugar_limit_g,
        "phosphorus_limit_mg": phosphorus_limit_mg,
        "fiber_target_g": fiber_target_g,
        "fluid_target_ml": fluid_target_ml,
        "diet_focus": diet_focus,
        "calibration_context": {
            "disease": "_".join(clean_diseases),
            "diseases": clean_diseases,
            "risk_level": highest_risk,
            "comorbidity": True,
        },
        "recommendation_note": note,
    }


def build_plan(
    disease: str,
    risk_score: float,
    profile: Dict,
    thresholds: Optional[Dict] = None,
    calibration_context: Optional[Dict[str, Any]] = None,
    diseases: Optional[List[str]] = None,
) -> Dict:
    # Check for multi-disease comorbidity
    if diseases and len(diseases) > 1:
        risk_scores = {d: risk_score for d in diseases}
        return build_comorbid_plan(diseases, risk_scores, profile)

    if "_" in disease and disease not in ["ckd", "hypertension", "diabetes"]:
        d_list = disease.split("_")
        risk_scores = {d: risk_score for d in d_list}
        return build_comorbid_plan(d_list, risk_scores, profile)

    base_calories = int(profile.get("calories_target", 2000))
    context = calibration_context or build_calibration_context(disease, risk_score, thresholds)
    risk_level = context.get("risk_level", classify_risk_level(risk_score, thresholds))
    threshold_band = str(context.get("threshold_band", "unknown"))
    major_factors = list(context.get("major_risk_factors", []))

    diet_focus = []
    sugar_limit_g = None
    phosphorus_limit_mg = None
    fiber_target_g = None
    fluid_target_ml = None

    if risk_level == "high":
        calories_target = max(1200, base_calories - 300)
        sodium_limit = 1500
        potassium_limit = 1800 if disease == "ckd" else 2500
        note = "High-risk profile: stricter disease-specific diet control and closer adherence monitoring advised."
    elif risk_level == "moderate":
        calories_target = max(1300, base_calories - 150)
        sodium_limit = 1800
        potassium_limit = 2000 if disease == "ckd" else 3000
        note = "Moderate risk: controlled intake and disease-aware meal planning recommended."
    else:
        calories_target = base_calories
        sodium_limit = 2000
        potassium_limit = 2500 if disease == "ckd" else 3500
        note = "Low risk: maintain balanced diet and routine meal logging."

    if disease == "ckd":
        phosphorus_limit_mg = 800 if risk_level == "high" else 1000 if risk_level == "moderate" else 1200
        fluid_target_ml = 1800 if risk_level == "high" else 2200 if risk_level == "moderate" else 2500
        diet_focus = [
            "Limit sodium aggressively",
            "Watch potassium-rich foods closely",
            "Moderate protein portions",
            "Prefer lower-phosphorus foods",
        ]
    elif disease == "hypertension":
        fiber_target_g = 35 if risk_level == "high" else 30 if risk_level == "moderate" else 25
        diet_focus = [
            "Reduce sodium and packaged foods",
            "Prefer high-fiber meals",
            "Control calories for blood-pressure support",
            "Keep meal timing regular",
        ]
    elif disease == "diabetes":
        sugar_limit_g = 20 if risk_level == "high" else 30 if risk_level == "moderate" else 40
        fiber_target_g = 32 if risk_level == "high" else 28 if risk_level == "moderate" else 24
        diet_focus = [
            "Tighten carbohydrate quality and portion control",
            "Lower added sugar intake",
            "Increase fiber-rich foods",
            "Prefer steady meal spacing to reduce glucose spikes",
        ]

    protein_ratio = 0.18 if disease == "ckd" and risk_level == "high" else 0.20
    carb_ratio = 0.40 if disease == "diabetes" and risk_level == "high" else 0.42 if disease == "diabetes" else 0.45
    fat_ratio = max(0.25, 1.0 - protein_ratio - carb_ratio)

    if threshold_band == "above_high":
        sodium_limit = int(max(1200, round(sodium_limit * 0.9)))
        if disease == "diabetes":
            sugar_limit_g = int((sugar_limit_g or 20) * 0.85)
        if disease == "ckd":
            phosphorus_limit_mg = int((phosphorus_limit_mg or 800) * 0.9)

    if major_factors:
        focus_line = "Key modeled risk factors: " + ", ".join(major_factors)
        diet_focus = [focus_line] + diet_focus
        note = f"{note} Diet calibrated using threshold band '{threshold_band}' and model factor profile."
    else:
        note = f"{note} Diet calibrated using threshold band '{threshold_band}'."

    return {
        "calories_target": calories_target,
        "protein_target_g": int(calories_target * protein_ratio / 4),
        "carb_target_g": int(calories_target * carb_ratio / 4),
        "fat_target_g": int(calories_target * fat_ratio / 9),
        "sodium_limit_mg": sodium_limit,
        "potassium_limit_mg": potassium_limit,
        "sugar_limit_g": sugar_limit_g,
        "phosphorus_limit_mg": phosphorus_limit_mg,
        "fiber_target_g": fiber_target_g,
        "fluid_target_ml": fluid_target_ml,
        "diet_focus": diet_focus,
        "calibration_context": context,
        "recommendation_note": note,
    }


def assess_meal_deviation(planned_calories: int, consumed_calories: int, threshold_percent: float = 15.0) -> Dict[str, Any]:
    if planned_calories <= 0:
        return {
            "deviation_flag": False,
            "deviation_percent": 0.0,
            "alert_created": False,
            "alert_message": None,
        }

    diff = consumed_calories - planned_calories
    dev_pct = round(abs(diff) / planned_calories * 100.0, 2)
    flag = dev_pct >= threshold_percent

    msg = None
    if flag:
        direction = "above" if diff > 0 else "below"
        msg = f"Meal calorie intake was {dev_pct}% {direction} planned target."

    return {
        "deviation_flag": flag,
        "deviation_percent": dev_pct,
        "alert_created": flag,
        "alert_message": msg,
    }
