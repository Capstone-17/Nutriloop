"""
Interactive & Scriptable Clinical Risk Prediction CLI Tool
===========================================================
Usage:
  python predict_cli.py sample_patient.json
  python predict_cli.py --file patient_data.json
  python predict_cli.py --disease ckd --interactive
  python predict_cli.py --raw-input patient_ckd.json
  python predict_cli.py --disease hypertension --show-template
"""

from __future__ import annotations
import argparse
import json
import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.model_registry import registry
from backend.raw_input import get_raw_field_metadata, get_raw_template, map_raw_payload
from backend.reporting import build_risk_report
from backend.rules import build_calibration_context, classify_risk_level


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A Deep Learning and Generative AI-Driven Diet Recommendation System for Personalized Chronic Disease Management"
    )
    parser.add_argument("file_positional", nargs="?", type=str, help="Optional path to payload JSON file")
    parser.add_argument("--file", type=str, help="Path to input payload JSON file")
    parser.add_argument("--disease", type=str, choices=["ckd", "hypertension", "diabetes"], help="Target disease")
    parser.add_argument("--input", type=str, help="Path to JSON file with direct scaled features")
    parser.add_argument("--raw-input", type=str, help="Path to JSON file with conversational raw inputs")
    parser.add_argument("--show-template", action="store_true", help="Display questionnaire template for disease")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive terminal questionnaire")
    parser.add_argument("--recommend-diet", action="store_true", default=True, help="Include dietary recommendations")
    parser.add_argument("--weekly-diet", action="store_true", help="Generate 7-day, 5-interval personalized regional weekly meal plan")
    return parser.parse_args()


def interactive_wizard(disease: str) -> dict:
    print(f"\n--- Clinical Assessment Wizard: {disease.upper()} ---")
    fields = get_raw_field_metadata(disease)
    raw_inputs = {}

    for f in fields:
        name = f["name"]
        label = f["label"]
        req = f.get("required", False)
        prompt = f"{label} {'(required)' if req else '(optional)'}: "

        while True:
            val = input(prompt).strip()
            if not val:
                if req:
                    print("  This field is required.")
                    continue
                break

            if name == "sex":
                if val.lower() in ["male", "m"]:
                    raw_inputs[name] = "male"
                    break
                elif val.lower() in ["female", "f"]:
                    raw_inputs[name] = "female"
                    break
                print("  Please enter 'male' or 'female'.")
            elif "diagnosed" in name or "smoker" in name or "stroke" in name:
                if val.lower() in ["true", "t", "yes", "y", "1"]:
                    raw_inputs[name] = True
                    break
                elif val.lower() in ["false", "f", "no", "n", "0"]:
                    raw_inputs[name] = False
                    break
                print("  Please enter 'yes' or 'no'.")
            else:
                try:
                    num = float(val)
                    raw_inputs[name] = int(num) if num.is_integer() else num
                    break
                except ValueError:
                    print("  Please enter a valid numeric value.")

    return raw_inputs


