from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


import sys

def _get_bundle_dir() -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_bundle_dir()
FOOD_KB_PATH = BASE_DIR / "datasets" / "unified_food_kb.csv"
if not FOOD_KB_PATH.exists():
    FOOD_KB_PATH = BASE_DIR / "medical datasets" / "raw" / "unified_food_kb_20260222_093221.csv"
NUTRIENT_CALIBRATION_PATH = BASE_DIR / "artifacts" / "nutrient_calibration_rules.json"


class FoodKB:
    def __init__(self) -> None:
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> None:
        if self._df is not None:
            return
        if not FOOD_KB_PATH.exists():
            self._df = pd.DataFrame()
            return

        df = pd.read_csv(FOOD_KB_PATH)
        keep_cols = [
            "food_name",
            "food_category",
            "energy_kcal",
            "protein_g",
            "carbs_g",
            "sugars_free_g",
            "sodium_mg",
            "potassium_mg",
            "phosphorus_mg",
            "fiber_g",
            "data_completeness",
        ]
        self._df = df[[c for c in keep_cols if c in df.columns]].copy()

        numeric_cols = [
            "energy_kcal",
            "protein_g",
            "carbs_g",
            "sugars_free_g",
            "sodium_mg",
            "potassium_mg",
            "phosphorus_mg",
            "fiber_g",
            "data_completeness",
        ]
        for col in numeric_cols:
            if col in self._df.columns:
                self._df[col] = pd.to_numeric(self._df[col], errors="coerce")

        self._df = self._df.dropna(subset=["food_name"]).drop_duplicates(subset=["food_name"])

    @property
    def df(self) -> pd.DataFrame:
        self.load()
        return self._df if self._df is not None else pd.DataFrame()


food_kb = FoodKB()


