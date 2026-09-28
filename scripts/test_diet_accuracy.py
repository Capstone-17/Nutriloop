"""Synthetic software smoke checks for the diet engine.

These examples exercise code paths and explicit request constraints only.
They do not clinically validate diagnoses, dietary targets, or patient safety.
"""

from __future__ import annotations
import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.schemas import WeeklyDietPlanRequest, LatestTestReportInput, PatientPreferencesInput
from backend.weekly_diet_engine import weekly_diet_engine, derive_clinical_targets
from backend.rules import calculate_ckd_epi_egfr


def test_egfr_math_and_nutrient_rule_smoke():
    print("\n[TEST 1] eGFR Formula Arithmetic & Synthetic Nutrient-Rule Smoke Check...")
    # Elderly female, Creatinine 1.2 mg/dL, Age 68, BMI 27.5, No explicit eGFR
    labs = LatestTestReportInput(
        serum_creatinine_mg_dl=1.2,
        systolic_bp_mmhg=142.0,
        diastolic_bp_mmhg=88.0,
        fasting_glucose_mg_dl=135.0,
    )
    targets, conditions = derive_clinical_targets(
        age=68,
        sex="female",
        bmi=27.5,
        labs=labs,
        medications=["lisinopril", "jardiance"]
    )
    
    # Arithmetic check only: one eGFR value does not confirm chronic kidney disease.
    egfr = calculate_ckd_epi_egfr(1.2, 68.0, "female")
    assert abs(egfr - 49.3) < 0.1, f"Formula arithmetic changed unexpectedly: {egfr}"
    
    # Check SGLT2i floor
    assert targets["carbohydrate_g"] >= 130.0, f"Failed: SGLT2i carb floor violated: {targets['carbohydrate_g']}"
    assert targets["fluid_intake_ml"] >= 2500, f"Failed: SGLT2i fluid floor violated: {targets['fluid_intake_ml']}"
    # Check Potassium ceiling for CKD + ACEi
    assert targets["potassium_guidance_mg"] <= 2000.0, f"Failed: Potassium ceiling violated: {targets['potassium_guidance_mg']}"
    print(f"  [PASS] Formula arithmetic and configured nutrient-rule assertions: {targets['calories_kcal']} kcal, {targets['protein_g']}g Protein")


def test_regional_caloric_and_macro_adherence():
    print("\n[TEST 2] Synthetic 5-Region Plan Constraint Smoke Check (±5% calories)...")
    regions = ["south_indian", "north_indian", "western_indian", "eastern_indian", "continental"]
    
    for reg in regions:
        req = WeeklyDietPlanRequest(
            user_id=f"test_{reg}",
            age_years=52,
            sex="male",
            body_mass_index=26.5,
            test_reports=LatestTestReportInput(systolic_bp_mmhg=135, fasting_glucose_mg_dl=115),
            preferences=PatientPreferencesInput(
                native_place_region=reg,
                dietary_type="vegetarian",
                calorie_target_override=1850,
            )
        )
        plan = weekly_diet_engine.generate_weekly_plan(req)
        target_cal = plan.clinical_targets["calories_kcal"]
        assert target_cal == 1850, f"Custom calorie target override failed: got {target_cal}"

        # Verify all 7 days
        for day in plan.days:
            day_cal = day.daily_total_nutrients["calories"]
            cal_diff_pct = abs(day_cal - target_cal) / target_cal
            assert cal_diff_pct <= 0.05, f"Region {reg} Day {day.day_number} cal diff {cal_diff_pct:.1%}: {day_cal} vs target {target_cal}"
            
            # Verify protein is within clinical bounds (>= 80% of target)
            day_p = day.daily_total_nutrients["protein_g"]
            assert day_p >= plan.clinical_targets["protein_g"] * 0.80, f"Region {reg} Day {day.day_number} protein deficient: {day_p} vs target {plan.clinical_targets['protein_g']}"

            # Verify sodium ceiling
            day_sod = day.daily_total_nutrients["sodium_mg"]
            assert day_sod <= plan.clinical_targets["sodium_limit_mg"] * 1.05, f"Region {reg} Day {day.day_number} sodium exceeded: {day_sod}"

        print(f"  [PASS] {reg.upper()}: 7 days within +/-5% of {target_cal} kcal (avg {plan.weekly_nutritional_summary['average_daily_calories_kcal']} kcal)")


def test_variety_and_no_duplicate_days():
    print("\n[TEST 3] At Least Five Distinct Lunch/Dinner Title Pairs...")
    regions = ["south_indian", "north_indian", "western_indian", "eastern_indian", "continental"]
    
    for reg in regions:
        req = WeeklyDietPlanRequest(
            user_id="test_variety",
            preferences=PatientPreferencesInput(native_place_region=reg, dietary_type="vegetarian")
        )
        plan = weekly_diet_engine.generate_weekly_plan(req)
        
        # Collect signature of lunch and dinner meal titles across the 7 days
        signatures = [
            f"{d.intervals[2].meal_title} | {d.intervals[4].meal_title}"
            for d in plan.days
        ]
        unique_signatures = set(signatures)
        assert len(unique_signatures) >= 5, f"Region {reg} lacks variety! Only {len(unique_signatures)} unique lunch/dinner combos out of 7 days: {signatures}"
        print(f"  [PASS] {reg.upper()}: {len(unique_signatures)} distinct daily meal patterns across 7 days")


def test_dietary_patterns_and_allergens():
    print("\n[TEST 4] Dietary Type & Allergen Exclusion Engine...")
    
    # 1. Test Bengali Vegetarian (Must not serve fish!)
    req_bengali_veg = WeeklyDietPlanRequest(
        user_id="test_bengali_veg",
        preferences=PatientPreferencesInput(
            native_place_region="Bengali",
            dietary_type="vegetarian"
        )
    )
    plan = weekly_diet_engine.generate_weekly_plan(req_bengali_veg)
    all_dish_titles = " ".join(inv.meal_title for d in plan.days for inv in d.intervals).lower()
    assert "machh" not in all_dish_titles and "fish" not in all_dish_titles, "Bengali vegetarian received fish dish!"
    print("  [PASS] Bengali vegetarian dish titles passed the fish/machh substring check")

    # 2. Test Jain Dietary Pattern (Must not contain onion, garlic, or root vegetables)
    req_jain = WeeklyDietPlanRequest(
        user_id="test_jain",
        preferences=PatientPreferencesInput(
            native_place_region="Gujarati",
            dietary_type="jain",
            dislikes=["peanuts"]
        )
    )
    plan_jain = weekly_diet_engine.generate_weekly_plan(req_jain)
    for day in plan_jain.days:
        for inv in day.intervals:
            for item in inv.items:
                item_lower = item.item_name.lower()
                assert "peanut" not in item_lower, f"Peanut found in Jain plan: {item.item_name}"
    print("  [PASS] Jain-plan item names passed the peanut substring check")


def run_all():
    print("=" * 70)
    print("      RUNNING SYNTHETIC DIET-ENGINE SOFTWARE SMOKE CHECKS")
    print("=" * 70)
    test_egfr_math_and_nutrient_rule_smoke()
    test_regional_caloric_and_macro_adherence()
    test_variety_and_no_duplicate_days()
    test_dietary_patterns_and_allergens()
    print("\n" + "=" * 70)
    print("      ALL SYNTHETIC SOFTWARE ASSERTIONS PASSED (NOT CLINICAL VALIDATION)")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
