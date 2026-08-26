"""
Interactive & Scriptable Clinical Risk Prediction CLI Tool
===========================================================
Usage:
  python predict_cli.py --disease ckd --interactive
  python predict_cli.py --raw-input ../demo_inputs/ckd_sample.json
  python predict_cli.py --disease hypertension --show-template
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.model_registry import registry
from backend.raw_input import get_raw_field_metadata, get_raw_template, map_raw_payload
from backend.reporting import build_explanation_text, build_risk_report
from backend.rules import build_calibration_context, classify_risk_level


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A Deep Learning and Generative AI-Driven Diet Recommendation System for Personalized Chronic Disease Management"
    )
    parser.add_argument("--disease", type=str, choices=["ckd", "hypertension", "diabetes"], help="Target disease")
    parser.add_argument("--input", type=str, help="Path to JSON file with direct features")
    parser.add_argument("--raw-input", type=str, help="Path to JSON file with conversational raw inputs")
    parser.add_argument("--show-template", action="store_true", help="Display questionnaire template for disease")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive terminal questionnaire")
    parser.add_argument("--recommend-diet", action="store_true", default=True, help="Include dietary recommendations")
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

    elif args.raw_input:
        with open(args.raw_input, "r", encoding="utf-8") as f:
            data = json.load(f)
        disease = data.get("disease", disease)
        raw_inputs = data.get("raw_inputs", data)

    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        disease = data.get("disease", disease)
        features = data.get("features", data)

    else:
        print("Error: Specify --interactive, --raw-input <file>, --input <file>, or --show-template")
        sys.exit(1)

    if not disease:
        print("Error: Unable to determine disease.")
        sys.exit(1)

    if raw_inputs:
        mapping_result = map_raw_payload(disease, raw_inputs)
        features = mapping_result.transformed_features

    # Run Prediction
    pred_class, risk_score, model_name, thresholds, top_factors = registry.predict_risk(disease, features)
    risk_level = classify_risk_level(risk_score, thresholds)
    calib = build_calibration_context(disease, risk_score, thresholds, top_factors)

    print("\n" + "=" * 70)
    print(f"       CLINICAL RISK ASSESSMENT REPORT: {disease.upper()}")
    print("=" * 70)
    print(f"Model Employed:      {model_name}")
    print(f"Calculated Risk Score: {risk_score:.4f} ({risk_level.upper()} RISK)")
    strictness = calib.get("strictness_multiplier", 1.0) if isinstance(calib, dict) else getattr(calib, "strictness_multiplier", 1.0)
    print(f"Strictness Factor:   {strictness:.2f}x")

    print("\nTop Contributing Risk Factors:")
    for f in top_factors[:5]:
        print(f"  • {f['feature']:25s} | Importance: {f['relative_importance'] * 100:.1f}%")

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
        print(f"Daily Calories:      {plan['calories_target']} kcal")
        print(f"Protein Target:      {plan['protein_target_g']} g")
        print(f"Carbohydrate Target: {plan['carb_target_g']} g")
        print(f"Dietary Fat Limit:   {plan['fat_target_g']} g")
        print(f"Sodium Upper Limit:  {plan['sodium_limit_mg']} mg")
        print(f"Potassium Guidance:  {plan['potassium_limit_mg']} mg")
        print(f"Fiber Goal:          {plan['fiber_target_g']} g")

        print("\nClinical Dietary Priorities:")
        for focus in plan["diet_focus"]:
            print(f"  + {focus}")

        print("\nRecommended Clinical Food Selections:")
        for food in report["recommended_foods"][:5]:
            print(f"  * {food['food_name']:40s} | Category: {food['food_category']:20s} | Score: {food['food_score']:.3f}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
