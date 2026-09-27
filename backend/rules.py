from typing import Any, Dict, Optional, List


def classify_risk_level(risk_score: float, thresholds: Optional[Dict] = None) -> str:
    t = thresholds or {}
    moderate = float(t.get("moderate", 0.50))
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
    moderate = float(t.get("moderate", 0.50))
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


def calculate_ckd_epi_egfr(sc: float, age: float, sex: str) -> float:
    """Calculate estimated GFR using the 2021 CKD-EPI Creatinine equation (without race)."""
    if sc <= 0:
        return 90.0
    s = str(sex).lower()
    k, alpha, sex_factor = (0.7, -0.241, 1.012) if s == "female" else (0.9, -0.302, 1.0)
    ratio = sc / k
    val = 142.0 * (ratio ** (alpha if ratio < 1.0 else -1.200)) * (0.9938 ** age) * sex_factor
    return round(float(val), 1)


def calibrate_disease_risk(disease: str, raw_score: float, raw_inputs: Dict[str, Any]) -> float:
    """
    Calibrates raw ML model probabilities with modern continuous clinical diagnostic guidelines
    (KDIGO 2024 for CKD, AHA/ACC 2023 for Hypertension, ADA 2024 for Type 2 Diabetes).
    
    Provides smooth, continuous sensitivity so that even small adjustments in biomarkers
    (BMI, Blood Pressure, Fasting Glucose, Serum Creatinine, eGFR, Age) are calculated with
    high precision without step-function plateaus or leaf quantization artifacts.
    """
    import numpy as np
    d = disease.lower().strip()

    sex = str(raw_inputs.get("sex", "male")).lower()
    age = float(raw_inputs.get("age_years", 50) or 50)
    bmi = float(raw_inputs.get("body_mass_index", 24.0) or 24.0)
    sbp = float(raw_inputs.get("systolic_bp_mmhg", 120) or 120)
    dbp = float(raw_inputs.get("diastolic_bp_mmhg", 80) or 80)
    fbg = float(raw_inputs.get("fasting_glucose_mg_dl", 100) or 100)
    hba1c = float(raw_inputs.get("hba1c_pct")) if raw_inputs.get("hba1c_pct") is not None else None
    sc = float(raw_inputs.get("serum_creatinine_mg_dl")) if raw_inputs.get("serum_creatinine_mg_dl") is not None else None
    egfr = float(raw_inputs.get("egfr_ml_min")) if raw_inputs.get("egfr_ml_min") is not None else None
    al = float(raw_inputs.get("urine_albumin_dipstick")) if raw_inputs.get("urine_albumin_dipstick") is not None else 0.0
    chol = float(raw_inputs.get("total_cholesterol_mg_dl", 190.0) or 190.0) if raw_inputs.get("total_cholesterol_mg_dl") is not None else 190.0
    smoker = bool(raw_inputs.get("current_smoker", False))

    if d == "ckd":
        creat_normal_upper = 1.2 if sex == "male" else 1.0
        if egfr is None and sc is not None and sc > 0:
            egfr = calculate_ckd_epi_egfr(float(sc), age, sex)
        elif egfr is None:
            egfr = 95.0

        # Continuous eGFR risk function according to KDIGO staging:
        # eGFR >= 90: Pristine (Stage 1), base risk ~0.04
        # 60 <= eGFR < 90: Stage 2 mild reduction, risk smoothly scales from 0.045 to 0.48
        # 30 <= eGFR < 60: Stage 3 clinical CKD, risk smoothly scales from 0.52 to 0.84
        # eGFR < 30: Stage 4-5 severe impairment, risk smoothly scales from 0.85 to 0.98
        if egfr >= 90.0:
            base_risk = 0.04 + max(0.0, 100.0 - egfr) * 0.0004
        elif egfr >= 60.0:
            frac = (90.0 - egfr) / 30.0
            base_risk = 0.045 + frac * 0.435
        elif egfr >= 30.0:
            frac = (60.0 - egfr) / 30.0
            base_risk = 0.52 + frac * 0.32
        else:
            frac = (30.0 - max(8.0, egfr)) / 22.0
            base_risk = 0.85 + frac * 0.13

        # Continuous SBP & DBP renal hemodynamic pressure adjustments
        delta_bp = 0.0
        if sbp > 115.0:
            delta_bp += (sbp - 115.0) * 0.0018
        else:
            delta_bp -= min(15.0, 115.0 - sbp) * 0.0006
        if dbp > 75.0:
            delta_bp += (dbp - 75.0) * 0.0014

        # Continuous Glycemic microvascular stress
        delta_glyc = 0.0
        if fbg > 85.0:
            if fbg <= 125.0:
                delta_glyc += (fbg - 85.0) * 0.0012
            else:
                delta_glyc += (125.0 - 85.0) * 0.0012 + (fbg - 125.0) * 0.0020
        if hba1c is not None and hba1c > 5.2:
            delta_glyc += (hba1c - 5.2) * 0.030

        # Continuous BMI hyperfiltration stress
        delta_bmi = 0.0
        if bmi > 22.0:
            delta_bmi += (bmi - 22.0) * 0.0030

        # Continuous Age nephron reserve factor
        delta_age = 0.0
        if age > 35.0:
            delta_age += (age - 35.0) * 0.0007

        # Urine Albumin Dipstick
        delta_al = max(0.0, al) * 0.14

        # Creatinine direct upper bound safety check
        delta_sc = 0.0
        if sc is not None and sc > creat_normal_upper:
            delta_sc += min(0.30, (sc - creat_normal_upper) * 0.25)

        # Electrolyte tubular excretion & intravascular osmolar stress
        delta_lytes = 0.0
        sod = float(raw_inputs.get("serum_sodium_meq_l", 140.0) or 140.0) if raw_inputs.get("serum_sodium_meq_l") is not None else None
        k_val = float(raw_inputs.get("serum_potassium_meq_l", 4.2) or 4.2) if raw_inputs.get("serum_potassium_meq_l") is not None else None
        if sod is not None:
            if sod > 145.0:
                delta_lytes += (sod - 145.0) * 0.0050  # Intraglomerular hypervolemic tension
            elif sod < 135.0:
                delta_lytes += (135.0 - sod) * 0.0040  # Dilutional hyponatremia
        if k_val is not None:
            if k_val > 5.0:
                delta_lytes += (k_val - 5.0) * 0.0650  # Impaired distal nephron clearance
            elif k_val < 3.5:
                delta_lytes += (3.5 - k_val) * 0.0250  # Hypokalemia

        total_ckd = base_risk + delta_bp + delta_glyc + delta_bmi + delta_age + delta_al + delta_sc + delta_lytes
        return round(float(np.clip(total_ckd, 0.01, 0.99)), 4)

    elif d == "hypertension":
        # Continuous clinical calibration for Hypertension
        # Normotensive AHA baseline: SBP 115, DBP 75, BMI 22.0, Age 35
        delta_bp = 0.0
        if sbp > 115.0:
            delta_bp += (sbp - 115.0) * 0.0055
        else:
            delta_bp += (sbp - 115.0) * 0.0015

        if dbp > 75.0:
            delta_bp += (dbp - 75.0) * 0.0038
        else:
            delta_bp += (dbp - 75.0) * 0.0010

        delta_bmi = 0.0
        if bmi > 22.0:
            delta_bmi += (bmi - 22.0) * 0.0050

        delta_age = 0.0
        if age > 35.0:
            delta_age += (age - 35.0) * 0.0012

        delta_meta = 0.0
        if fbg > 95.0:
            delta_meta += (fbg - 95.0) * 0.0007
        if chol > 190.0:
            delta_meta += (chol - 190.0) * 0.0003
        if smoker:
            delta_meta += 0.05

        # Serum Sodium intravascular hypervolemia gradient
        # Normal reference: 135-145 mEq/L (median 140). Excess sodium expands plasma volume and raises systemic vascular resistance.
        delta_sod = 0.0
        sod = float(raw_inputs.get("serum_sodium_meq_l", 140.0) or 140.0) if raw_inputs.get("serum_sodium_meq_l") is not None else None
        if sod is not None:
            if sod > 140.0:
                delta_sod += (sod - 140.0) * 0.0075
            elif sod < 135.0:
                delta_sod -= min(0.04, (135.0 - sod) * 0.0020)

        total_htn = raw_score + delta_bp + delta_bmi + delta_age + delta_meta + delta_sod
        return round(float(np.clip(total_htn, 0.01, 0.99)), 4)

    elif d == "diabetes":
        # Continuous clinical calibration for Type 2 Diabetes
        # Normal ADA baseline: Fasting Glucose 85, HbA1c 5.0, BMI 22.0, Age 35
        delta_fbg = 0.0
        if fbg <= 99.0:
            delta_fbg += max(0.0, fbg - 85.0) * 0.0022
        elif fbg <= 125.0:
            # Impaired Fasting Glucose (Prediabetes)
            delta_fbg += (99.0 - 85.0) * 0.0022 + (fbg - 99.0) * 0.0090
        else:
            # Overt Diabetes (>= 126 mg/dL)
            delta_fbg += (99.0 - 85.0) * 0.0022 + (125.0 - 99.0) * 0.0090 + 0.16 + (fbg - 125.0) * 0.0032

        delta_hba1c = 0.0
        if hba1c is not None:
            if hba1c <= 5.6:
                delta_hba1c += max(0.0, hba1c - 5.0) * 0.025
            elif hba1c <= 6.4:
                # Prediabetes
                delta_hba1c += (5.6 - 5.0) * 0.025 + (hba1c - 5.6) * 0.14
            else:
                # Overt Diabetes (>= 6.5%)
                delta_hba1c += (5.6 - 5.0) * 0.025 + (6.4 - 5.6) * 0.14 + 0.20 + (hba1c - 6.4) * 0.07

        delta_bmi = 0.0
        if bmi > 22.0:
            delta_bmi += (bmi - 22.0) * 0.0060

        delta_age = 0.0
        if age > 35.0:
            delta_age += (age - 35.0) * 0.0010

        delta_bp = 0.0
        if sbp > 120.0:
            delta_bp += (sbp - 120.0) * 0.0010

        total_dm = raw_score + delta_fbg + delta_hba1c + delta_bmi + delta_age + delta_bp
        return round(float(np.clip(total_dm, 0.01, 0.99)), 4)

    return round(float(np.clip(raw_score, 0.01, 0.99)), 4)