def render_weekly_diet_plan(data: dict):
    from backend.weekly_diet_engine import (
        weekly_diet_engine,
        WeeklyDietPlanRequest,
        LatestTestReportInput,
        PatientPreferencesInput,
    )

    raw = data.get("raw_inputs", {})
    reports_dict = data.get("test_reports") or {}
    if not reports_dict and raw:
        reports_dict = {
            "systolic_bp_mmhg": raw.get("systolic_bp_mmhg"),
            "diastolic_bp_mmhg": raw.get("diastolic_bp_mmhg"),
            "fasting_glucose_mg_dl": raw.get("fasting_glucose_mg_dl"),
            "hba1c_pct": raw.get("hba1c_pct"),
            "serum_creatinine_mg_dl": raw.get("serum_creatinine_mg_dl"),
            "blood_urea_mg_dl": raw.get("blood_urea_mg_dl"),
            "urine_albumin_dipstick": raw.get("urine_albumin_dipstick"),
            "total_cholesterol_mg_dl": raw.get("total_cholesterol_mg_dl"),
            "report_summary_text": data.get("clinical_context"),
        }

    test_reports = LatestTestReportInput(**reports_dict)
    preferences = PatientPreferencesInput(**data.get("preferences", {}))
    
    age = data.get("age_years") or raw.get("age_years", 50)
    sex = data.get("sex") or raw.get("sex", "male")
    bmi = data.get("body_mass_index") or raw.get("body_mass_index", 25.0)

    req = WeeklyDietPlanRequest(
        user_id=data.get("user_id", "patient"),
        age_years=age,
        sex=sex,
        body_mass_index=bmi,
        test_reports=test_reports,
        preferences=preferences,
    )
    res = weekly_diet_engine.generate_weekly_plan(req)

    print("\n" + "=" * 78)
    print("      7-DAY PERSONALIZED REGIONAL MEDICAL NUTRITION PLAN")
    print("=" * 78)
    print(f"Patient ID:            {res.user_id}")
    print(f"Demographics:          Age {res.patient_summary['age_years']}, {res.patient_summary['sex'].capitalize()} | BMI: {res.patient_summary['body_mass_index']}")
    print(f"Native Region:         {res.patient_summary['native_region']} ({res.patient_summary['dietary_type'].capitalize()})")
    print(f"Detected Conditions:   {', '.join(res.detected_conditions)}")
    print(f"Caloric Target:        {res.clinical_targets['calories_kcal']} kcal/day")
    print(f"Sodium Upper Limit:    {res.clinical_targets['sodium_limit_mg']} mg/day")
    print(f"Potassium Guidance:    {res.clinical_targets['potassium_guidance_mg']} mg/day")
    print(f"Protein Target:        {res.clinical_targets['protein_g']} g/day")

    if res.medication_alerts:
        print("\n" + "!" * 78)
        print("  CRITICAL PHARMACOPEIA & MEDICATION ALERTS:")
        for alert in res.medication_alerts:
            print(f"  [!] {alert}")
        print("!" * 78)

    for day in res.days:
        print("\n" + "-" * 78)
        print(f"  DAY {day.day_number}: {day.day_name.upper()}")
        print(f"  Daily Totals: {day.daily_total_nutrients['calories']} kcal | "
              f"Protein: {day.daily_total_nutrients['protein_g']}g | "
              f"Sodium: {day.daily_total_nutrients['sodium_mg']}mg | "
              f"Potassium: {day.daily_total_nutrients['potassium_mg']}mg | "
              f"Fiber: {day.daily_total_nutrients['fiber_g']}g")
        print("-" * 78)

        for interval in day.intervals:
            print(f"\n  [{interval.time_window}] {interval.interval_name.upper()}: {interval.meal_title}")
            for item in interval.items:
                print(f"    * {item.item_name} ({item.portion})")
            print(f"    -> Nutrients: {interval.total_nutrients['calories']} kcal, "
                  f"P: {interval.total_nutrients['protein_g']}g, "
                  f"Na: {interval.total_nutrients['sodium_mg']}mg, "
                  f"K: {interval.total_nutrients['potassium_mg']}mg")
            print(f"    -> Clinical Note: {interval.clinical_justification}")
            print(f"    -> Prep Tip: {interval.prep_tips}")

    print("\n" + "=" * 78)
    print("  WEEKLY GROCERY CHECKLIST (Top Items):")
    print("=" * 78)
    for i, g in enumerate(res.grocery_checklist, start=1):
        print(f"  {i:2d}. {g}")
    print("=" * 78 + "\n")


