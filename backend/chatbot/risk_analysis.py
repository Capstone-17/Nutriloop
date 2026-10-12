"""
backend/chatbot/risk_analysis.py
─────────────────────────────────
Clinical Diet Risk Analysis & Guardrail Validation Layer.

Mandates:
1. Programmatic Clinical Guardrails: Enforces KDIGO (Renal/CKD), ADA (Diabetes),
   and AHA/ACC DASH (Hypertension) clinical guidelines.
2. Anti-Loophole & Prompt-Injection Defense: Strips patient evasions (e.g. "cheat day",
   "my doctor said it's fine", "just this once", "birthday craving", "bypass instructions")
   and evaluates food safety strictly against verified physiological biomarkers.
3. Automated Plan Updating: When a proposed dietary change is safe, coordinates
   safe alterations in the active 7-Day Regional Meal Plan.
4. Clinical Hazard Explanations: When a proposal is unsafe, blocks the modification
   and returns a clear, empathetic clinical explanation with a safe alternative.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from backend.db import get_active_weekly_plan, get_latest_patient_test

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Loophole & Evasion Stripper
# ──────────────────────────────────────────────────────────────────────────────

EVASION_PATTERNS = [
    r"\bcheat\s*day\b",
    r"\bjust\s*(?:this\s*once|for\s*today|a\s*little\s*bit|one\s*time)\b",
    r"\bmy\s*(?:doctor|physician|nutritionist)\s*(?:said|allowed|approved|told\s*me)\b",
    r"\bi\s*(?:ran|walked|worked\s*out|exercised)\b",
    r"\bbirthday\b",
    r"\bcraving\b",
    r"\bignore\s*(?:previous|all|above|safety)\s*instructions?\b",
    r"\bbypass\b",
    r"\bloophole\b",
    r"\boverride\b",
]

_COMPILED_EVASIONS = [re.compile(p, re.IGNORECASE) for p in EVASION_PATTERNS]


def sanitize_diet_proposal(text: str) -> str:
    """Strip patient rationalizations, excuses, or evasion tokens."""
    cleaned = text
    for pat in _COMPILED_EVASIONS:
        cleaned = pat.sub("", cleaned)
    return cleaned.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Clinical Trigger Dictionaries
# ──────────────────────────────────────────────────────────────────────────────

# High-glycemic sweets, refined confectionery, sugary drinks
GLYCEMIC_DANGER_TRIGGERS = [
    "sugar", "gulab jamun", "jalebi", "sweet", "sweets", "dessert", "halwa",
    "pastry", "cake", "candy", "sweet lassi", "syrup", "soda", "coca cola",
    "pepsi", "ice cream", "kheer", "rasgulla", "laddu", "peda", "condensed milk",
    "chocolate cake", "milk chocolate", "sweet tea", "jaggery", "honey",
    "sweetened", "doughnut", "donut", "barfi", "kaju katli",
]

# High-sodium triggers
SODIUM_DANGER_TRIGGERS = [
    "pickle", "achar", "papad", "salted chips", "french fries", "salted peanuts",
    "soy sauce", "salted butter", "processed meat", "bacon", "sausage", "hot dog",
    "canned soup", "salted namkeen", "maggi", "ramen", "instant noodles", "instant noodle",
    "maggi tastemaker", "tastemaker", "flavor packet", "seasoning packet",
    "extra salt", "table salt", "excess salt", "bouillon", "salted nuts",
]

# Renal / CKD triggers (Potassium, Nephrotoxins, Purine Overload)
CKD_NEPHROTOXIC_TRIGGERS = [
    "starfruit", "carambola",  # Caramboxin: strictly neurotoxic & nephrotoxic in CKD
]

HIGH_POTASSIUM_TRIGGERS = [
    "coconut water", "tender coconut water", "potassium salt", "salt substitute",
    "nosalt", "raw spinach smoothie", "raw spinach juice", "banana", "bananas",
    "orange juice", "kiwi", "dried apricots", "prunes",
]

# Drug-Food Interaction Triggers
DRUG_INTERACTIONS = {
    "amlodipine": {
        "triggers": ["grapefruit", "grapefruit juice", "pomelo"],
        "hazard": "Grapefruit inhibits the intestinal CYP3A4 enzyme, leading to dangerous accumulation of Amlodipine and severe, sudden hypotension.",
    },
    "lisinopril": {
        "triggers": ["potassium salt", "salt substitute", "nosalt", "tender coconut water"],
        "hazard": "Lisinopril is an ACE inhibitor that retains serum potassium. Combining it with potassium-rich substitutes or high-potassium fluids risks fatal hyperkalemic cardiac arrhythmias.",
    },
    "losartan": {
        "triggers": ["potassium salt", "salt substitute", "nosalt", "tender coconut water"],
        "hazard": "Losartan conserves potassium; excessive potassium intake increases the risk of severe hyperkalemia.",
    },
    "telmisartan": {
        "triggers": ["potassium salt", "salt substitute", "nosalt", "tender coconut water"],
        "hazard": "Telmisartan conserves potassium; high-potassium substitutes can induce dangerous hyperkalemia.",
    },
    "jardiance": {
        "triggers": ["prolonged fasting", "zero carb", "carnivore diet", "extreme keto"],
        "hazard": "SGLT2 inhibitors like Jardiance promote renal glycosuria. Severe carbohydrate restriction can trigger life-threatening euglycemic diabetic ketoacidosis (euDKA).",
    },
    "empagliflozin": {
        "triggers": ["prolonged fasting", "zero carb", "carnivore diet", "extreme keto"],
        "hazard": "Empagliflozin requires adequate daily carbohydrate intake (≥130g) to prevent euglycemic diabetic ketoacidosis.",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Core Safety Validation Logic
# ──────────────────────────────────────────────────────────────────────────────

def validate_diet_risk(
    user_id: str,
    proposed_text: str,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Validate proposed food items strictly against patient vitals, active medications,
    and clinical guidelines (ADA, KDIGO, AHA/ACC).
    
    Returns:
        {
            "passed": bool,
            "violations": List[str],
            "clinical_explanation": str,
            "recommended_alternative": Optional[str],
        }
    """
    clean_query = sanitize_diet_proposal(proposed_text)
    combined_text = f"{clean_query} " + " ".join(
        str(it.get("item_name", "")) for it in (items or []) if isinstance(it, dict)
    )
    combined_lower = combined_text.lower()

    # Retrieve patient clinical profile
    latest = get_latest_patient_test(user_id) or {}
    labs = latest.get("test_reports", latest)
    detected_conds = [str(c).lower() for c in latest.get("detected_conditions", [])]

    hba1c = float(labs.get("hba1c_pct", 5.2) or 5.2)
    fbg = float(labs.get("fasting_glucose_mg_dl", 90.0) or 90.0)
    sbp = float(labs.get("systolic_bp_mmhg", 120.0) or 120.0)
    dbp = float(labs.get("diastolic_bp_mmhg", 80.0) or 80.0)
    creat = float(labs.get("serum_creatinine_mg_dl", 0.9) or 0.9)
    egfr = float(labs.get("egfr_ml_min", 90.0) or 90.0)
    pot = float(labs.get("serum_potassium_meq_l", 4.2) or 4.2)

    is_diabetic = any("diabet" in c or "t2dm" in c for c in detected_conds) or hba1c >= 6.5 or fbg >= 126.0
    is_prediabetic = (not is_diabetic) and (any("prediabet" in c for c in detected_conds) or hba1c >= 5.7 or fbg >= 100.0)
    is_htn = any("hypertens" in c or "htn" in c for c in detected_conds) or sbp >= 130.0 or dbp >= 80.0
    is_ckd = any("ckd" in c or "kidney" in c for c in detected_conds) or egfr < 60.0 or creat >= 1.3
    is_hyperkalemic = any("hyperkalem" in c for c in detected_conds) or pot >= 5.0

    violations = []
    clinical_reasons = []
    recommended_alt = None

    # 1. Pharmacopeia & Drug-Nutrient Interactions
    active_plan = get_active_weekly_plan(user_id)
    med_alerts = (active_plan.get("medication_alerts", []) if active_plan else [])
    patient_meds = [str(m).lower() for m in latest.get("medications", [])]
    for alert in med_alerts:
        for med_key in DRUG_INTERACTIONS:
            if med_key in alert.lower() and med_key not in patient_meds:
                patient_meds.append(med_key)

    for med in patient_meds:
        for med_key, rule in DRUG_INTERACTIONS.items():
            if med_key in med:
                for trig in rule["triggers"]:
                    if trig in combined_lower:
                        violations.append(f"Drug Interaction: {med_key.title()} + {trig.title()}")
                        clinical_reasons.append(rule["hazard"])

    # 2. Chronic Kidney Disease & Nephrotoxin Guardrails (KDIGO)
    for trig in CKD_NEPHROTOXIC_TRIGGERS:
        if trig in combined_lower:
            violations.append(f"Nephrotoxic Compound: {trig.title()}")
            clinical_reasons.append(
                f"Starfruit contains the potent neurotoxin caramboxin and concentrated oxalates. "
                "In chronic disease care, caramboxin cannot be cleared safely and crosses the blood-brain barrier, "
                "triggering uremic neurotoxicity, intractable hiccups, and seizures. It is strictly excluded from all clinical plans."
            )
            recommended_alt = "Safe low-potassium fruits like crisp green apples, guava, or blueberries."

    if is_ckd or is_hyperkalemic:
        for trig in HIGH_POTASSIUM_TRIGGERS:
            if trig in combined_lower:
                violations.append(f"Renal Potassium Overload: {trig.title()}")
                clinical_reasons.append(
                    f"With your renal filtration profile (eGFR {egfr:.0f} mL/min, Serum Potassium {pot:.1f} mEq/L), "
                    f"consuming high-potassium items like '{trig}' risks dangerous potassium accumulation and cardiac arrhythmias."
                )
                recommended_alt = "Low-potassium options such as cucumber slices, peeled green apples, or bottle gourd soup."

    # 3. Diabetes & Glycemic Guardrails (ADA)
    for trig in GLYCEMIC_DANGER_TRIGGERS:
        if trig in combined_lower:
            if is_diabetic or is_prediabetic:
                violations.append(f"High Glycemic Load: {trig.title()}")
                clinical_reasons.append(
                    f"With your glycemic reading (HbA1c {hba1c:.1f}%, Fasting Glucose {fbg:.0f} mg/dL), "
                    f"adding refined sweets or high-sugar items ('{trig}') causes acute postprandial glucose surges, "
                    "endothelial inflammation, and advanced glycation end-products (AGEs) that damage delicate microvasculature."
                )
            else:
                violations.append(f"Refined Confectionery: {trig.title()}")
                clinical_reasons.append(
                    f"Clinical nutrition therapy prohibits replacing balanced meals with refined sugar or confectionery ('{trig}'). "
                    "Refined sweets induce rapid insulin spikes, visceral fat accumulation, and glycemic volatility with zero therapeutic value."
                )
            recommended_alt = "Complex carbohydrates like oats upma, ragi idli, or a small portion of fresh berries."
            break

    # 4. Hypertension & Sodium Guardrails (AHA / ACC DASH)
    for trig in SODIUM_DANGER_TRIGGERS:
        if trig in combined_lower:
            if is_htn:
                violations.append(f"Excess Dietary Sodium: {trig.title()}")
                clinical_reasons.append(
                    f"With your recorded blood pressure ({int(sbp)}/{int(dbp)} mmHg), consuming heavily salted or processed "
                    f"items ('{trig}') causes intravascular fluid retention and arterial shear stress, worsening hypertension."
                )
            else:
                violations.append(f"Excess Dietary Sodium: {trig.title()}")
                clinical_reasons.append(
                    f"Clinical nutrition standards strictly limit sodium from commercial flavor packets, pickles, and added salt ('{trig}'). "
                    "Excess sodium induces fluid retention and arterial wall stiffness."
                )
            recommended_alt = "Dishes seasoned with fresh garlic, roasted cumin, black pepper, and lemon juice rather than commercial salt seasonings."
            break

    if violations:
        return {
            "passed": False,
            "violations": violations,
            "clinical_explanation": " ".join(clinical_reasons),
            "recommended_alternative": recommended_alt,
        }

    return {
        "passed": True,
        "violations": [],
        "clinical_explanation": "Validated for safe glycemic, cardiovascular, and renal parameters.",
        "recommended_alternative": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Primary Risk Analysis & Execution Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_diet_risk_analysis(
    user_id: str,
    proposed_meal: str,
    items: Optional[List[Dict[str, Any]]] = None,
    day_number: int = 1,
    interval_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Programmatic Clinical Safety and Risk Analysis Layer.
    
    Evaluates any proposed meal against patient biomarkers, diagnosed chronic conditions,
    and active medications. If safe, alters the active 7-Day Regional Meal Plan in SQLite.
    """
    clean_query = sanitize_diet_proposal(proposed_meal)
    validation = validate_diet_risk(user_id, clean_query, items)

    if not validation["passed"]:
        log.warning(
            "[run_diet_risk_analysis] BLOCKED proposed meal '%s' for user %s: %s",
            proposed_meal, user_id, validation["violations"],
        )
        return {
            "passed": False,
            "status": "blocked",
            "risk_level": "high",
            "violations": validation["violations"],
            "clinical_explanation": validation["clinical_explanation"],
            "recommended_alternative": validation["recommended_alternative"],
            "clean_items": [],
            "updated_plan": None,
            "day_number": day_number,
            "interval_name": interval_name or "Meal",
        }

    # Resolve target interval
    target_interval = interval_name
    if not target_interval:
        low_prop = clean_query.lower()
        if "breakfast" in low_prop:
            target_interval = "Breakfast"
        elif "lunch" in low_prop:
            target_interval = "Lunch"
        elif "dinner" in low_prop:
            target_interval = "Dinner"
        elif "snack" in low_prop or "morning" in low_prop:
            target_interval = "Mid-Morning Snack"
        else:
            if any(w in low_prop for w in ["egg", "omelet", "scramble", "idli", "dosa", "oats", "poha"]):
                target_interval = "Breakfast"
            elif any(w in low_prop for w in ["soup", "khichdi", "thepla"]):
                target_interval = "Dinner"
            else:
                target_interval = "Lunch"

    # Formulate clean items and title
    clean_title = clean_query.strip().title()
    if not clean_title:
        clean_title = "Boiled Eggs & Vegetable Scramble"

    if "egg" in clean_query.lower():
        clean_title = "Boiled Eggs / Egg Whites with Black Pepper"
        structured_items = [
            {"item_name": "Boiled Whole Egg or Egg Whites", "portion": "1 whole egg or 2–3 egg whites (100g)"},
            {"item_name": "Sautéed Bell Peppers & Onions (Olive Oil)", "portion": "1/2 cup (75g)"},
            {"item_name": "Crushed Black Pepper & Roasted Cumin", "portion": "to taste (pinch)"},
        ]
        clinical_justification = (
            "Provides high biological value protein with zero carbohydrates and low sodium, "
            "supporting muscle mass and glycemic stability without renal strain."
        )
    elif "chicken" in clean_query.lower():
        clean_title = "Herb-Grilled Skinless Chicken Breast"
        structured_items = [
            {"item_name": "Grilled Skinless Chicken Breast", "portion": "100–120g portion"},
            {"item_name": "Steamed French Beans & Carrots", "portion": "1 cup (120g)"},
        ]
        clinical_justification = "Lean protein source low in saturated fat, portioned within metabolic guidelines."
    elif "soup" in clean_query.lower() or "rasam" in clean_query.lower():
        clean_title = "Light Vegetable & Lentil Broth (Low Sodium)"
        structured_items = [
            {"item_name": "Clear Vegetable Soup / Pepper Rasam", "portion": "1 bowl (180 mL)"},
            {"item_name": "Steamed Sprouted Moong", "portion": "1/2 cup (80g)"},
        ]
        clinical_justification = "Low-calorie, potassium-balanced broth supporting hydration and satiety."
    else:
        structured_items = items or [
            {"item_name": clean_title, "portion": "1 standard portion"},
        ]
        clinical_justification = "Balanced clinical substitution validated for safe glycemic and vascular parameters."

    # Update active plan in database
    updated_plan = None
    try:
        from backend.chatbot.tools import alter_diet_plan_meal
        res = alter_diet_plan_meal(
            user_id=user_id,
            day_number=day_number,
            interval_name=target_interval,
            new_meal_title=clean_title,
            new_items=structured_items,
            clinical_justification=clinical_justification,
        )
        if isinstance(res, dict) and res.get("status") == "success":
            updated_plan = res.get("updated_plan")
    except Exception as exc:
        log.warning("[run_diet_risk_analysis] DB alteration failed: %s", exc)

    return {
        "passed": True,
        "status": "approved",
        "risk_level": "low",
        "violations": [],
        "clinical_explanation": clinical_justification,
        "recommended_alternative": None,
        "clean_meal_title": clean_title,
        "clean_items": structured_items,
        "updated_plan": updated_plan,
        "day_number": day_number,
        "interval_name": target_interval,
    }
