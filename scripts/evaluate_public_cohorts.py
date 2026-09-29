"""Leakage-conscious, source-specific exploratory evaluation for public cohorts.

This script does not provide clinical validation. It evaluates each public
source independently, performs all imputation/encoding/scaling inside each
training fold, does not oversample, and never tunes a threshold on validation
folds. Raw files are supplied by the user and are not copied into the repo.
"""

from __future__ import annotations

import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, StackingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.dummy import DummyClassifier


SEED = 42
FOLDS = 5
TARGET_FEATURE_CAVEATS = {
    "ckd_uci": "Concurrent CKD label with same-source clinical findings; target and feature timing are not clinically adjudicated.",
    "hypertension_framingham": "Prevalent-hypertension label with contemporaneous BP measurements; target/reference construction requires verification.",
    "diabetes_pima": "Current diabetes label with glucose among predictors; glucose may be target-proximal.",
    "diabetes_nhanes": "Self-reported prior clinician diagnosis with current survey/lab features; this is not lab-adjudicated current disease.",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_ckd_arff_from_rar(path: Path) -> tuple[pd.DataFrame, bytes, dict[str, Any], list[str]]:
    """Read the full ARFF member through tar without extracting the archive."""
    tar = shutil.which("tar")
    if tar is None:
        raise RuntimeError("A system 'tar' command capable of reading RAR files is required for CKD.")
    member = "Chronic_Kidney_Disease/chronic_kidney_disease_full.arff"
    proc = subprocess.run([tar, "-xOf", str(path), member], check=True, capture_output=True)
    content = proc.stdout
    columns: list[str] = []
    numeric_columns: list[str] = []
    records: list[list[str]] = []
    malformed_rows = 0
    normalized_trailing_delimiters = 0
    in_data = False
    for line in content.decode("utf-8", errors="replace").splitlines():
        row = line.strip()
        if not row or row.startswith("%"):
            continue
        if row.lower().startswith("@attribute"):
            parts = row.split()
            if len(parts) < 3:
                raise ValueError(f"Could not parse ARFF attribute declaration: {row}")
            column = parts[1].strip("'\"")
            columns.append(column)
            if parts[-1].lower() == "numeric":
                numeric_columns.append(column)
        elif row.lower().startswith("@data"):
            in_data = True
        elif in_data:
            values = [value.strip().strip("'\"") for value in row.split(",")]
            if len(values) == len(columns) + 1 and values[-1] == "":
                values.pop()
                normalized_trailing_delimiters += 1
            if len(values) != len(columns):
                malformed_rows += 1
                continue
            records.append(values)
    if not columns:
        raise ValueError("CKD ARFF is missing attribute declarations.")
    frame = pd.DataFrame(records, columns=columns).replace({"?": np.nan, "": np.nan})
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame, content, {
        "raw_data_rows": len(records) + malformed_rows,
        "malformed_rows_excluded": malformed_rows,
        "empty_trailing_delimiters_normalized": normalized_trailing_delimiters,
    }, numeric_columns


def make_cohorts(data_root: Path) -> tuple[dict[str, tuple[pd.DataFrame, pd.Series, pd.Series | None, dict[str, Any]]], dict[str, Any]]:
    cohorts = {}
    provenance = {}

    ckd_archive = data_root / "chronic+kidney+disease" / "Chronic_Kidney_Disease.rar"
    ckd, ckd_arff, ckd_parse, ckd_numeric_features = read_ckd_arff_from_rar(ckd_archive)
    ckd_target = ckd["class"].astype("string").str.strip().str.lower().map({"ckd": 1, "notckd": 0})
    ckd_x = ckd.drop(columns=["class"]).copy()
    ckd_features_sha = hashlib.sha256(ckd_arff).hexdigest()
    cohorts["ckd_uci"] = (ckd_x, ckd_target, None, {
        "source_file": str(ckd_archive.name), "source_sha256": sha256(ckd_archive),
        "source_member": "Chronic_Kidney_Disease/chronic_kidney_disease_full.arff",
        "member_sha256": ckd_features_sha, "excluded_unlabeled_target_rows": int(ckd_target.isna().sum()),
        "numeric_features_from_arff_schema": ckd_numeric_features,
        **ckd_parse,
        "class_counts_before_split": {str(key): int(value) for key, value in ckd_target.value_counts().sort_index().items()},
    })

    framingham_path = data_root / "hypertension" / "framingham_heart_study.csv"
    framingham = pd.read_csv(framingham_path)
    framingham = framingham.drop(columns=["TenYearCHD"], errors="ignore")
    htn_target = pd.to_numeric(framingham.pop("prevalentHyp"), errors="coerce")
    htn_groups = None
    cohorts["hypertension_framingham"] = (framingham, htn_target, htn_groups, {
        "source_file": framingham_path.name, "source_sha256": sha256(framingham_path),
        "group_id_column": None,
        "class_counts_before_split": {str(key): int(value) for key, value in htn_target.value_counts().sort_index().items()},
    })

    pima_path = data_root / "diabetes" / "diabetes.csv"
    pima = pd.read_csv(pima_path)
    pima_target = pd.to_numeric(pima.pop("Outcome"), errors="coerce")
    for column in ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]:
        if column in pima:
            pima.loc[pima[column] == 0, column] = np.nan
    cohorts["diabetes_pima"] = (pima, pima_target, None, {
        "source_file": pima_path.name, "source_sha256": sha256(pima_path),
        "group_id_column": None,
        "zero_to_missing_columns": ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"],
        "class_counts_before_split": {str(key): int(value) for key, value in pima_target.value_counts().sort_index().items()},
    })

    nhanes_path = data_root / "NHANES_2017_2018" / "NHANES_2017_2018_MERGED.csv"
    nhanes = pd.read_csv(nhanes_path)
    nhanes_target_raw = pd.to_numeric(nhanes["DIQ010"], errors="coerce")
    nhanes_target = nhanes_target_raw.map({1: 1, 2: 0})
    nhanes_x = pd.DataFrame({
        "age_years": nhanes["RIDAGEYR"],
        "sex_code": nhanes["RIAGENDR"],
        "bmi": nhanes["BMXBMI"],
        "fasting_glucose_mg_dl": nhanes["LBXGLU"],
        "systolic_bp_1": nhanes["BPXSY1"],
        "systolic_bp_2": nhanes["BPXSY2"],
        "systolic_bp_3": nhanes["BPXSY3"],
        "diastolic_bp_1": nhanes["BPXDI1"],
        "diastolic_bp_2": nhanes["BPXDI2"],
        "diastolic_bp_3": nhanes["BPXDI3"],
    })
    nhanes_groups = nhanes["SEQN"].astype("string") if "SEQN" in nhanes else None
    cohorts["diabetes_nhanes"] = (nhanes_x, nhanes_target, nhanes_groups, {
        "source_file": nhanes_path.name, "source_sha256": sha256(nhanes_path),
        "group_id_column": "SEQN" if nhanes_groups is not None else None,
        "excluded_indeterminate_or_missing_target_rows": int(nhanes_target.isna().sum()),
        "class_counts_before_split": {str(key): int(value) for key, value in nhanes_target.value_counts().sort_index().items()},
        "diq010_raw_codes": {str(key): int(value) for key, value in nhanes_target_raw.value_counts(dropna=False).items()},
    })
    return cohorts, provenance


