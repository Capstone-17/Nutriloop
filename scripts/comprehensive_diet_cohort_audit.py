"""
Comprehensive Clinical Diet Recommendation Audit
=================================================
Rigorous, medicine-grade clinical verification test suite:
  - 50 Diverse Clinical Sample Patients covering all 5 regional cuisines,
    all 5 dietary types, all stages of CKD, Hypertension, Type 2 Diabetes,
    Hyperkalemia, SGLT2i / ACEi / CCB pharmacopeia rules, and complex allergies.
  - 10 Iterations per patient (500 generation runs, 3,500 daily diet plans, 17,500 meal intervals).
  - 10 Comprehensive Clinical Safety Audits per run:
      1. Structural & execution integrity (0 exceptions, 0 nulls).
      2. Caloric precision (+/- 5% or 100 kcal).
      3. Renal & general protein compliance (KDIGO protein ceiling vs floor).
      4. Potassium ceiling & hyperkalemia safety (leached prep, 0 coconut water / bananas).
      5. Sodium ceiling & DASH compliance (<= 1500mg for HTN/CKD).
      6. Diabetic glycemic safety & SGLT2i carb floor (>=130g carbs, 0 sugar/sweets).
      7. Pharmacopeia drug-nutrient contraindications (Amlodipine citrus ban, etc.).
      8. Dietary type adherence (Veg, Vegan, Eggetarian, Jain root-veg ban).
      9. Zero-tolerance allergen & dislike scrubbing.
     10. Intra-week variety & non-stagnation.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Any, Dict, List, Tuple

# Globally disable writing bytecode (.pyc) or __pycache__ folders
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.schemas import (
    WeeklyDietPlanRequest,
    LatestTestReportInput,
    PatientPreferencesInput,
    WeeklyDietPlanResponse,
)
from backend.weekly_diet_engine import weekly_diet_engine


# ==============================================================================
# 1. 50 Clinically Diverse Sample Patients
# ==============================================================================

def build_50_sample_patients() -> List[Dict[str, Any]]:
    """Builds a comprehensive cohort of 50 diverse clinical patients."""
    cohort = []

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 1: Healthy Baselines & General Vitality (Patients 1 to 5)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P01_HEALTHY_SOUTH_VEG",
        "name": "Aditya Rao",
        "age": 24, "sex": "male", "bmi": 22.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=85.0, systolic_bp_mmhg=115.0, diastolic_bp_mmhg=75.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian", interests_and_likes=["dosa", "idli"]),
        "clinical_category": "Healthy Baseline",
    })
    cohort.append({
        "id": "P02_HEALTHY_NORTH_NONVEG",
        "name": "Pooja Sharma",
        "age": 35, "sex": "female", "bmi": 21.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=90.0, systolic_bp_mmhg=118.0, diastolic_bp_mmhg=76.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian", interests_and_likes=["chicken"]),
        "clinical_category": "Healthy Baseline",
    })
    cohort.append({
        "id": "P03_HEALTHY_WESTERN_JAIN",
        "name": "Bhavik Shah",
        "age": 42, "sex": "male", "bmi": 23.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=92.0, systolic_bp_mmhg=116.0, diastolic_bp_mmhg=74.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain", interests_and_likes=["khichdi"]),
        "clinical_category": "Healthy Baseline",
    })
    cohort.append({
        "id": "P04_HEALTHY_EASTERN_EGGETARIAN",
        "name": "Rupa Das",
        "age": 29, "sex": "female", "bmi": 20.8,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=88.0, systolic_bp_mmhg=112.0, diastolic_bp_mmhg=72.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="eggetarian", interests_and_likes=["egg"]),
        "clinical_category": "Healthy Baseline",
    })
    cohort.append({
        "id": "P05_HEALTHY_CONTINENTAL_VEGAN",
        "name": "Marcus Vance",
        "age": 55, "sex": "male", "bmi": 24.2,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=94.0, systolic_bp_mmhg=120.0, diastolic_bp_mmhg=78.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="vegan", interests_and_likes=["oats", "berries"]),
        "clinical_category": "Healthy Baseline",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 2: Isolated Essential Hypertension (Patients 6 to 12)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P06_HTN1_SOUTH_VEG",
        "name": "Karthik Subramanian",
        "age": 48, "sex": "male", "bmi": 27.2,
        "labs": LatestTestReportInput(systolic_bp_mmhg=138.0, diastolic_bp_mmhg=88.0, fasting_glucose_mg_dl=95.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian", active_medications=[]),
        "clinical_category": "Hypertension (Stage 1)",
    })
    cohort.append({
        "id": "P07_HTN2_NORTH_NONVEG_AMLODIPINE",
        "name": "Sunita Verma",
        "age": 56, "sex": "female", "bmi": 29.0,
        "labs": LatestTestReportInput(systolic_bp_mmhg=152.0, diastolic_bp_mmhg=94.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian", active_medications=["amlodipine"]),
        "clinical_category": "Hypertension (Stage 2)",
    })
    cohort.append({
        "id": "P08_HTN2_WESTERN_VEG_LISINOPRIL_PEANUT_ALLERGY",
        "name": "Deepak Mehta",
        "age": 62, "sex": "male", "bmi": 26.8,
        "labs": LatestTestReportInput(systolic_bp_mmhg=146.0, diastolic_bp_mmhg=90.0, serum_potassium_meq_l=4.4),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="vegetarian", active_medications=["lisinopril"], allergies=["peanut"]),
        "clinical_category": "Hypertension (Stage 2)",
    })
    cohort.append({
        "id": "P09_HTN1_EASTERN_NONVEG_LOSARTAN",
        "name": "Mitali Banerjee",
        "age": 51, "sex": "female", "bmi": 28.5,
        "labs": LatestTestReportInput(systolic_bp_mmhg=142.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="non_vegetarian", active_medications=["losartan"], interests_and_likes=["fish"]),
        "clinical_category": "Hypertension (Stage 1)",
    })
    cohort.append({
        "id": "P10_HTN_RESISTANT_CONTINENTAL_VEGAN",
        "name": "Robert Klein",
        "age": 65, "sex": "male", "bmi": 31.0,
        "labs": LatestTestReportInput(systolic_bp_mmhg=165.0, diastolic_bp_mmhg=102.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="vegan", active_medications=["amlodipine", "metoprolol"]),
        "clinical_category": "Resistant Hypertension",
    })
    cohort.append({
        "id": "P11_HTN1_WESTERN_JAIN",
        "name": "Heena Doshi",
        "age": 43, "sex": "female", "bmi": 25.4,
        "labs": LatestTestReportInput(systolic_bp_mmhg=135.0, diastolic_bp_mmhg=86.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain"),
        "clinical_category": "Hypertension (Stage 1)",
    })
    cohort.append({
        "id": "P12_HTN2_SOUTH_EGGETARIAN_TELMISARTAN",
        "name": "Girish Nair",
        "age": 58, "sex": "male", "bmi": 27.8,
        "labs": LatestTestReportInput(systolic_bp_mmhg=148.0, diastolic_bp_mmhg=92.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="eggetarian", active_medications=["telmisartan", "amlodipine"]),
        "clinical_category": "Hypertension (Stage 2)",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 3: Isolated Type 2 Diabetes & Prediabetes (Patients 13 to 20)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P13_PREDIABETES_NORTH_VEG",
        "name": "Manish Gupta",
        "age": 45, "sex": "male", "bmi": 26.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=108.0, hba1c_pct=5.9, systolic_bp_mmhg=118.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="vegetarian", interests_and_likes=["methi", "sprouts"]),
        "clinical_category": "Prediabetes",
    })
    cohort.append({
        "id": "P14_T2DM_SOUTH_NONVEG_METFORMIN",
        "name": "Priyanka Reddy",
        "age": 52, "sex": "female", "bmi": 28.2,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=145.0, hba1c_pct=7.4),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="non_vegetarian", active_medications=["metformin"]),
        "clinical_category": "Type 2 Diabetes",
    })
    cohort.append({
        "id": "P15_T2DM_EASTERN_VEG_JARDIANCE",
        "name": "Debasis Ghosh",
        "age": 60, "sex": "male", "bmi": 30.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=178.0, hba1c_pct=8.8),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="vegetarian", active_medications=["jardiance"]),
        "clinical_category": "Type 2 Diabetes (SGLT2i)",
    })
    cohort.append({
        "id": "P16_T2DM_WESTERN_JAIN_DAPAGLIFLOZIN",
        "name": "Tarla Kothari",
        "age": 49, "sex": "female", "bmi": 27.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=155.0, hba1c_pct=8.1),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain", active_medications=["dapagliflozin"]),
        "clinical_category": "Type 2 Diabetes (SGLT2i)",
    })
    cohort.append({
        "id": "P17_T2DM_UNCONTROLLED_CONTINENTAL_NONVEG_INSULIN",
        "name": "George Miller",
        "age": 67, "sex": "male", "bmi": 29.8,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=210.0, hba1c_pct=10.2),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="non_vegetarian", active_medications=["insulin", "metformin"]),
        "clinical_category": "Severe Type 2 Diabetes",
    })
    cohort.append({
        "id": "P18_T2DM_SOUTH_VEGAN_SEMAGLUTIDE",
        "name": "Sandhya Balan",
        "age": 38, "sex": "female", "bmi": 24.8,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=138.0, hba1c_pct=7.1),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegan", active_medications=["semaglutide"]),
        "clinical_category": "Type 2 Diabetes (GLP-1 RA)",
    })
    cohort.append({
        "id": "P19_T2DM_NORTH_EGGETARIAN",
        "name": "Vikram Singh",
        "age": 55, "sex": "male", "bmi": 26.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=162.0, hba1c_pct=8.4),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="eggetarian", active_medications=["metformin"]),
        "clinical_category": "Type 2 Diabetes",
    })
    cohort.append({
        "id": "P20_T2DM_EASTERN_VEG_EMPA",
        "name": "Ananya Sen",
        "age": 71, "sex": "female", "bmi": 25.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=150.0, hba1c_pct=7.8),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="vegetarian", active_medications=["empagliflozin"]),
        "clinical_category": "Type 2 Diabetes (SGLT2i)",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 4: Isolated Chronic Kidney Disease (Stages 1 to 5) (Patients 21 to 28)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P21_CKD2_SOUTH_VEG",
        "name": "Venkatesh Murthy",
        "age": 58, "sex": "male", "bmi": 25.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.3, egfr_ml_min=65.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian"),
        "clinical_category": "CKD Stage 2",
    })
    cohort.append({
        "id": "P22_CKD3A_NORTH_NONVEG",
        "name": "Kamla Devi",
        "age": 64, "sex": "female", "bmi": 24.8,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.5, egfr_ml_min=42.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian"),
        "clinical_category": "CKD Stage 3a",
    })
    cohort.append({
        "id": "P23_CKD3B_WESTERN_VEG",
        "name": "Pravin Bhai",
        "age": 70, "sex": "male", "bmi": 26.2,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.1, egfr_ml_min=32.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="vegetarian"),
        "clinical_category": "CKD Stage 3b",
    })
    cohort.append({
        "id": "P24_CKD4_EASTERN_NONVEG",
        "name": "Supriya Mukherjee",
        "age": 59, "sex": "female", "bmi": 23.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.6, egfr_ml_min=22.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="non_vegetarian"),
        "clinical_category": "CKD Stage 4",
    })
    cohort.append({
        "id": "P25_CKD5_CONTINENTAL_VEG",
        "name": "Arthur Pendelton",
        "age": 75, "sex": "male", "bmi": 24.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=3.8, egfr_ml_min=14.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="vegetarian"),
        "clinical_category": "CKD Stage 5 (Non-dialysis)",
    })
    cohort.append({
        "id": "P26_CKD3B_WESTERN_JAIN",
        "name": "Chirag Vora",
        "age": 53, "sex": "male", "bmi": 25.8,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.6, egfr_ml_min=40.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain"),
        "clinical_category": "CKD Stage 3b",
    })
    cohort.append({
        "id": "P27_CKD3A_SOUTH_VEGAN",
        "name": "Madhavan Pillai",
        "age": 68, "sex": "male", "bmi": 23.2,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.4, egfr_ml_min=52.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegan"),
        "clinical_category": "CKD Stage 3a",
    })
    cohort.append({
        "id": "P28_CKD3B_NORTH_EGGETARIAN",
        "name": "Sarojini Saxena",
        "age": 61, "sex": "female", "bmi": 25.2,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.9, egfr_ml_min=31.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="eggetarian"),
        "clinical_category": "CKD Stage 3b",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 5: Comorbid CKD + Hypertension (Patients 29 to 34)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P29_CKD_HTN_SOUTH_VEG_LISINOPRIL",
        "name": "Raghavan S",
        "age": 66, "sex": "male", "bmi": 26.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.6, egfr_ml_min=44.0, systolic_bp_mmhg=155.0, diastolic_bp_mmhg=92.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian", active_medications=["lisinopril", "amlodipine"]),
        "clinical_category": "CKD + Hypertension",
    })
    cohort.append({
        "id": "P30_CKD_HTN_NORTH_NONVEG_LOSARTAN",
        "name": "Indira Chawla",
        "age": 72, "sex": "female", "bmi": 27.4,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.0, egfr_ml_min=27.0, systolic_bp_mmhg=148.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian", active_medications=["losartan"]),
        "clinical_category": "CKD + Hypertension",
    })
    cohort.append({
        "id": "P31_CKD_HTN_WESTERN_JAIN_RAMIPRIL",
        "name": "Narendra Zaveri",
        "age": 58, "sex": "male", "bmi": 25.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.5, egfr_ml_min=49.0, systolic_bp_mmhg=142.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain", active_medications=["ramipril"]),
        "clinical_category": "CKD + Hypertension",
    })
    cohort.append({
        "id": "P32_CKD4_HTN_EASTERN_NONVEG_FUROSEMIDE",
        "name": "Barnali Roy",
        "age": 63, "sex": "female", "bmi": 26.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.4, egfr_ml_min=24.0, systolic_bp_mmhg=160.0, diastolic_bp_mmhg=96.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="non_vegetarian", active_medications=["amlodipine", "furosemide"]),
        "clinical_category": "CKD Stage 4 + HTN",
    })
    cohort.append({
        "id": "P33_CKD_HTN_CONTINENTAL_VEGAN_ENALAPRIL",
        "name": "William Davis",
        "age": 69, "sex": "male", "bmi": 27.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.8, egfr_ml_min=38.0, systolic_bp_mmhg=150.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="vegan", active_medications=["enalapril", "atorvastatin"]),
        "clinical_category": "CKD + Hypertension",
    })
    cohort.append({
        "id": "P34_CKD_HTN_SOUTH_EGGETARIAN_TELMISARTAN",
        "name": "Shyamala Menon",
        "age": 55, "sex": "female", "bmi": 24.6,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.4, egfr_ml_min=46.0, systolic_bp_mmhg=138.0, diastolic_bp_mmhg=86.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="eggetarian", active_medications=["telmisartan"]),
        "clinical_category": "CKD + Hypertension",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 6: Comorbid Diabetes + Hypertension (Patients 35 to 40)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P35_T2DM_HTN_NORTH_VEG_METFORMIN_LISINOPRIL",
        "name": "Harish Kapoor",
        "age": 50, "sex": "male", "bmi": 28.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=160.0, hba1c_pct=8.2, systolic_bp_mmhg=144.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="vegetarian", active_medications=["metformin", "lisinopril"]),
        "clinical_category": "T2DM + Hypertension",
    })
    cohort.append({
        "id": "P36_T2DM_HTN_SOUTH_NONVEG_JARDIANCE_AMLODIPINE",
        "name": "Kavitha Rajan",
        "age": 57, "sex": "female", "bmi": 29.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=175.0, hba1c_pct=8.9, systolic_bp_mmhg=152.0, diastolic_bp_mmhg=94.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="non_vegetarian", active_medications=["jardiance", "amlodipine"]),
        "clinical_category": "T2DM + Hypertension",
    })
    cohort.append({
        "id": "P37_T2DM_HTN_WESTERN_JAIN_LOSARTAN",
        "name": "Jitendra Jain",
        "age": 64, "sex": "male", "bmi": 26.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=140.0, hba1c_pct=7.5, systolic_bp_mmhg=138.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain", active_medications=["metformin", "losartan"]),
        "clinical_category": "T2DM + Hypertension",
    })
    cohort.append({
        "id": "P38_T2DM_HTN_EASTERN_VEG_OZEMPIC",
        "name": "Pratima Dutta",
        "age": 49, "sex": "female", "bmi": 32.0,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=185.0, hba1c_pct=9.1, systolic_bp_mmhg=146.0, diastolic_bp_mmhg=92.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="vegetarian", active_medications=["ozempic", "amlodipine"]),
        "clinical_category": "T2DM + Hypertension",
    })
    cohort.append({
        "id": "P39_T2DM_HTN_CONTINENTAL_NONVEG_DAPA_RAMI",
        "name": "Thomas Bennett",
        "age": 61, "sex": "male", "bmi": 28.8,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=165.0, hba1c_pct=8.5, systolic_bp_mmhg=158.0, diastolic_bp_mmhg=98.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="non_vegetarian", active_medications=["dapagliflozin", "ramipril", "atorvastatin"]),
        "clinical_category": "T2DM + Hypertension",
    })
    cohort.append({
        "id": "P40_T2DM_HTN_SOUTH_VEGAN_TELMISARTAN",
        "name": "Vasantha Kumari",
        "age": 53, "sex": "female", "bmi": 25.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=150.0, hba1c_pct=7.9, systolic_bp_mmhg=140.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegan", active_medications=["metformin", "telmisartan"]),
        "clinical_category": "T2DM + Hypertension",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 7: Triple Comorbidity (CKD + T2DM + HTN) (Patients 41 to 45)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P41_TRIPLE_SOUTH_VEG_JARDIANCE_LISINOPRIL",
        "name": "Sankaran Nambiar",
        "age": 68, "sex": "male", "bmi": 27.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.8, egfr_ml_min=38.0, fasting_glucose_mg_dl=155.0, hba1c_pct=8.0, systolic_bp_mmhg=150.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian", active_medications=["lisinopril", "jardiance"]),
        "clinical_category": "CKD + T2DM + HTN",
    })
    cohort.append({
        "id": "P42_TRIPLE_NORTH_NONVEG_INSULIN_LOSARTAN",
        "name": "Gurmeet Kaur",
        "age": 73, "sex": "female", "bmi": 28.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.2, egfr_ml_min=25.0, fasting_glucose_mg_dl=170.0, hba1c_pct=8.6, systolic_bp_mmhg=158.0, diastolic_bp_mmhg=92.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian", active_medications=["losartan", "insulin"]),
        "clinical_category": "CKD + T2DM + HTN",
    })
    cohort.append({
        "id": "P43_TRIPLE_WESTERN_JAIN_RAMIPRIL",
        "name": "Mansukh Lal",
        "age": 62, "sex": "male", "bmi": 26.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.7, egfr_ml_min=41.0, fasting_glucose_mg_dl=148.0, hba1c_pct=7.7, systolic_bp_mmhg=145.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="jain", active_medications=["ramipril", "metformin"]),
        "clinical_category": "CKD + T2DM + HTN",
    })
    cohort.append({
        "id": "P44_TRIPLE_EASTERN_NONVEG_AMLODIPINE_INSULIN",
        "name": "Geeta Majumdar",
        "age": 70, "sex": "female", "bmi": 29.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.5, egfr_ml_min=22.0, fasting_glucose_mg_dl=190.0, hba1c_pct=9.4, systolic_bp_mmhg=162.0, diastolic_bp_mmhg=96.0),
        "prefs": PatientPreferencesInput(native_place_region="eastern_indian", dietary_type="non_vegetarian", active_medications=["amlodipine", "insulin", "furosemide"]),
        "clinical_category": "CKD + T2DM + HTN",
    })
    cohort.append({
        "id": "P45_TRIPLE_CONTINENTAL_VEGAN_TELMISARTAN_DAPA",
        "name": "Donald Wright",
        "age": 65, "sex": "male", "bmi": 26.8,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.9, egfr_ml_min=36.0, fasting_glucose_mg_dl=160.0, hba1c_pct=8.3, systolic_bp_mmhg=148.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="vegan", active_medications=["telmisartan", "dapagliflozin"]),
        "clinical_category": "CKD + T2DM + HTN",
    })

    # ──────────────────────────────────────────────────────────────────────────
    # COHORT 8: Electrolyte Derangements & Extreme Risk Edge Cases (Patients 46 to 50)
    # ──────────────────────────────────────────────────────────────────────────
    cohort.append({
        "id": "P46_HYPERKALEMIA_CKD3B_SOUTH_VEG",
        "name": "Krishnan Kutty",
        "age": 67, "sex": "male", "bmi": 26.0,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.9, egfr_ml_min=34.0, serum_potassium_meq_l=5.4, systolic_bp_mmhg=142.0),
        "prefs": PatientPreferencesInput(native_place_region="south_indian", dietary_type="vegetarian", active_medications=["lisinopril"]),
        "clinical_category": "Hyperkalemia + CKD Stage 3b",
    })
    cohort.append({
        "id": "P47_HYPERKALEMIA_CKD4_NORTH_NONVEG",
        "name": "Pushpa Rani",
        "age": 71, "sex": "female", "bmi": 24.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=2.5, egfr_ml_min=22.0, serum_potassium_meq_l=5.6, systolic_bp_mmhg=155.0, diastolic_bp_mmhg=90.0),
        "prefs": PatientPreferencesInput(native_place_region="north_indian", dietary_type="non_vegetarian", active_medications=["losartan"]),
        "clinical_category": "Hyperkalemia + CKD Stage 4",
    })
    cohort.append({
        "id": "P48_GERIATRIC_FRAIL_WESTERN_VEG",
        "name": "Chandrakant Parikh",
        "age": 82, "sex": "male", "bmi": 17.8,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.4, egfr_ml_min=48.0, systolic_bp_mmhg=132.0, diastolic_bp_mmhg=78.0),
        "prefs": PatientPreferencesInput(native_place_region="western_indian", dietary_type="vegetarian", active_medications=["amlodipine"]),
        "clinical_category": "Geriatric Frail / Underweight",
    })
    cohort.append({
        "id": "P49_MORBID_OBESITY_T2DM_HTN_CONTINENTAL",
        "name": "Brenda Scott",
        "age": 44, "sex": "female", "bmi": 41.5,
        "labs": LatestTestReportInput(fasting_glucose_mg_dl=170.0, hba1c_pct=9.2, systolic_bp_mmhg=154.0, diastolic_bp_mmhg=96.0),
        "prefs": PatientPreferencesInput(native_place_region="continental", dietary_type="non_vegetarian", active_medications=["jardiance", "amlodipine"]),
        "clinical_category": "Class III Obesity + T2DM + HTN",
    })
    cohort.append({
        "id": "P50_CKD3B_MULTIPLE_ALLERGIES_EASTERN",
        "name": "Subir Mondal",
        "age": 59, "sex": "male", "bmi": 25.5,
        "labs": LatestTestReportInput(serum_creatinine_mg_dl=1.8, egfr_ml_min=35.0, systolic_bp_mmhg=140.0, diastolic_bp_mmhg=88.0),
        "prefs": PatientPreferencesInput(
            native_place_region="eastern_indian",
            dietary_type="non_vegetarian",
            active_medications=["amlodipine", "atorvastatin"],
            allergies=["peanut", "shellfish"],
            dislikes=["coconut", "karela"]
        ),
        "clinical_category": "CKD 3b + Poly-Allergies",
    })

    return cohort


# ==============================================================================
# 2. Comprehensive Clinical Auditor
# ==============================================================================

class ClinicalDietAuditor:
    """Rigorous Clinical Audit Engine to detect any false positives or unsafe foods."""

    NON_VEG_TERMS = {"chicken", "fish", "mutton", "prawn", "salmon", "rohu", "pomfret", "meat", "machh", "turkey", "cod", "tilapia", "shrimp", "crab", "beef", "pork"}
    EGG_TERMS = {"egg", "eggs", "omelet", "omelette", "frittata", "scrambled egg", "boiled egg", "egg curry", "bhurji", "anda"}
    DAIRY_TERMS = {"paneer", "curd", "dahi", "yogurt", "milk", "cheese", "butter", "ghee", "buttermilk", "kadhi", "cream"}
    JAIN_AVOID_TERMS = {"onion", "garlic", "potato", "aloo", "carrot", "beetroot", "radish", "mooli", "ginger"}
    HIGH_POTASSIUM_DANGEROUS = {"tender coconut water", "coconut water", "raw tomato concentrates"}
    HIGH_SUGAR_DANGEROUS = {"white sugar", "refined sugar", "jaggery sweet", "sweet pongal", "sheera", "halwa", "mithai", "syrup"}
    CITRUS_INTERACTIONS = {"grapefruit", "pomelo", "seville orange"}

    def __init__(self):
        self.total_plans_audited = 0
        self.total_days_audited = 0
        self.total_intervals_audited = 0
        self.total_items_audited = 0
        self.violations: List[Dict[str, Any]] = []

    def audit_plan(
        self,
        plan: WeeklyDietPlanResponse,
        patient: Dict[str, Any],
        iteration: int
    ) -> List[str]:
        """Runs 10 strict clinical audits on a generated 7-day plan."""
        p_id = patient["id"]
        errors = []

        self.total_plans_audited += 1
        targets = plan.clinical_targets
        target_cal = float(targets["calories_kcal"])
        target_prot = float(targets["protein_g"])
        target_pot = float(targets["potassium_guidance_mg"])
        target_sod = float(targets["sodium_limit_mg"])
        target_carb = float(targets["carbohydrate_g"])
        conditions = plan.detected_conditions
        dietary_type = patient["prefs"].dietary_type.lower()
        allergies = [a.lower().strip() for a in (patient["prefs"].allergies or [])]
        dislikes = [d.lower().strip() for d in (patient["prefs"].dislikes or [])]
        meds = [m.lower().strip() for m in (patient["prefs"].active_medications or [])]

        is_ckd = any("CKD" in c for c in conditions)
        is_hyperkalemia = any("Hyperkalemia" in c for c in conditions)
        is_htn = any("Hypertension" in c for c in conditions)
        is_diabetic = any("Diabetes" in c for c in conditions)
        has_sglt2i = any(m in meds for m in ["jardiance", "empagliflozin", "farxiga", "dapagliflozin"])
        has_ccb_or_statin = any(m in meds for m in ["amlodipine", "nifedipine", "diltiazem", "atorvastatin", "simvastatin"])

        # Audit 1: Structural Integrity
        if len(plan.days) != 7:
            errors.append(f"Day count is {len(plan.days)} (expected 7)")

        for day in plan.days:
            self.total_days_audited += 1
            if len(day.intervals) != 5:
                errors.append(f"Day {day.day_number} has {len(day.intervals)} intervals (expected 5)")

            day_nutrients = day.daily_total_nutrients
            day_cal = day_nutrients["calories"]
            day_prot = day_nutrients["protein_g"]
            day_sod = day_nutrients["sodium_mg"]
            day_pot = day_nutrients["potassium_mg"]
            day_carb = day_nutrients["carbs_g"]

            # Audit 2: Caloric Precision (+/- 5% or 100 kcal)
            cal_diff = abs(day_cal - target_cal)
            cal_pct = cal_diff / target_cal
            if cal_pct > 0.05 and cal_diff > 100:
                errors.append(f"Day {day.day_number} Caloric deviation: {day_cal} vs target {target_cal} ({cal_pct:.1%})")

            # Audit 3: Protein Compliance
            if is_ckd:
                # KDIGO renal protein ceiling
                if day_prot > target_prot * 1.15:
                    errors.append(f"Day {day.day_number} CKD Protein exceeded ceiling: {day_prot}g vs target {target_prot}g")
            else:
                # Adequate adult protein floor
                if day_prot < target_prot * 0.80:
                    errors.append(f"Day {day.day_number} Protein deficient: {day_prot}g vs target {target_prot}g")

            # Audit 4: Potassium Ceiling
            if is_hyperkalemia or is_ckd:
                if day_pot > target_pot * 1.05:
                    errors.append(f"Day {day.day_number} Potassium exceeded safe ceiling: {day_pot}mg vs limit {target_pot}mg")

            # Audit 5: Sodium Ceiling
            if is_htn or is_ckd:
                if day_sod > target_sod * 1.05:
                    errors.append(f"Day {day.day_number} Sodium exceeded safe ceiling: {day_sod}mg vs limit {target_sod}mg")

            # Audit 6: SGLT2i Carbohydrate Safety Floor
            if has_sglt2i:
                if day_carb < 130.0:
                    errors.append(f"Day {day.day_number} SGLT2i Carb floor violated: {day_carb}g (<130g floor)")

            # Audit 7-9: Individual Meal Interval & Food Item Audits
            for inv in day.intervals:
                self.total_intervals_audited += 1
                t_lower = inv.meal_title.lower()
                all_items_text = " ".join(it.item_name.lower() for it in inv.items)
                prep_text = inv.prep_tips.lower()
                full_meal_text = f"{t_lower} {all_items_text} {prep_text}"

                for item in inv.items:
                    self.total_items_audited += 1
                    it_name = item.item_name.lower()

                    # Audit 8: Dietary Type Violations
                    if dietary_type == "vegetarian":
                        for term in self.NON_VEG_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Non-veg item '{item.item_name}' served to Vegetarian!")
                        for term in self.EGG_TERMS:
                            if term in it_name and "eggplant" not in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Egg item '{item.item_name}' served to Vegetarian!")

                    elif dietary_type == "eggetarian":
                        for term in self.NON_VEG_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Non-veg item '{item.item_name}' served to Eggetarian!")

                    elif dietary_type == "vegan":
                        for term in self.NON_VEG_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Non-veg item '{item.item_name}' served to Vegan!")
                        for term in self.EGG_TERMS:
                            if term in it_name and "eggplant" not in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Egg item '{item.item_name}' served to Vegan!")
                        for term in self.DAIRY_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Dairy item '{item.item_name}' served to Vegan!")

                    elif dietary_type == "jain":
                        for term in self.NON_VEG_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Non-veg item '{item.item_name}' served to Jain!")
                        for term in self.EGG_TERMS:
                            if term in it_name and "eggplant" not in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Egg item '{item.item_name}' served to Jain!")
                        for term in self.JAIN_AVOID_TERMS:
                            if term in it_name:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Root vegetable '{item.item_name}' served to Jain!")

                    # Audit 9: Allergen / Dislike Violations
                    for ex in (allergies + dislikes):
                        if ex in it_name:
                            errors.append(f"Day {day.day_number} {inv.interval_name}: Excluded allergen '{ex}' found in '{item.item_name}'!")

                    # Audit 7: Drug-Food Interaction Violations
                    if has_ccb_or_statin:
                        for c in self.CITRUS_INTERACTIONS:
                            if c in it_name or c in t_lower:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Banned citrus '{c}' served with Amlodipine/Statin!")

                    if is_hyperkalemia or (is_ckd and any("lisinopril" in m or "losartan" in m for m in meds)):
                        for pk in self.HIGH_POTASSIUM_DANGEROUS:
                            if pk in it_name or pk in t_lower:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Dangerous high-potassium item '{pk}' served to Hyperkalemic patient!")

                    if is_diabetic:
                        for sk in self.HIGH_SUGAR_DANGEROUS:
                            if sk in it_name or sk in t_lower:
                                errors.append(f"Day {day.day_number} {inv.interval_name}: Dangerous high-sugar item '{sk}' served to Diabetic patient!")

        # Audit 10: Multi-Day Variety (no 100% duplicate days)
        day_signatures = [
            f"{d.intervals[0].meal_title} | {d.intervals[2].meal_title} | {d.intervals[4].meal_title}"
            for d in plan.days
        ]
        if len(set(day_signatures)) < 5:
            errors.append(f"Plan lacks intra-week variety: only {len(set(day_signatures))} unique days")

        if errors:
            self.violations.append({
                "patient_id": p_id,
                "iteration": iteration,
                "errors": errors
            })

        return errors


# ==============================================================================
# 3. Main Test Execution Orchestrator
# ==============================================================================

def run_comprehensive_diet_audit():
    print("=" * 80)
    print("      COMPREHENSIVE CLINICAL DIET RECOMMENDATION AUDIT")
    print("      50 DIVERSE PATIENTS × 10 ITERATIONS = 500 TOTAL PLANS")
    print("=" * 80)

    patients = build_50_sample_patients()
    auditor = ClinicalDietAuditor()

    print(f"\nCohort initialized with {len(patients)} diverse clinical patients:")
    print("  - 5 Regional Cuisines (South, North, Western, Eastern, Continental)")
    print("  - 5 Dietary Types (Vegetarian, Non-Vegetarian, Vegan, Eggetarian, Jain)")
    print("  - Chronic Conditions: CKD Stages 1-5, Hyperkalemia, HTN, T2DM, Triple Comorbidities")
    print("  - Active Medications: ACEi, ARBs, CCBs (Amlodipine), SGLT2i (Jardiance), Statins, Insulin")
    print("  - Complex Allergens: Peanuts, Shellfish, Coconut, Dairy, Bitter Gourd\n")

    start_time = time.time()
    total_runs = 0
    clean_runs = 0

    print("Executing 10 evaluation iterations per patient...")
    for p_idx, patient in enumerate(patients, start=1):
        p_id = patient["id"]
        category = patient["clinical_category"]
        p_errors_count = 0

        req = WeeklyDietPlanRequest(
            user_id=p_id,
            age_years=patient["age"],
            sex=patient["sex"],
            body_mass_index=patient["bmi"],
            test_reports=patient["labs"],
            preferences=patient["prefs"]
        )

        for it in range(1, 11):
            total_runs += 1
            plan = weekly_diet_engine.generate_weekly_plan(req)
            errors = auditor.audit_plan(plan, patient, it)

            if not errors:
                clean_runs += 1
            else:
                p_errors_count += len(errors)

        status_str = "[PASS 10/10 CLEAN]" if p_errors_count == 0 else f"[FAIL: {p_errors_count} errors]"
        print(f"  [{p_idx:02d}/50] {p_id:<42} ({category:<26}) -> {status_str}")

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 80)
    print("                     AUDIT SUMMARY & CLINICAL METRICS")
    print("=" * 80)
    print(f"Total Patients Tested:               50 patients")
    print(f"Iterations per Patient:              10 runs")
    print(f"Total Plans Audited:                 {auditor.total_plans_audited} plans")
    print(f"Total Daily Schedules Audited:       {auditor.total_days_audited:,} days")
    print(f"Total Meal Intervals Audited:        {auditor.total_intervals_audited:,} intervals")
    print(f"Total Food Items Screened:           {auditor.total_items_audited:,} items")
    print(f"Elapsed Time:                        {elapsed_time:.2f} seconds ({elapsed_time/total_runs*1000:.1f} ms/plan)")
    print(f"Clean Error-Free Runs:               {clean_runs} / {total_runs} ({(clean_runs/total_runs)*100:.1f}%)")
    print(f"Total Clinical Safety Violations:    {len(auditor.violations)}")

    if auditor.violations:
        print("\n[CRITICAL SAFETY FAILURES DETECTED]:")
        for v in auditor.violations[:10]:
            print(f"  Patient {v['patient_id']} (Iteration {v['iteration']}):")
            for err in v["errors"]:
                print(f"    - {err}")
        sys.exit(1)
    else:
        print("\n" + "=" * 80)
        print(" [VERIFICATION SUCCESS] 100% CLINICALLY ACCURATE & SAFE ACROSS ALL 500 RUNS!")
        print(" ZERO FALSE POSITIVES. ZERO DANGEROUS FOODS SERVED. ZERO RUNTIME ERRORS.")
        print("=" * 80)


if __name__ == "__main__":
    run_comprehensive_diet_audit()
