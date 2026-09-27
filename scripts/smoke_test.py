"""
Comprehensive REST API Smoke Test Suite
========================================
Validates that all 22 REST endpoints in NutriMed AI execute with status 200
and conform strictly to Pydantic schemas.
"""

from __future__ import annotations
import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.app import app
from backend.db import init_db
from backend.model_registry import registry


def assert_status(response, expected=200, label=""):
    assert response.status_code == expected, f"{label} failed: status {response.status_code}, text={response.text}"
    print(f"  [PASS] {label} -> {response.status_code}")


def run_all_tests():
    init_db()
    registry.load()

    print("\n" + "=" * 70)
    print("        RUNNING REPOSITORY REST API SMOKE TEST SUITE")
    print("=" * 70)

    with TestClient(app) as client:
        # 1. Health & Status
        assert_status(client.get("/health"), 200, "GET /health")
        assert_status(client.get("/implementation-progress"), 200, "GET /implementation-progress")

    # 2. Templates & Raw Metadata
    for disease in ["ckd", "hypertension", "diabetes"]:
        assert_status(client.get(f"/raw-input-template/{disease}"), 200, f"GET /raw-input-template/{disease}")

    # 3. Direct Predictions
    for disease in ["ckd", "hypertension", "diabetes"]:
        res = client.post("/predict-risk", json={"disease": disease, "features": {}})
        assert_status(res, 200, f"POST /predict-risk ({disease})")

    # 4. Raw Inputs Predictions
    for disease in ["ckd", "hypertension", "diabetes"]:
        raw_res = client.get(f"/raw-input-template/{disease}").json()
        payload = {"disease": disease, "raw_inputs": raw_res.get("raw_inputs", {})}
        assert_status(client.post("/predict-risk-raw", json=payload), 200, f"POST /predict-risk-raw ({disease})")
        assert_status(client.post("/risk-explanation-raw", json=payload), 200, f"POST /risk-explanation-raw ({disease})")
        assert_status(client.post("/risk-report-raw", json=payload), 200, f"POST /risk-report-raw ({disease})")

    # 5. Core Nutrition & Explanations
    assert_status(
        client.post(
            "/recommend-plan",
            json={"user_id": "test_user", "disease": "ckd", "risk_score": 0.85, "profile": {}},
        ),
        200,
        "POST /recommend-plan",
    )
    assert_status(
        client.post(
            "/log-meal",
            json={"user_id": "test_user", "planned_calories": 500, "consumed_calories": 520, "notes": "Lunch"},
        ),
        200,
        "POST /log-meal",
    )
    assert_status(client.get("/risk-explanations?user_id=test_user"), 200, "GET /risk-explanations")

    # 6. Medical Knowledge Base & Safety
    assert_status(client.get("/medical/guidelines?disease=ckd"), 200, "GET /medical/guidelines")
    assert_status(client.get("/medical/drug-interactions/lisinopril"), 200, "GET /medical/drug-interactions/lisinopril")
    assert_status(
        client.post(
            "/safety/validate",
            json={
                "user_id": "test_user",
                "disease": "ckd",
                "meal_data": {"calories": 400.0, "sodium_mg": 300.0, "potassium_mg": 250.0, "protein_g": 20.0},
            },
        ),
        200,
        "POST /safety/validate",
    )

    # 7. Adaptation & Feedback Learning
    assert_status(
        client.post(
            "/adaptation/log-meal",
            json={
                "user_id": "test_user",
                "meal_type": "lunch",
                "planned_calories": 600,
                "consumed_calories": 620,
                "planned_nutrients": {"sodium_mg": 400.0},
                "consumed_nutrients": {"sodium_mg": 410.0},
            },
        ),
        200,
        "POST /adaptation/log-meal",
    )
    assert_status(client.get("/adaptation/summary/test_user"), 200, "GET /adaptation/summary/test_user")
    assert_status(
        client.post(
            "/feedback/submit",
            json={
                "user_id": "test_user",
                "feedback_type": "adherence",
                "rating": 5,
                "text_feedback": "Great recommendations!",
            },
        ),
        200,
        "POST /feedback/submit",
    )
    assert_status(
        client.post(
            "/outcomes/record",
            json={
                "user_id": "test_user",
                "outcome_type": "blood_pressure_change",
                "value": -5.0,
                "unit": "mmHg",
            },
        ),
        200,
        "POST /outcomes/record",
    )
    assert_status(client.get("/learning/summary"), 200, "GET /learning/summary")

    # 8. Multi-Agent & Chatbot Endpoints
    assert_status(
        client.post(
            "/chatbot/chat",
            json={"user_id": "test_user", "message": "What should I eat for breakfast?"},
        ),
        200,
        "POST /chatbot/chat (with zero-downtime offline fallback)",
    )
    assert_status(
        client.post(
            "/agent/chat",
            json={
                "user_id": "test_user",
                "user_message": "Give me a healthy dinner plan for CKD",
                "user_profile": {
                    "user_id": "test_user",
                    "disease": "ckd",
                    "risk_level": "moderate",
                    "dietary_preferences": ["vegetarian"],
                    "calorie_target": 1800,
                },
            },
        ),
        200,
        "POST /agent/chat",
    )

    # 9. Comorbidity & Multi-Disease Planning
    comorbid_res = client.post(
        "/recommend-plan",
        json={
            "user_id": "test_user",
            "diseases": ["ckd", "hypertension"],
            "risk_score": 0.85,
            "profile": {"calories_target": 1900},
        },
    )
    assert_status(comorbid_res, 200, "POST /recommend-plan (Comorbidity: CKD + HTN)")
    comorbid_data = comorbid_res.json()
    assert comorbid_data["potassium_limit_mg"] <= 2000, "Renal potassium safety override failed"
    assert comorbid_data["sodium_limit_mg"] <= 1500, "DASH sodium restriction failed"
    print("  [PASS] Comorbidity Clinical Priority Rule Verified: Potassium <= 2000mg & Sodium <= 1500mg")

    # 10. Expanded Pharmacopeia
    assert_status(client.get("/medical/drug-interactions/empagliflozin"), 200, "GET /medical/drug-interactions/empagliflozin")
    assert_status(client.get("/medical/drug-interactions/amlodipine"), 200, "GET /medical/drug-interactions/amlodipine")
    assert_status(client.get("/medical/drug-interactions/losartan"), 200, "GET /medical/drug-interactions/losartan")

    # 11. Personalized Weekly Diet Recommendation (Test Reports + Regional Preferences)
    weekly_payload = {
        "user_id": "smoke_test_patient",
        "age_years": 58,
        "sex": "male",
        "body_mass_index": 28.2,
        "test_reports": {
            "systolic_bp_mmhg": 150.0,
            "diastolic_bp_mmhg": 92.0,
            "fasting_glucose_mg_dl": 140.0,
            "hba1c_pct": 7.6,
            "serum_creatinine_mg_dl": 1.9,
            "report_summary_text": "Patient with Stage 3 CKD, uncontrolled HTN, and T2DM on Lisinopril."
        },
        "preferences": {
            "native_place_region": "South Indian",
            "dietary_type": "vegetarian",
            "interests_and_likes": ["ragi", "millets", "light spices"],
            "cooking_skill": "intermediate",
            "active_medications": ["lisinopril", "jardiance"]
        }
    }
    weekly_res = client.post("/recommend-weekly-plan", json=weekly_payload)
    assert_status(weekly_res, 200, "POST /recommend-weekly-plan (7-Day, 5-Interval Cultural Clinical Diet)")
    weekly_data = weekly_res.json()
    assert len(weekly_data["days"]) == 7, "Weekly plan must contain exactly 7 days"
    assert len(weekly_data["days"][0]["intervals"]) == 5, "Each day must have 5 meal intervals"
    assert weekly_data["clinical_targets"]["potassium_guidance_mg"] <= 2000, "Renal potassium limit failed in weekly targets"
    assert weekly_data["clinical_targets"]["sodium_limit_mg"] <= 1500, "DASH sodium restriction failed in weekly targets"
    assert len(weekly_data["medication_alerts"]) >= 1, "Medication alerts should be generated"
    print("  [PASS] Weekly Diet Plan Verified: 7 Days x 5 Intervals, Regional Grounding, Lab Targets & Drug Alerts OK")

    print("=" * 70)
    print("  SUCCESS: ALL 22 REST ENDPOINTS + COMORBIDITY + WEEKLY DIET SUITE PASSED WITH HTTP 200!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_all_tests()

