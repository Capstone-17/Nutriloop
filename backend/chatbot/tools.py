"""
backend/chatbot/tools.py
─────────────────────────
The five grounded tool functions available to the diet chatbot agent.

Design
──────
Each function reads from the existing SQLite DB (via backend.db) or the
Unified Food Knowledge Base (via backend.reporting).  The chatbot agent
NEVER recomputes risk scores or diet targets — those come exclusively
from the sklearn classifiers already persisted in artifacts/.

Tool contract
─────────────
Every function returns a plain dict that is JSON-serialisable.  The
agent sees these dicts as tool_result strings inside its context.

The `log_interaction` tool writes to `risk_explanation_log` with
source='chatbot_interaction' so every chatbot turn is audited exactly
like existing API / terminal flows.  The schema already has this column
— no migration needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.db import (
    get_conn,
    insert_meal_log,
    insert_risk_explanation,
)
from backend.reporting import recommend_foods, food_kb

log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers not yet in db.py (added here to keep db.py clean)
# ──────────────────────────────────────────────────────────────────────────────

def _get_latest_risk_profile(user_id: str, disease: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the most-recent row in risk_explanation_log for this user/disease.
    Returns None if no record exists yet.
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            risk_score, risk_level, top_factors_json,
            threshold_band, threshold_moderate, threshold_high,
            calibration_context_json, created_at
        FROM risk_explanation_log
        WHERE user_id = ? AND disease = ? AND source <> 'chatbot_interaction'
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 1
        """,
        (user_id, disease),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "risk_score":    float(row["risk_score"]),
        "risk_level":    row["risk_level"],
        "top_factors":   json.loads(row["top_factors_json"]),
        "threshold_band": row["threshold_band"],
        "thresholds": {
            "moderate": float(row["threshold_moderate"]),
            "high":     float(row["threshold_high"]),
        },
        "calibration_context": json.loads(row["calibration_context_json"]),
        "recorded_at":   row["created_at"],
    }