def main():
    args = parse_args()
    registry.load()

    if args.show_template:
        if not args.disease:
            print("Error: --disease is required when using --show-template")
            sys.exit(1)
        tpl = get_raw_template(args.disease)
        print(json.dumps(tpl, indent=2))
        return

    raw_inputs = None
    features = None
    disease = args.disease

    # Check for file inputs from various flag options
    target_file = args.file_positional or args.file or args.raw_input or args.input

    if args.interactive:
        if not disease:
            print("Select disease:")
            print("1. Chronic Kidney Disease (CKD)")
            print("2. Hypertension")
            print("3. Type 2 Diabetes")
            choice = input("Enter choice (1-3): ").strip()
            mapping = {"1": "ckd", "2": "hypertension", "3": "diabetes"}
            disease = mapping.get(choice, "ckd")
        raw_inputs = interactive_wizard(disease)

    elif target_file:
        file_path = Path(target_file)
        if not file_path.exists():
            print(f"Error: File '{target_file}' not found.")
            sys.exit(1)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle weekly diet plan directly if present
        if "test_reports" in data or args.weekly_diet:
            render_weekly_diet_plan(data)
            return

        disease = data.get("disease", disease)
        if "raw_inputs" in data:
            raw_inputs = data["raw_inputs"]
        elif "features" in data:
            features = data["features"]
        else:
            raw_inputs = data

    else:
        print("Error: Specify a JSON payload file (e.g. `python scripts/predict_cli.py sample_patient.json`), --file, --interactive, or --show-template")
        sys.exit(1)

    if not disease:
        print("Error: Unable to determine disease from file or flags. Specify --disease [ckd|hypertension|diabetes]")
        sys.exit(1)

    if raw_inputs:
        mapping_result = map_raw_payload(disease, raw_inputs)
        features = mapping_result.transformed_features
        if mapping_result.validation_warnings:
            print("\nClinical Mapping Warnings:")
            for w in mapping_result.validation_warnings:
                print(f"  [!] {w}")

    # Run Prediction
    pred_class, risk_score, model_name, thresholds, top_factors = registry.predict_risk(disease, features)
    risk_level = classify_risk_level(risk_score, thresholds)
    calib = build_calibration_context(disease, risk_score, thresholds, top_factors)

    print("\n" + "=" * 70)
    print(f"       CLINICAL RISK ASSESSMENT REPORT: {disease.upper()}")
    print("=" * 70)
    print(f"Model Employed:        {model_name}")
    print(f"Calculated Risk Score: {risk_score:.4f} ({risk_level.upper()} RISK)")
    strictness = calib.get("strictness_multiplier", 1.0) if isinstance(calib, dict) else getattr(calib, "strictness_multiplier", 1.0)
    print(f"Strictness Factor:     {strictness:.2f}x")

    print("\nTop Contributing Risk Factors:")
    for f in top_factors[:5]:
        print(f"  - {f['feature']:25s} | Relative Impact: {f['relative_importance'] * 100:.1f}%")

    if args.recommend_diet:
        report = build_risk_report(
            disease=disease,
            predicted_class=pred_class,
            risk_score=risk_score,
            model_name=model_name,
            thresholds=thresholds,
            top_factors=top_factors,
            transformed_features=features,
            raw_inputs=raw_inputs,
            warnings=[],
        )
        plan = report["plan"]
        print("\n" + "-" * 70)
        print("  PERSONALIZED DIETARY TARGETS & MEDICAL NUTRITION GUIDELINES")
        print("-" * 70)
        print(f"Daily Calories:        {plan['calories_target']} kcal")
        print(f"Protein Target:        {plan['protein_target_g']} g")
        print(f"Carbohydrate Target:   {plan['carb_target_g']} g")
        print(f"Dietary Fat Limit:     {plan['fat_target_g']} g")
        print(f"Sodium Upper Limit:    {plan['sodium_limit_mg']} mg")
        print(f"Potassium Guidance:    {plan['potassium_limit_mg']} mg")
        print(f"Fiber Goal:            {plan['fiber_target_g']} g")

        print("\nClinical Dietary Priorities:")
        for focus in plan["diet_focus"]:
            print(f"  + {focus}")

        print("\nRecommended Clinical Food Selections:")
        for food in report["recommended_foods"][:5]:
            print(f"  * {food['food_name']:40s} | Category: {food['food_category']:20s} | Score: {food['food_score']:.3f}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