def _load_nutrient_calibration() -> Dict[str, Any]:
    if not NUTRIENT_CALIBRATION_PATH.exists():
        return {}
    try:
        return json.loads(NUTRIENT_CALIBRATION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _disease_rules(disease: str) -> Dict[str, Any]:
    cfg = _load_nutrient_calibration()
    return cfg.get("diseases", {}).get(disease, {})


def _score_foods(df: pd.DataFrame, disease: str, risk_level: str, plan: Dict[str, Any]) -> pd.DataFrame:
    work = df.copy()
    d_clean = disease.lower()
    has_ckd = "ckd" in d_clean
    has_htn = "hypertension" in d_clean
    has_diabetes = "diabetes" in d_clean

    rules = _disease_rules("ckd" if has_ckd else ("hypertension" if has_htn else "diabetes"))
    weights = rules.get("weights", {})

    sodium_limit = float(plan.get("sodium_limit_mg", 2000))
    potassium_limit = float(plan.get("potassium_limit_mg", 3500))
    calories_target = float(plan.get("calories_target", 2000))
    sugar_limit = float(plan.get("sugar_limit_g", 40) or 40)
    phosphorus_limit = float(plan.get("phosphorus_limit_mg", 1200) or 1200)
    fiber_target = float(plan.get("fiber_target_g", 25) or 25)

    work["score"] = 0.0

    if "sodium_mg" in work.columns:
        sodium_w = float(weights.get("sodium_low_better", 0.4))
        work["score"] += (1.0 - (work["sodium_mg"].fillna(sodium_limit) / max(sodium_limit, 1.0))).clip(0, 1) * sodium_w

    if "potassium_mg" in work.columns:
        pot_weight = float(weights.get("potassium_low_better", 0.35 if has_ckd else 0.2))
        work["score"] += (1.0 - (work["potassium_mg"].fillna(potassium_limit) / max(potassium_limit, 1.0))).clip(0, 1) * pot_weight

    if "energy_kcal" in work.columns:
        energy_target = max(80.0, calories_target / 8.0)
        work["score"] += (1.0 - (work["energy_kcal"].fillna(energy_target) / energy_target)).abs().clip(0, 1) * 0.1

    if has_diabetes and "sugars_free_g" in work.columns:
        sugar_w = float(weights.get("sugar_low_better", 0.30))
        work["score"] += (1.0 - (work["sugars_free_g"].fillna(sugar_limit) / max(sugar_limit, 1.0))).clip(0, 1) * sugar_w
        if "carbs_g" in work.columns:
            carbs_w = float(weights.get("carbs_low_better", 0.15))
            work["score"] += (1.0 - (work["carbs_g"].fillna(plan.get("carb_target_g", 50)) / max(float(plan.get("carb_target_g", 50)), 1.0))).clip(0, 1) * carbs_w

    if has_htn and "fiber_g" in work.columns:
        fiber_w = float(weights.get("fiber_high_better", 0.20))
        work["score"] += (work["fiber_g"].fillna(0.0) / max(fiber_target, 1.0)).clip(0, 1) * fiber_w

    if has_ckd and "phosphorus_mg" in work.columns:
        phos_w = float(weights.get("phosphorus_low_better", 0.30))
        work["score"] += (1.0 - (work["phosphorus_mg"].fillna(phosphorus_limit) / max(phosphorus_limit, 1.0))).clip(0, 1) * phos_w

    if "data_completeness" in work.columns:
        comp_w = float(weights.get("completeness_high_better", 0.1))
        work["score"] += work["data_completeness"].fillna(0.0).clip(0, 1) * comp_w

    return work



def recommend_foods(disease: str, risk_level: str, plan: Dict[str, Any], top_n: int = 8) -> List[Dict[str, Any]]:
    df = food_kb.df
    if df.empty:
        return []

    filtered = df.copy()

    if "data_completeness" in filtered.columns:
        filtered = filtered[(filtered["data_completeness"].isna()) | (filtered["data_completeness"] >= 0.7)]

    key_cols = [c for c in ["sodium_mg", "potassium_mg", "phosphorus_mg"] if c in filtered.columns]
    if key_cols:
        filtered = filtered[~((filtered[key_cols].fillna(0) <= 0).all(axis=1))]

    rules = _disease_rules(disease)
    caps = rules.get("caps", {}).get(risk_level, {})

    sodium_factor = {"low": 1.2, "moderate": 1.0, "high": 0.85}.get(risk_level, 1.0)
    potassium_factor = {"low": 1.2, "moderate": 1.0, "high": 0.85}.get(risk_level, 1.0)

    sodium_cap = float(caps.get("sodium_mg", float(plan.get("sodium_limit_mg", 2000)) * sodium_factor))
    potassium_cap = float(caps.get("potassium_mg", float(plan.get("potassium_limit_mg", 3500)) * potassium_factor))

    if "sodium_mg" in filtered.columns:
        filtered = filtered[(filtered["sodium_mg"].isna()) | (filtered["sodium_mg"] <= sodium_cap)]
    if "potassium_mg" in filtered.columns:
        filtered = filtered[(filtered["potassium_mg"].isna()) | (filtered["potassium_mg"] <= potassium_cap)]

    if disease == "diabetes" and "sugars_free_g" in filtered.columns:
        sugar_cap = float(caps.get("sugars_free_g", float(plan.get("sugar_limit_g", 40) or 40)))
        filtered = filtered[(filtered["sugars_free_g"].isna()) | (filtered["sugars_free_g"] <= sugar_cap)]
        if "carbs_g" in filtered.columns:
            carbs_cap = float(caps.get("carbs_g", float(plan.get("carb_target_g", 220)) / 3.0))
            filtered = filtered[(filtered["carbs_g"].isna()) | (filtered["carbs_g"] <= carbs_cap)]

    if disease == "ckd" and "phosphorus_mg" in filtered.columns:
        phosphorus_cap = float(caps.get("phosphorus_mg", float(plan.get("phosphorus_limit_mg", 1200) or 1200)))
        filtered = filtered[(filtered["phosphorus_mg"].isna()) | (filtered["phosphorus_mg"] <= phosphorus_cap)]

    if filtered.empty:
        filtered = df.copy()

    scored = _score_foods(filtered, disease, risk_level, plan)
    top = scored.sort_values("score", ascending=False).head(max(1, top_n))

    records = []
    for row in top.to_dict(orient="records"):
        records.append(
            {
                "food_name": row.get("food_name"),
                "food_category": row.get("food_category"),
                "energy_kcal": row.get("energy_kcal"),
                "protein_g": row.get("protein_g"),
                "carbs_g": row.get("carbs_g"),
                "sugars_free_g": row.get("sugars_free_g"),
                "sodium_mg": row.get("sodium_mg"),
                "potassium_mg": row.get("potassium_mg"),
                "phosphorus_mg": row.get("phosphorus_mg"),
                "food_score": round(float(row.get("score", 0.0)), 6),
            }
        )

    return records


def build_report_text(
    disease: str,
    risk_score: float,
    risk_level: str,
    top_factors: List[Dict[str, Any]],
    calibration_context: Optional[Dict[str, Any]] = None,
) -> str:
    factor_list = ", ".join([str(item.get("feature")) for item in top_factors[:5]])
    context = calibration_context or {}
    threshold_band = context.get("threshold_band", "unknown")
    major_factors = context.get("major_risk_factors", [])
    major_factor_text = ", ".join(major_factors) if major_factors else "none highlighted"
    disease_guidance = {
        "ckd": "Meal calibration emphasizes sodium, potassium, protein, and phosphorus control.",
        "hypertension": "Meal calibration emphasizes sodium reduction, calorie discipline, and fiber-rich choices.",
        "diabetes": "Meal calibration emphasizes carbohydrate quality, lower added sugar, and fiber support.",
    }.get(disease, "Meal calibration follows disease-specific dietary constraints.")
    return (
        f"{disease.title()} risk assessment completed. "
        f"Risk score is {risk_score:.4f} ({risk_level} risk band). "
        f"Most influential factors for this disease model include: {factor_list}. "
        f"Threshold band: {threshold_band}. Highlighted risk factors for calibration: {major_factor_text}. "
        f"{disease_guidance} "
        "Diet recommendations are filtered from the unified nutrition knowledge base "
        "to align with disease-specific metabolic constraints."
    )


def build_explanation_text(
    disease: str,
    risk_score: float,
    risk_level: str,
    threshold_band: str,
    major_risk_factors: List[str],
    validation_warnings: Optional[List[str]] = None,
) -> str:
    factor_text = ", ".join(major_risk_factors) if major_risk_factors else "no dominant factors surfaced"
    warning_hint = ""
    if validation_warnings:
        warning_hint = " Compatibility warnings were detected for some fields in the deployed model path."
    return (
        f"{disease.title()} explanation: score={risk_score:.4f}, level={risk_level}, "
        f"band={threshold_band}. Major factors: {factor_text}.{warning_hint}"
    )


def build_risk_report(
    disease: str,
    predicted_class: int,
    risk_score: float,
    model_name: str,
    thresholds: Dict[str, float],
    top_factors: List[Dict[str, Any]],
    transformed_features: Optional[Dict[str, float]] = None,
    raw_inputs: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    profile: Optional[Dict[str, Any]] = None,
    top_n_foods: int = 5,
) -> Dict[str, Any]:
    from backend.rules import build_calibration_context, build_plan, classify_risk_level

    risk_level = classify_risk_level(risk_score, thresholds)
    calib = build_calibration_context(
        disease=disease,
        risk_score=risk_score,
        thresholds=thresholds,
        top_factors=top_factors,
        transformed_features=transformed_features,
    )
    plan = build_plan(disease, risk_score, profile or {}, thresholds, calib)
    foods = recommend_foods(disease, risk_level, plan=plan, top_n=top_n_foods)
    report_text = build_report_text(disease, risk_score, risk_level, top_factors, calib)

    return {
        "disease": disease,
        "predicted_class": predicted_class,
        "risk_score": float(risk_score),
        "risk_level": risk_level,
        "model_name": model_name,
        "thresholds": thresholds,
        "top_factors": top_factors,
        "calibration_context": calib,
        "plan": plan,
        "recommended_foods": foods,
        "report_text": report_text,
        "transformed_features": transformed_features or {},
        "raw_inputs": raw_inputs,
        "validation_warnings": warnings or [],
    }