def _get_latest_diet_plan(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the most-recent diet plan row for this user."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            disease, calories_target, protein_target_g, carb_target_g,
            fat_target_g, sodium_limit_mg, potassium_limit_mg,
            recommendation_note, created_at
        FROM diet_plan
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "disease":            row["disease"],
        "calories_target":    int(row["calories_target"]),
        "protein_target_g":   int(row["protein_target_g"]),
        "carb_target_g":      int(row["carb_target_g"]),
        "fat_target_g":       int(row["fat_target_g"]),
        "sodium_limit_mg":    int(row["sodium_limit_mg"]),
        "potassium_limit_mg": int(row["potassium_limit_mg"]),
        "recommendation_note": row["recommendation_note"],
        "created_at":         row["created_at"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 1 — get_risk_profile
# ──────────────────────────────────────────────────────────────────────────────

def get_risk_profile(user_id: str, disease: str) -> Dict[str, Any]:
    """
    Pull the already-computed risk profile from risk_explanation_log.

    The agent reads this; it NEVER recomputes the risk score.

    Returns
    -------
    dict with keys: risk_score, risk_level, top_factors, threshold_band,
                    thresholds, calibration_context, recorded_at
    OR
    dict with key: error  (if no profile exists for this user/disease)
    """
    profile = _get_latest_risk_profile(user_id, disease)
    if profile is None:
        return {
            "error": (
                f"No risk profile found for user_id='{user_id}' and disease='{disease}'. "
                "The user may not have been assessed yet.  "
                "Ask them to complete a risk assessment first."
            )
        }

    log.info(
        "[tool:get_risk_profile] user=%s disease=%s → level=%s score=%.4f",
        user_id, disease, profile["risk_level"], profile["risk_score"],
    )
    return profile


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2 — get_diet_plan
# ──────────────────────────────────────────────────────────────────────────────

def get_diet_plan(user_id: str) -> Dict[str, Any]:
    """
    Return the user's current active diet plan from the diet_plan table.

    Returns
    -------
    dict with plan fields  OR  dict with key: error
    """
    plan = _get_latest_diet_plan(user_id)
    if plan is None:
        return {
            "error": (
                f"No diet plan found for user_id='{user_id}'.  "
                "The user may not have completed a risk assessment + plan generation yet."
            )
        }

    log.info(
        "[tool:get_diet_plan] user=%s disease=%s cal=%d sodium_limit=%d",
        user_id, plan["disease"], plan["calories_target"], plan["sodium_limit_mg"],
    )
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# Tool 3 — search_food_kb
# ──────────────────────────────────────────────────────────────────────────────

def search_food_kb(
    query: str,
    disease: str,
    exclude: Optional[List[str]] = None,
    top_n: int = 6,
) -> Dict[str, Any]:
    """
    RAG lookup against the Unified Food Knowledge Base.

    1. Pre-filter food_name by `query` substring (case-insensitive).
       If no matches, fall back to full KB.
    2. Apply `exclude` as substring exclusions (e.g., ["dairy", "milk"]
       for a no-dairy constraint).
    3. Score with the existing disease-aware nutrient-calibration scorer
       (backend.reporting.recommend_foods internals).
    4. Return top_n results.

    This grounds all food-nutrient numbers in the real KB instead of
    letting the LLM hallucinate nutrition values.
    """
    df = food_kb.df

    if df.empty:
        return {"error": "Food knowledge base is not loaded.  Check the CSV path."}

    # Retrieve a mock diet plan dict for scoring (use disease defaults)
    plan_defaults = {
        "ckd":          {"sodium_limit_mg": 2000, "potassium_limit_mg": 2000,
                         "calories_target": 2000, "phosphorus_limit_mg": 1000},
        "hypertension": {"sodium_limit_mg": 1800, "potassium_limit_mg": 3000,
                         "calories_target": 2000, "fiber_target_g": 30},
        "diabetes":     {"sodium_limit_mg": 2300, "potassium_limit_mg": 3500,
                         "calories_target": 2000, "sugar_limit_g": 30,
                         "carb_target_g": 220},
    }
    plan = plan_defaults.get(disease, {"sodium_limit_mg": 2000,
                                        "potassium_limit_mg": 3500,
                                        "calories_target": 2000})

    work = df.copy()

    # Pre-filter by query substring
    if query:
        mask = work["food_name"].str.contains(query, case=False, na=False)
        filtered_by_query = work[mask]
        if not filtered_by_query.empty:
            work = filtered_by_query

    # Apply exclusion list (dietary restrictions)
    if exclude:
        for excl in exclude:
            excl_mask = ~work["food_name"].str.contains(excl, case=False, na=False)
            if "food_category" in work.columns:
                excl_mask &= ~work["food_category"].str.contains(excl, case=False, na=False)
            work = work[excl_mask]

    if work.empty:
        return {"results": [], "note": "No matching foods found after applying filters."}

    # Temporarily override the global food_kb df for scoring
    # (recommend_foods reads food_kb.df internally)
    from backend import reporting as _rep
    original_df = _rep.food_kb._df
    _rep.food_kb._df = work

    try:
        results = recommend_foods(disease, "moderate", plan, top_n=top_n)
    finally:
        _rep.food_kb._df = original_df

    log.info(
        "[tool:search_food_kb] query='%s' disease=%s exclude=%s → %d results",
        query, disease, exclude, len(results),
    )
    return {"results": results, "query": query, "disease": disease}


# ──────────────────────────────────────────────────────────────────────────────
# Tool 4 — log_meal
# ──────────────────────────────────────────────────────────────────────────────

def log_meal(user_id: str, food_name: str, portion_g: float) -> Dict[str, Any]:
    """
    Log a meal for the user by looking up the food in the KB and computing
    calorie deviation against their current plan.

    Users never type free-form calorie totals — the KB lookup grounds the
    calorie estimate.  If the food is not found, returns an error asking
    the user to try a different search term.

    Wraps existing insert_meal_log() so the meal_log table is updated.
    """
    df = food_kb.df
    if df.empty:
        return {"error": "Food knowledge base not loaded."}

    # Look up food
    matches = df[df["food_name"].str.contains(food_name, case=False, na=False)]
    if matches.empty:
        return {
            "error": (
                f"Could not find '{food_name}' in the food knowledge base.  "
                "Try a shorter or different search term."
            )
        }

    food_row = matches.iloc[0]
    kcal_per_100g = float(food_row.get("energy_kcal", 100) or 100)
    consumed_kcal = int(round(kcal_per_100g * portion_g / 100))

    # Get planned calories from the user's diet plan
    plan = _get_latest_diet_plan(user_id)
    planned_kcal = int(plan["calories_target"] / 3) if plan else 667  # default 1/3 of 2000 kcal

    # Compute deviation
    deviation_pct = abs(consumed_kcal - planned_kcal) / max(planned_kcal, 1) * 100
    deviation_flag = deviation_pct >= 15.0
    severity = "high" if deviation_pct >= 25 else "medium" if deviation_pct >= 15 else "low"

    notes = (
        f"Food: {food_row['food_name']} | Portion: {portion_g:.0f}g | "
        f"Estimated kcal: {consumed_kcal} | Deviation: {deviation_pct:.1f}% ({severity})"
    )

    meal_id = insert_meal_log(
        user_id=user_id,
        planned_calories=planned_kcal,
        consumed_calories=consumed_kcal,
        deviation_flag=deviation_flag,
        deviation_percent=deviation_pct,
        notes=notes,
    )

    log.info(
        "[tool:log_meal] user=%s food='%s' portion=%.0fg kcal=%d dev=%.1f%%",
        user_id, food_row["food_name"], portion_g, consumed_kcal, deviation_pct,
    )

    return {
        "meal_id":        meal_id,
        "food_matched":   str(food_row["food_name"]),
        "portion_g":      portion_g,
        "consumed_kcal":  consumed_kcal,
        "planned_kcal":   planned_kcal,
        "deviation_pct":  round(deviation_pct, 1),
        "deviation_flag": deviation_flag,
        "severity":       severity,
        "notes":          notes,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 5 — log_interaction
# ──────────────────────────────────────────────────────────────────────────────

def log_interaction(user_id: str, turn_summary: str, disease: str) -> Dict[str, Any]:
    """
    Write a chatbot turn to risk_explanation_log with source='chatbot_interaction'.

    This ensures every chatbot conversation is audited exactly like API and
    terminal-mode interactions — the same source-discriminated audit trail
    described in backend/db.py.

    We reuse insert_risk_explanation() with placeholder values for fields
    that don't apply to a conversational turn (scores set to -1.0 to
    signal "chatbot log entry, not a classifier output").
    """
    now = datetime.now(timezone.utc).isoformat()
    log_id = insert_risk_explanation(
        disease=disease or "general",
        model_name="llama3.2:3b (chatbot)",
        predicted_class=-1,
        risk_score=-1.0,
        risk_level="chatbot_turn",
        threshold_moderate=0.0,
        threshold_high=0.0,
        threshold_band="chatbot_interaction",
        major_risk_factors=[],
        validation_warnings=[],
        raw_inputs={"turn_summary": turn_summary, "logged_at": now},
        transformed_features={},
        top_factors=[],
        calibration_context={},
        explanation_text=turn_summary,
        user_id=user_id,
        source="chatbot_interaction",
    )

    log.info(
        "[tool:log_interaction] user=%s disease=%s log_id=%d",
        user_id, disease, log_id,
    )
    return {"log_id": log_id, "status": "logged"}


# ──────────────────────────────────────────────────────────────────────────────
# Tool dispatch registry (used by agent.py)
# ──────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "get_risk_profile":  get_risk_profile,
    "get_diet_plan":     get_diet_plan,
    "search_food_kb":    search_food_kb,
    "log_meal":          log_meal,
    "log_interaction":   log_interaction,
}