def make_pipeline(model_name: str, X: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    numeric = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in X.columns if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ]), numeric))
    if categorical:
        transformers.append(("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categorical))
    prep = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    models = {
        "majority_baseline": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, random_state=SEED)),
        ]),
        "logistic_regression_balanced": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED)),
        ]),
        "random_forest_balanced": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, class_weight="balanced",
            random_state=SEED, n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=15, l2_regularization=1.0,
            random_state=SEED,
        ),
        "gaussian_nb": GaussianNB(),
        "rbf_svm_balanced": SVC(
            C=2.0, kernel="rbf", probability=True, class_weight="balanced",
            random_state=SEED,
        ),
        "knn_distance": KNeighborsClassifier(n_neighbors=5, weights="distance"),
        "stacking_ensemble": StackingClassifier(
            estimators=[
                ("rf", RandomForestClassifier(
                    n_estimators=150, max_depth=6, class_weight="balanced",
                    random_state=SEED, n_jobs=-1,
                )),
                ("hgb", HistGradientBoostingClassifier(
                    max_iter=100, max_leaf_nodes=15, random_state=SEED,
                )),
                ("lr", LogisticRegression(
                    max_iter=2000, class_weight="balanced", random_state=SEED,
                )),
            ],
            final_estimator=LogisticRegression(max_iter=2000, random_state=SEED),
            cv=5,
            n_jobs=-1,
        ),
    }
    try:
        from xgboost import XGBClassifier
        positive = int((y_train == 1).sum())
        negative = int((y_train == 0).sum())
        models["xgboost_balanced"] = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            scale_pos_weight=negative / positive, random_state=SEED,
            eval_metric="logloss", n_jobs=-1,
        )
    except ImportError:
        pass
    return Pipeline([("preprocess", prep), ("scale", StandardScaler()), ("model", models[model_name])])


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_probability: np.ndarray) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in cm.ravel())
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1], zero_division=0)
    try:
        roc = float(roc_auc_score(y_true, y_probability))
    except ValueError:
        roc = None
    return {
        "threshold": 0.5,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "sensitivity": float(tp / (tp + fn)) if tp + fn else None,
        "specificity": float(tn / (tn + fp)) if tn + fp else None,
        "pr_auc": float(average_precision_score(y_true, y_probability)),
        "roc_auc": roc,
        "brier_score": float(brier_score_loss(y_true, y_probability)),
        "per_class": {
            "0": {"precision": float(p[0]), "recall": float(r[0]), "f1": float(f[0])},
            "1": {"precision": float(p[1]), "recall": float(r[1]), "f1": float(f[1])},
        },
        "confusion_matrix_labels_0_1": cm.astype(int).tolist(),
    }


