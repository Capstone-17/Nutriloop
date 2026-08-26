"""
Comparative Model Benchmark Suite
=================================
Evaluates all trained models in Latest_Update against baseline implementations
and generates a structured comparison report with Macro-F1, PR-AUC, ROC-AUC,
Sensitivity/Recall, Specificity, and Brier calibration scores.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("benchmark")

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "datasets" / "preprocessed"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"


def benchmark():
    with open(ARTIFACTS_DIR / "risk_thresholds_and_factors.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)

    results = []

    for disease in ["ckd", "hypertension", "diabetes"]:
        model_path = ARTIFACTS_DIR / f"{disease}_model.joblib"
        feat_path = ARTIFACTS_DIR / f"{disease}_features.json"
        test_path = DATA_DIR / f"{disease}_test.csv"

        if not model_path.exists() or not test_path.exists():
            continue

        model = joblib.load(model_path)
        with open(feat_path, "r", encoding="utf-8") as f:
            features = json.load(f)

        test_df = pd.read_csv(test_path)
        target_col = test_df.columns[-1]
        X_test = test_df[features].values
        y_test = test_df[target_col].values.astype(int)

        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test)[:, 1]
        else:
            y_prob = model.decision_function(X_test)
            y_prob = 1.0 / (1.0 + np.exp(-y_prob))

        mod_th = profiles[disease]["thresholds"]["moderate"]
        y_pred = (y_prob >= mod_th).astype(int)

        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        prec = precision_score(y_test, y_pred, zero_division=0)
        tn = np.sum((y_test == 0) & (y_pred == 0))
        fp = np.sum((y_test == 0) & (y_pred == 1))
        spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

        try:
            roc = roc_auc_score(y_test, y_prob)
        except Exception:
            roc = 0.5

        try:
            p_curve, r_curve, _ = precision_recall_curve(y_test, y_prob)
            pr = float(auc(r_curve, p_curve))
        except Exception:
            pr = 0.0

        brier = brier_score_loss(y_test, y_prob)

        results.append({
            "disease": disease.upper(),
            "model_type": profiles[disease]["model_name"],
            "moderate_threshold": mod_th,
            "accuracy": round(acc, 4),
            "macro_f1": round(f1, 4),
            "recall_positive": round(rec, 4),
            "precision_positive": round(prec, 4),
            "specificity": round(spec, 4),
            "pr_auc": round(pr, 4),
            "roc_auc": round(roc, 4),
            "brier_score": round(brier, 4),
        })

    df_res = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print("                 LATEST_UPDATE CLINICAL MODEL BENCHMARK RESULTS")
    print("=" * 80)
    print(df_res.to_string(index=False))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    benchmark()
