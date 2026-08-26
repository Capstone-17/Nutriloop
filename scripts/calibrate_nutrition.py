"""
Nutrient Knowledge Base Calibration and Clinical Rule Generator
================================================================
Generates multi-condition clinical suitability scoring rules from the
unified Indian & global food knowledge base (6,313 items) according to
KDOQI, ADA, and DASH dietary guidelines.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("calibrate_nutrition")

PROJECT_DIR = Path(__file__).resolve().parent.parent
FOOD_KB_PATH = PROJECT_DIR / "datasets" / "unified_food_kb.csv"
OUT_RULES = PROJECT_DIR / "artifacts" / "nutrient_calibration_rules.json"


def safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def rank_score(series: pd.Series, prefer_low: bool) -> pd.Series:
    s = series.copy()
    med = float(s.dropna().median()) if s.notna().any() else 0.0
    s = s.fillna(med)
    rank = s.rank(pct=True, method="average")
    return 1.0 - rank if prefer_low else rank


def tier_from_score(s: pd.Series) -> pd.Series:
    q1 = float(s.quantile(0.33))
    q2 = float(s.quantile(0.66))
    return pd.Series(
        np.where(s >= q2, "high", np.where(s >= q1, "moderate", "low")),
        index=s.index,
    )


def calibrate_and_export():
    if not FOOD_KB_PATH.exists():
        raise FileNotFoundError(f"Missing {FOOD_KB_PATH}")

    df = pd.read_csv(FOOD_KB_PATH)
    log.info(f"Loaded food KB with {len(df)} items.")

    numeric_cols = [
        "energy_kcal", "protein_g", "carbs_g", "sugars_free_g",
        "sodium_mg", "potassium_mg", "phosphorus_mg", "fiber_g", "data_completeness"
    ]
    df = safe_numeric(df, numeric_cols)

    # Disease Scoring Rules
    # CKD: Low Sodium, Low Potassium, Low Phosphorus, Controlled Protein
    s_ckd = (
        0.30 * rank_score(df["sodium_mg"], prefer_low=True)
        + 0.30 * rank_score(df["potassium_mg"], prefer_low=True)
        + 0.25 * rank_score(df["phosphorus_mg"], prefer_low=True)
        + 0.15 * rank_score(df["protein_g"], prefer_low=True)
    )

    # Hypertension: Low Sodium, High Potassium, High Fiber, Low Energy Density
    s_htn = (
        0.45 * rank_score(df["sodium_mg"], prefer_low=True)
        + 0.30 * rank_score(df["potassium_mg"], prefer_low=False)
        + 0.15 * rank_score(df["fiber_g"], prefer_low=False)
        + 0.10 * rank_score(df["energy_kcal"], prefer_low=True)
    )

    # Diabetes: Low Sugars, Low Carbs, High Fiber, Low Sodium
    s_diab = (
        0.40 * rank_score(df["sugars_free_g"], prefer_low=True)
        + 0.25 * rank_score(df["carbs_g"], prefer_low=True)
        + 0.25 * rank_score(df["fiber_g"], prefer_low=False)
        + 0.10 * rank_score(df["sodium_mg"], prefer_low=True)
    )

    rules_payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(FOOD_KB_PATH.name),
        "total_food_items": int(len(df)),
        "diseases": {
            "ckd": {
                "primary_guideline": "KDOQI Clinical Practice Guideline for Nutrition in CKD",
                "scoring_weights": {
                    "sodium_mg": {"weight": 0.30, "direction": "minimize"},
                    "potassium_mg": {"weight": 0.30, "direction": "minimize"},
                    "phosphorus_mg": {"weight": 0.25, "direction": "minimize"},
                    "protein_g": {"weight": 0.15, "direction": "moderate"},
                },
                "score_distribution": {
                    "mean": float(s_ckd.mean()),
                    "p50": float(s_ckd.median()),
                    "p90": float(s_ckd.quantile(0.90)),
                    "max": float(s_ckd.max()),
                },
                "recommended_categories": ["Vegetables", "Cereals & Millets", "Fruits (low K)"],
            },
            "hypertension": {
                "primary_guideline": "DASH (Dietary Approaches to Stop Hypertension) Eating Plan",
                "scoring_weights": {
                    "sodium_mg": {"weight": 0.45, "direction": "minimize"},
                    "potassium_mg": {"weight": 0.30, "direction": "maximize"},
                    "fiber_g": {"weight": 0.15, "direction": "maximize"},
                    "energy_kcal": {"weight": 0.10, "direction": "moderate"},
                },
                "score_distribution": {
                    "mean": float(s_htn.mean()),
                    "p50": float(s_htn.median()),
                    "p90": float(s_htn.quantile(0.90)),
                    "max": float(s_htn.max()),
                },
                "recommended_categories": ["Vegetables", "Legumes & Pulses", "Fruits", "Low-fat Dairy"],
            },
            "diabetes": {
                "primary_guideline": "American Diabetes Association (ADA) Standards of Medical Care in Diabetes",
                "scoring_weights": {
                    "sugars_free_g": {"weight": 0.40, "direction": "minimize"},
                    "carbs_g": {"weight": 0.25, "direction": "controlled"},
                    "fiber_g": {"weight": 0.25, "direction": "maximize"},
                    "sodium_mg": {"weight": 0.10, "direction": "minimize"},
                },
                "score_distribution": {
                    "mean": float(s_diab.mean()),
                    "p50": float(s_diab.median()),
                    "p90": float(s_diab.quantile(0.90)),
                    "max": float(s_diab.max()),
                },
                "recommended_categories": ["Non-starchy Vegetables", "Legumes", "Whole Grains", "Nuts & Seeds"],
            },
        },
    }

    OUT_RULES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_RULES, "w", encoding="utf-8") as f:
        json.dump(rules_payload, f, indent=2)

    log.info(f"Nutrient calibration rules exported to {OUT_RULES}")


if __name__ == "__main__":
    calibrate_and_export()