def summarize_metrics(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["accuracy", "macro_precision", "macro_recall", "macro_f1", "sensitivity", "specificity", "pr_auc", "roc_auc", "brier_score"]
    summary: dict[str, Any] = {}
    for field in fields:
        values = np.asarray([m[field] for m in fold_metrics if m[field] is not None], dtype=float)
        summary[field] = {"mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0, "n_folds": int(len(values))}
    summary["per_class"] = {}
    for cls in ("0", "1"):
        summary["per_class"][cls] = {}
        for metric in ("precision", "recall", "f1"):
            values = np.asarray([m["per_class"][cls][metric] for m in fold_metrics], dtype=float)
            summary["per_class"][cls][metric] = {
                "mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            }
    summary["confusion_matrix_sum_labels_0_1"] = np.sum(
        [m["confusion_matrix_labels_0_1"] for m in fold_metrics], axis=0
    ).astype(int).tolist()
    return summary


def xgboost_available() -> bool:
    try:
        from importlib.util import find_spec
        return find_spec("xgboost") is not None
    except (ImportError, ValueError):
        return False


def evaluate_cohort(name: str, data: tuple[pd.DataFrame, pd.Series, pd.Series | None, dict[str, Any]]) -> dict[str, Any]:
    X, y_raw, groups, metadata = data
    valid = y_raw.notna()
    X = X.loc[valid].reset_index(drop=True)
    y = y_raw.loc[valid].astype(int).reset_index(drop=True)
    groups = groups.loc[valid].reset_index(drop=True) if groups is not None else None
    class_counts = y.value_counts().sort_index()
    if len(class_counts) != 2 or int(class_counts.min()) < FOLDS:
        raise ValueError(f"{name}: insufficient class counts for {FOLDS}-fold stratified evaluation: {class_counts.to_dict()}")
    if groups is not None:
        splitter = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
        split_iter = splitter.split(X, y, groups)
        split_method = "StratifiedGroupKFold by record ID"
    else:
        splitter = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
        split_iter = splitter.split(X, y)
        split_method = "StratifiedKFold by row; source has no record ID, patient independence unverified"
    splits = list(split_iter)
    if any(set(y.iloc[train].unique()) != {0, 1} or set(y.iloc[test].unique()) != {0, 1} for train, test in splits):
        raise ValueError(f"{name}: a fold does not contain both outcome classes.")

    model_names = ["majority_baseline", "logistic_regression", "logistic_regression_balanced", "random_forest_balanced", "hist_gradient_boosting", "gaussian_nb", "rbf_svm_balanced", "knn_distance", "stacking_ensemble"]
    if xgboost_available():
        model_names.append("xgboost_balanced")
    outputs: dict[str, Any] = {}
    for model_name in model_names:
        fold_metrics = []
        for fold, (train_idx, test_idx) in enumerate(splits, start=1):
            y_train = y.iloc[train_idx]
            model = make_pipeline(model_name, X, y_train)
            model.fit(X.iloc[train_idx], y_train)
            y_prob = model.predict_proba(X.iloc[test_idx])[:, 1]
            y_pred = (y_prob >= 0.5).astype(int)
            metrics = calculate_metrics(y.iloc[test_idx].to_numpy(), y_pred, y_prob)
            metrics["fold"] = fold
            metrics["n_train"] = int(len(train_idx))
            metrics["n_test"] = int(len(test_idx))
            metrics["training_class_counts_before_resampling"] = {
                str(key): int(value) for key, value in y.iloc[train_idx].value_counts().sort_index().items()
            }
            metrics["training_class_counts_after_resampling"] = dict(metrics["training_class_counts_before_resampling"])
            metrics["test_class_counts"] = {
                str(key): int(value) for key, value in y.iloc[test_idx].value_counts().sort_index().items()
            }
            fold_metrics.append(metrics)
            outputs[model_name] = {"mean_std": summarize_metrics(fold_metrics), "folds": fold_metrics}

    paired_tests = []
    for index, first in enumerate(model_names):
        for second in model_names[index + 1:]:
            first_scores = [fold["macro_f1"] for fold in outputs[first]["folds"]]
            second_scores = [fold["macro_f1"] for fold in outputs[second]["folds"]]
            try:
                result = wilcoxon(first_scores, second_scores, alternative="two-sided", method="auto")
                statistic, p_value, note = float(result.statistic), float(result.pvalue), None
            except ValueError as error:
                statistic, p_value, note = None, None, str(error)
            paired_tests.append({
                "metric": "fold_macro_f1", "model_a": first, "model_b": second,
                "wilcoxon_statistic": statistic, "p_value": p_value,
                "note": note or "Exploratory only: five fold scores are dependent because training sets overlap; not confirmatory inference.",
            })

    source_meta = dict(metadata)
    source_meta["target_feature_caveat"] = TARGET_FEATURE_CAVEATS[name]
    source_meta["class_counts_evaluated"] = {str(key): int(value) for key, value in class_counts.items()}
    source_meta["positive_prevalence_unweighted"] = float(class_counts.get(1, 0) / len(y))
    source_meta["split_method"] = split_method
    source_meta["record_id_grouped"] = bool(groups is not None)
    source_meta["resampling"] = "none; original training-fold class distribution retained"
    return {
        "metadata": source_meta,
        "n_rows_evaluated": int(len(y)), "n_features_before_encoding": int(X.shape[1]),
        "model_results": outputs, "paired_wilcoxon_fold_macro_f1": paired_tests,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path, help="Directory containing the inventoried raw source folders.")
    parser.add_argument("--output", type=Path, default=Path("reports/clinical_validation/exploratory_public_cohort_benchmark.json"))
    args = parser.parse_args()
    cohorts, _ = make_cohorts(args.data_root)
    result = {
        "created_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "purpose": "Exploratory source-specific public-dataset benchmark; not clinical validation or deployment evidence.",
        "protocol": {
            "random_seed": SEED, "folds": FOLDS,
            "threshold": 0.5, "threshold_selected_on_test": False,
            "all_preprocessing_fold_local": True, "resampling": "none",
            "metrics": "mean and sample standard deviation across folds; fold confusion matrices and summed counts; per-class metrics; paired Wilcoxon exploratory comparisons.",
        },
        "software_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__, "pandas": pd.__version__,
            "scikit_learn": importlib.metadata.version("scikit-learn"),
            "scipy": importlib.metadata.version("scipy"),
            "xgboost": importlib.metadata.version("xgboost") if xgboost_available() else None,
        },
        "cohorts": {name: evaluate_cohort(name, data) for name, data in cohorts.items()},
        "limitations": [
            "No external clinical validation or clinician adjudication was performed.",
            "Pooled source labels were avoided; each dataset has a separate target and result.",
            "Patient-level grouping is used only where a record ID is available; row-wise folds do not prove independence for datasets without IDs.",
            "Five-fold cross-validation on small public datasets estimates internal resampling performance, not transportability or clinical utility.",
            "No threshold optimization or probability calibration was performed; scores are not clinical risks.",
            "Wilcoxon fold-level p-values are exploratory because folds are dependent.",
            "Survey weights are not used for NHANES; weighted population estimates are not produced.",
            "The source files are local inputs and are not copied to the repository by this script.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    for name, cohort in result["cohorts"].items():
        print(f"{name}: n={cohort['n_rows_evaluated']} class_counts={cohort['metadata']['class_counts_evaluated']}")
        for model, details in cohort["model_results"].items():
            macro = details["mean_std"]["macro_f1"]
            sensitivity = details["mean_std"]["sensitivity"]
            print(f"  {model}: macro_f1={macro['mean']:.3f}±{macro['std']:.3f}, sensitivity={sensitivity['mean']:.3f}±{sensitivity['std']:.3f}")


if __name__ == "__main__":
    main()
