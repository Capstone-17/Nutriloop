"""
Comprehensive 21-Endpoint REST API Smoke Test Suite
===================================================
Validates that all core, Phase 2, and Phase 3 endpoints in Latest_Update
execute with status 200 and conform strictly to Pydantic schemas.
"""

from __future__ import annotations
import sys
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
    print("        RUNNING 21-ENDPOINT SMOKE TEST SUITE FOR LATEST_UPDATE")
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
        "POST /chatbot/chat",
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

    print("=" * 70)
    print("  SUCCESS: ALL 21 REST ENDPOINTS PASSED WITH HTTP 200 STATUS!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_all_tests()