def explain_disease_risk(
    disease: str,
    risk_score: float,
    risk_level: str,
    raw_inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Directly explains the clinical result:
      - If HIGH: Why is it so, and What to do.
      - If MODERATE: Why is it so, and How to reduce it.
      - If LOW: What is working well (Good signals), and Steps to preserve it.
    """
    d = disease.lower().strip()
    age = float(raw_inputs.get("age_years", 50) or 50)
    sex = str(raw_inputs.get("sex", "male")).lower()
    bmi = float(raw_inputs.get("body_mass_index", 25.0) or 25.0)
    sbp = float(raw_inputs.get("systolic_bp_mmhg", 120.0) or 120.0)
    dbp = float(raw_inputs.get("diastolic_bp_mmhg", 80.0) or 80.0)
    fbg = float(raw_inputs.get("fasting_glucose_mg_dl", 100.0) or 100.0)
    hba1c = float(raw_inputs.get("hba1c_pct", 5.7) or 5.7) if raw_inputs.get("hba1c_pct") is not None else None
    sc = float(raw_inputs.get("serum_creatinine_mg_dl", 1.0) or 1.0) if raw_inputs.get("serum_creatinine_mg_dl") is not None else None
    egfr = float(raw_inputs.get("egfr_ml_min", 90.0) or 90.0) if raw_inputs.get("egfr_ml_min") is not None else None
    k_val = float(raw_inputs.get("serum_potassium_meq_l", 4.2) or 4.2) if raw_inputs.get("serum_potassium_meq_l") is not None else None
    sod_val = float(raw_inputs.get("serum_sodium_meq_l", 140.0) or 140.0) if raw_inputs.get("serum_sodium_meq_l") is not None else None
    smoker = bool(raw_inputs.get("current_smoker", False))
    chol = float(raw_inputs.get("total_cholesterol_mg_dl", 190.0) or 190.0) if raw_inputs.get("total_cholesterol_mg_dl") is not None else None

    pct_val = round(risk_score * 100, 1)
    pct_str = f"{pct_val:.1f}%"
    disease_titles = {"ckd": "Chronic Kidney Disease", "hypertension": "Hypertension", "diabetes": "Type 2 Diabetes"}
    d_name = disease_titles.get(d, d.upper())

    why_reasons: List[str] = []
    action_steps: List[str] = []

    # ──────────────────────────────────────────────────────────────────────────
    # 1. CHRONIC KIDNEY DISEASE (CKD)
    # ──────────────────────────────────────────────────────────────────────────
    if d == "ckd":
        creat_thresh = 1.2 if sex == "male" else 1.0

        if risk_level == "high":
            why_title = "Why Is It High? (Primary Clinical Drivers)"
            action_title = "What To Do (Urgent Clinical & Dietary Actions)"

            if egfr is not None and egfr < 45:
                why_reasons.append(f"Severely reduced eGFR ({egfr:.0f} mL/min): Indicates Stage 3b-5 filtration impairment; kidneys cannot filter metabolic waste adequately.")
            elif egfr is not None and egfr < 60:
                why_reasons.append(f"Compromised eGFR ({egfr:.0f} mL/min): Significant loss of filtration capacity below the Stage 3 CKD threshold.")
            if sc is not None and sc > creat_thresh:
                why_reasons.append(f"Elevated Serum Creatinine ({sc:.1f} mg/dL): Well above the normal {sex} limit ({creat_thresh} mg/dL), confirming nitrogenous waste buildup.")
            if sbp >= 140 or dbp >= 90:
                why_reasons.append(f"Stage 2 Hypertension ({sbp:.0f}/{dbp:.0f} mmHg): Transmits damaging capillary hydrostatic shear pressure into renal glomeruli.")
            if (hba1c is not None and hba1c >= 6.5) or fbg >= 126:
                why_reasons.append(f"Diabetic Glycemia (HbA1c {hba1c if hba1c is not None else 6.5:.1f}% / Glucose {fbg:.0f} mg/dL): Accelerates microvascular glomerular basement membrane thickening.")
            if k_val is not None and k_val > 5.0:
                why_reasons.append(f"Elevated Potassium ({k_val:.1f} mEq/L): Hyperkalemia indicates impaired distal tubular electrolyte excretion.")
            if sod_val is not None and sod_val > 145:
                why_reasons.append(f"Hypernatremia ({sod_val:.0f} mEq/L): Excess sodium retention expands intravascular volume and stresses damaged nephrons.")
            elif sod_val is not None and sod_val < 135:
                why_reasons.append(f"Hyponatremia ({sod_val:.0f} mEq/L): Subnormal sodium signals impaired free water clearance or over-diuresis.")
            if not why_reasons:
                why_reasons.append(f"Multiple compounding biomarkers indicate advanced functional renal strain (Score: {pct_str}).")

            action_steps = [
                "Nephrology Consultation: Schedule an urgent clinical evaluation with a nephrologist for comprehensive staging and 24-hr urine albumin quantification.",
                "Restrict Sodium to < 1,500 mg/day: Eliminates excess fluid retention and relieves intraglomerular capillary hydrostatic pressure.",
                "Watch Potassium (< 2,000 mg/day) & Phosphorus (< 800 mg/day): Prevents life-threatening cardiac arrhythmias and mineral-bone disease.",
                "Medication Safety Audit: Immediately avoid all over-the-counter NSAID painkillers (ibuprofen, naproxen) and review ACEi/ARB dosages with your doctor.",
                "Moderate Protein Intake (0.6-0.8 g/kg/day): Eases the kidney's nitrogenous filtration workload while maintaining lean muscle tissue.",
            ]

        elif risk_level == "moderate":
            why_title = "Why Is It Moderate? (Key Contributing Factors)"
            action_title = "How To Reduce It (Targeted Corrective Steps)"

            if egfr is not None and 60 <= egfr < 90:
                why_reasons.append(f"Borderline eGFR ({egfr:.0f} mL/min): Reflects mild filtration decline below the ideal baseline (>= 90 mL/min).")
            if sc is not None and sc >= creat_thresh - 0.1:
                why_reasons.append(f"Serum Creatinine ({sc:.1f} mg/dL): Sits at or near the upper physiological margin for adult renal clearance.")
            if (130 <= sbp < 140) or (80 <= dbp < 90):
                why_reasons.append(f"Stage 1 Hypertension ({sbp:.0f}/{dbp:.0f} mmHg): Creates ongoing microvascular resistance against kidney filtration units.")
            if (hba1c is not None and 5.7 <= hba1c < 6.5) or (100 <= fbg < 126):
                why_reasons.append(f"Prediabetic Glycemic Levels (HbA1c {hba1c if hba1c is not None else 5.7:.1f}% / Glucose {fbg:.0f} mg/dL): Puts early metabolic stress on renal podocytes.")
            if age >= 50:
                why_reasons.append(f"Age Factor ({int(age)} years): Natural gradual age-related loss of reserve nephrons.")
            if not why_reasons:
                why_reasons.append(f"Borderline clearance values and metabolic markers suggest early filtration vulnerability (Score: {pct_str}).")

            action_steps = [
                "Target Blood Pressure Below 120/80 mmHg: Adopt the DASH dietary protocol and reduce salt to under 1,800 mg/day to protect kidney arterioles.",
                "Stabilize Blood Sugar: Choose low-glycemic, high-fiber whole foods (millets, oats, vegetables) to prevent microvascular glucotoxicity.",
                "Maintain Steady Daily Hydration: Drink 1.8 to 2.2 liters of water daily to support continuous kidney perfusion (unless fluid-restricted).",
                "150 Mins/Week Moderate Activity: Regular brisk walking or cycling improves vascular endothelial nitric oxide dilation and insulin sensitivity.",
                "Re-Test in 90 Days: Check your metabolic panel (eGFR, Creatinine, Urine Albumin) after 3 months of dietary adjustments to verify stabilization.",
            ]

        else: # low
            why_title = "What Is Working Well (Positive Health Signals)"
            action_title = "Steps To Preserve It (Daily Habits to Maintain Health)"

            if egfr is not None and egfr >= 90:
                why_reasons.append(f"Optimal eGFR ({egfr:.0f} mL/min): Indicates robust, healthy glomerular filtration capacity (KDIGO Stage 1).")
            if sc is not None and sc <= (0.9 if sex == "female" else 1.0):
                why_reasons.append(f"Normal Serum Creatinine ({sc:.1f} mg/dL): Demonstrates clean and efficient metabolic waste clearance.")
            if sbp < 120 and dbp < 80:
                why_reasons.append(f"Optimal Blood Pressure ({sbp:.0f}/{dbp:.0f} mmHg): Shields delicate renal filtration capillaries from hypertensive shear stress.")
            if fbg < 100:
                why_reasons.append(f"Healthy Fasting Glucose ({fbg:.0f} mg/dL): Prevents glucotoxicity and preserves renal podocyte integrity.")
            if k_val is not None and 3.5 <= k_val <= 5.0:
                why_reasons.append(f"Balanced Potassium ({k_val:.1f} mEq/L): Confirms intact tubular electrolyte and fluid homeostasis.")
            elif k_val is not None and k_val > 5.0:
                why_reasons.append(f"Notice — Elevated Potassium ({k_val:.1f} mEq/L): Early distal tubular clearance strain detected.")
            if sod_val is not None and 135 <= sod_val <= 145:
                why_reasons.append(f"Balanced Serum Sodium ({sod_val:.0f} mEq/L): Confirms healthy extracellular fluid balance and normal natriuresis.")
            elif sod_val is not None and sod_val > 145:
                why_reasons.append(f"Notice — Elevated Sodium ({sod_val:.0f} mEq/L): Early sodium retention adds subtle intraglomerular hemodynamic strain.")
            if not why_reasons:
                why_reasons.append(f"All core clinical parameters for kidney function are comfortably within safe baseline limits (Score: {pct_str}).")

            action_steps = [
                "Stay Well-Hydrated: Drink pure water regularly throughout the day to help your kidneys flush out metabolic byproducts effortlessly.",
                "Keep Sodium Balanced (< 2,000 mg/day): Cook primarily with fresh ingredients, herbs, and spices rather than high-sodium packaged seasonings.",
                "Avoid Overusing NSAID Painkillers: Minimize frequent use of over-the-counter ibuprofen or naproxen, which can cause acute tubular stress.",
                "Routine Annual Checkups: Have an annual basic metabolic panel (BMP) and urinalysis during routine wellness checkups to ensure kidneys remain healthy.",
            ]
            if sod_val is not None and sod_val > 145:
                action_steps[1] = "Strict Sodium Control (< 1,500 mg/day): Your serum sodium is elevated (> 145 mEq/L). Limit salt to prevent volume expansion and renal capillary stress."

    # ──────────────────────────────────────────────────────────────────────────
    # 2. HYPERTENSION
    # ──────────────────────────────────────────────────────────────────────────
    elif d == "hypertension":
        if risk_level == "high":
            why_title = "Why Is It High? (Primary Clinical Causes)"
            action_title = "What To Do (Urgent Clinical & Dietary Actions)"

            if sbp >= 140 or dbp >= 90:
                why_reasons.append(f"Resting Blood Pressure ({sbp:.0f}/{dbp:.0f} mmHg): Meets AHA/ACC criteria for Stage 2 Essential Hypertension.")
            if bmi >= 30.0:
                why_reasons.append(f"Obese BMI ({bmi:.1f} kg/m2): Substantially increases cardiac output demand and systemic peripheral resistance.")
            elif bmi >= 25.0:
                why_reasons.append(f"Overweight BMI ({bmi:.1f} kg/m2): Adds ongoing cardiovascular and sympathetic vascular strain.")
            if smoker:
                why_reasons.append("Active Tobacco Smoking: Nicotine stimulates continuous sympathetic vasoconstriction and endothelial injury.")
            if chol is not None and chol >= 200:
                why_reasons.append(f"Elevated Total Cholesterol ({chol:.0f} mg/dL): Promotes arterial stiffening and atherogenesis.")
            if sod_val is not None and sod_val > 145:
                why_reasons.append(f"Elevated Serum Sodium ({sod_val:.0f} mEq/L): Hypernatremia promotes intravascular fluid retention and raises vascular wall tension.")
            if age >= 55:
                why_reasons.append(f"Age Factor ({int(age)} years): Age-associated loss of arterial elastin and vascular compliance.")
            if not why_reasons:
                why_reasons.append(f"High systemic cardiovascular tension and arterial resistance profile (Score: {pct_str}).")

            action_steps = [
                "Physician Evaluation: Consult your primary care physician or cardiologist promptly to evaluate prescription antihypertensive therapy.",
                "Strict DASH Sodium Restriction (< 1,500 mg/day): Eliminate added table salt, processed snacks, canned soups, and restaurant takeout.",
                "Daily Home Blood Pressure Log: Measure blood pressure twice daily (morning and evening) in a calm seated position and log the readings.",
                "Quit Tobacco & Cut Caffeine: Cease all tobacco products immediately to restore endothelial nitric-oxide vascular dilation.",
                "Potassium & Magnesium Rich Foods: Eat more dark leafy greens, avocados, lentils, and pumpkin seeds (provided renal function is normal).",
            ]

        elif risk_level == "moderate":
            why_title = "Why Is It Moderate? (Key Contributing Factors)"
            action_title = "How To Reduce It (Targeted Corrective Steps)"

            if (120 <= sbp < 140) or (80 <= dbp < 90):
                why_reasons.append(f"Blood Pressure ({sbp:.0f}/{dbp:.0f} mmHg): Sits in the Elevated or Stage 1 Hypertension range.")
            if 25.0 <= bmi < 30.0:
                why_reasons.append(f"Overweight BMI ({bmi:.1f} kg/m2): Creates moderate extra resistance against arterial blood flow.")
            if fbg >= 100 or (hba1c is not None and hba1c >= 5.7):
                why_reasons.append(f"Elevated Fasting Glycemia ({fbg:.0f} mg/dL): Early insulin resistance promotes arterial stiffness and sodium retention.")
            if chol is not None and chol >= 190:
                why_reasons.append(f"Borderline Cholesterol ({chol:.0f} mg/dL): Contributes to early vascular wall resistance.")
            if not why_reasons:
                why_reasons.append(f"Early vascular resistance markers indicate pre-hypertensive drift (Score: {pct_str}).")

            action_steps = [
                "5%-7% Weight Reduction: Losing 3-5 kg can directly lower your systolic pressure by 4 to 8 mmHg.",
                "Reduce Sodium Under 1,800 mg/day: Check nutrition labels for hidden sodium and flavor meals with lemon, garlic, and vinegar.",
                "30 Minutes of Daily Brisk Walking: Regular aerobic exercise naturally prompts blood vessels to relax and dilate.",
                "Manage Stress & Sleep: Ensure 7-8 hours of sound sleep and take 10 minutes daily for calming breathwork to reduce sympathetic tone.",
                "Weekly BP Tracking: Check resting blood pressure once a week to verify whether dietary adjustments are moving it below 120/80 mmHg.",
            ]

        else: # low
            why_title = "What Is Working Well (Positive Health Signals)"
            action_title = "Steps To Preserve It (Daily Habits to Maintain Health)"

            if sbp < 120 and dbp < 80:
                why_reasons.append(f"Optimal Blood Pressure ({sbp:.0f}/{dbp:.0f} mmHg): Perfectly situated in the ideal AHA/ACC normotensive target (< 120/80 mmHg).")
            if 18.5 <= bmi < 25.0:
                why_reasons.append(f"Healthy BMI ({bmi:.1f} kg/m2): Protects against obesity-induced arterial resistance and cardiac overload.")
            if not smoker:
                why_reasons.append("Non-Smoker: Healthy vascular endothelium free from tobacco-induced vasoconstriction.")
            if fbg < 100:
                why_reasons.append(f"Normal Fasting Glucose ({fbg:.0f} mg/dL): Protects microvascular compliance and nitric oxide bioavailability.")
            if sod_val is not None and sod_val > 145:
                why_reasons.append(f"Notice — Elevated Sodium ({sod_val:.0f} mEq/L): While BP is currently low, hypernatremia expands intravascular volume and increases hypertensive drift.")
            elif sod_val is not None and 135 <= sod_val <= 145:
                why_reasons.append(f"Balanced Serum Sodium ({sod_val:.0f} mEq/L): Healthy fluid balance avoids excess vascular volume expansion.")
            if not why_reasons:
                why_reasons.append(f"Resting arterial tension and cardiovascular biomarkers are in the optimal healthy range (Score: {pct_str}).")

            action_steps = [
                "Continue DASH-Style Nutrition: Keep enjoying meals rich in fresh vegetables, whole grains, fruits, and lean protein.",
                "Stay Active: Maintain regular weekly cardiovascular exercise to preserve arterial wall elasticity as you age.",
                "Preserve Healthy Weight: Keep body weight steady in the normal BMI range through balanced, mindful eating.",
                "Routine BP Checks: Check blood pressure once every 6 months during routine visits to catch any subtle drift early.",
            ]
            if sod_val is not None and sod_val > 145:
                action_steps.insert(0, "Reduce Dietary Salt: Serum sodium is elevated (> 145 mEq/L). Limit table salt and processed foods to avoid volume-dependent blood pressure rise.")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. TYPE 2 DIABETES
    # ──────────────────────────────────────────────────────────────────────────
    else:
        if risk_level == "high":
            why_title = "Why Is It High? (Primary Clinical Causes)"
            action_title = "What To Do (Urgent Clinical & Dietary Actions)"

            if fbg >= 126:
                why_reasons.append(f"Fasting Glucose ({fbg:.0f} mg/dL): Exceeds diagnostic threshold (>= 126 mg/dL) for overt Type 2 Diabetes.")
            if hba1c is not None and hba1c >= 6.5:
                why_reasons.append(f"HbA1c ({hba1c:.1f}%): Meets diagnostic criterion (>= 6.5%) for chronic 90-day glycemic dysregulation.")
            if bmi >= 30.0:
                why_reasons.append(f"Obese BMI ({bmi:.1f} kg/m2): Triggers severe peripheral insulin receptor resistance via visceral adipose tissue.")
            elif bmi >= 25.0:
                why_reasons.append(f"Overweight BMI ({bmi:.1f} kg/m2): Drives peripheral glucose disposal resistance.")
            if sbp >= 130 or dbp >= 80:
                why_reasons.append(f"Concurrent Hypertension ({sbp:.0f}/{dbp:.0f} mmHg): Forms part of the Metabolic Syndrome triad compounding vascular risk.")
            if not why_reasons:
                why_reasons.append(f"Significant clinical indicators of insulin resistance and glycemic dysregulation (Score: {pct_str}).")

            action_steps = [
                "Medical / Endocrinology Consultation: Schedule an appointment to establish formal glycemic management and medication guidance.",
                "Strict Carbohydrate & Sugar Restriction: Restrict added sugars to < 15g/day; eliminate sweetened sodas, candies, and refined white flour.",
                "Self-Monitor Blood Glucose: Check fasting and 2-hour postprandial blood sugar levels to identify which foods cause sharp spikes.",
                "Fiber-First Meal Sequencing: Always pair complex carbs with soluble fiber (chia, flax, leafy greens) and lean protein to flatten the glucose curve.",
                "Comprehensive Diabetic Screening: Schedule a baseline annual diabetic dilated eye exam, comprehensive foot exam, and kidney microalbumin check.",
            ]

        elif risk_level == "moderate":
            why_title = "Why Is It Moderate? (Key Contributing Factors)"
            action_title = "How To Reduce It (Targeted Corrective Steps)"

            if 100 <= fbg < 126:
                why_reasons.append(f"Impaired Fasting Glucose ({fbg:.0f} mg/dL): Sits in the Prediabetes range (100-125 mg/dL), indicating early beta-cell strain.")
            if hba1c is not None and 5.7 <= hba1c < 6.5:
                why_reasons.append(f"Prediabetic HbA1c ({hba1c:.1f}%): Falls into the prediabetes category (5.7-6.4%), reflecting early insulin resistance.")
            if 25.0 <= bmi < 30.0:
                why_reasons.append(f"Overweight BMI ({bmi:.1f} kg/m2): Excess adiposity promotes low-grade inflammation that desensitizes insulin receptors.")
            if sbp >= 130 or dbp >= 80:
                why_reasons.append(f"Elevated Blood Pressure ({sbp:.0f}/{dbp:.0f} mmHg): Overlapping Metabolic Syndrome component.")
            if age >= 45:
                why_reasons.append(f"Age Factor ({int(age)} years): Age-associated physiological decline in pancreatic beta-cell sensitivity.")
            if not why_reasons:
                why_reasons.append(f"Early metabolic markers suggest prediabetic insulin resistance (Score: {pct_str}).")

            action_steps = [
                "Target 5%-10% Weight Loss: The Diabetes Prevention Program (DPP) proved that 7% weight loss cuts progression to diabetes by 58%.",
                "Swap High-GI Foods for Low-GI Alternatives: Replace white rice, white bread, and potatoes with millets, steel-cut oats, quinoa, and legumes.",
                "Boost Soluble Fiber (>= 30g/day): Eat plenty of lentils, beans, broccoli, and flaxseed to slow down carbohydrate absorption in the gut.",
                "10-Minute Post-Meal Walks: A light 10-15 minute walk right after lunch and dinner helps muscles absorb glucose without needing extra insulin.",
                "Repeat Blood Tests in 90 Days: Recheck HbA1c and fasting blood sugar after 3 months of dietary intervention to confirm reversal back to normal.",
            ]

        else: # low
            why_title = "What Is Working Well (Positive Health Signals)"
            action_title = "Steps To Preserve It (Daily Habits to Maintain Health)"

            if 70 <= fbg < 100:
                why_reasons.append(f"Optimal Fasting Glucose ({fbg:.0f} mg/dL): Demonstrates intact basal insulin secretion and normal hepatic glucose regulation.")
            if hba1c is not None and hba1c < 5.7:
                why_reasons.append(f"Normal HbA1c ({hba1c:.1f}%): Confirms sustained 90-day non-diabetic glycemic stability.")
            if 18.5 <= bmi < 25.0:
                why_reasons.append(f"Healthy BMI ({bmi:.1f} kg/m2): Protects against visceral fat deposition in liver and muscle tissue.")
            if sbp < 120 and dbp < 80:
                why_reasons.append(f"Normotensive BP ({sbp:.0f}/{dbp:.0f} mmHg): Confirms absence of metabolic syndrome vascular resistance.")
            if not why_reasons:
                why_reasons.append(f"Glycemic control and metabolic parameters are within ideal non-diabetic bounds (Score: {pct_str}).")

            action_steps = [
                "Continue Balanced Whole Foods: Build meals around unrefined complex carbohydrates, vegetables, and lean protein sources.",
                "Limit Hidden Added Sugars: Keep sweets, sugary drinks, and processed snacks as occasional treats rather than daily staples.",
                "Resistance Training + Walking: Strength training preserves skeletal muscle mass, which is your body's largest glucose disposal reservoir.",
                "Annual Wellness Checkup: Get your fasting glucose and HbA1c tested once a year during routine checkups to detect subtle shifts early.",
            ]

    status_label = f"{risk_level.upper()} RISK"
    clinical_summary = f"{d_name} risk is assessed as {status_label} ({pct_str}). {why_reasons[0]}"

    return {
        "disease": d,
        "disease_name": d_name,
        "risk_score_pct": pct_val,
        "risk_level": risk_level,
        "status_label": status_label,
        "why_title": why_title,
        "why_reasons": why_reasons,
        "action_title": action_title,
        "action_steps": action_steps,
        # Legacy fields
        "risk_drivers": why_reasons if risk_level != "low" else [],
        "protective_factors": why_reasons if risk_level == "low" else [],
        "clinical_summary": clinical_summary,
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
