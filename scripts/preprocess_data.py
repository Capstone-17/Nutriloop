"""
End-to-End Clinical Data Preprocessing and Feature Engineering Pipeline
========================================================================
Processes raw Chronic Kidney Disease, Hypertension, and Diabetes datasets:
  1. Robust ARFF/CSV parsing handling whitespace tokens & missing delimiters.
  2. Biologically implausible zero-value replacement (Pima diabetes).
  3. Clinical interaction feature engineering (BP_ratio, MAP, BMI*Glucose, etc.).
  4. KNN Imputation (k=5) for numeric & Most-Frequent for categorical features.
  5. MinMax Scaling into [0, 1] range.
  6. Stratified 80/20 train/test split.
  7. SMOTE balancing applied STRICTLY to training data (avoiding data leakage).
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

try:
    from imblearn.over_sampling import SMOTE
except (ImportError, ModuleNotFoundError):
    SMOTE = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("preprocess")

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "datasets" / "raw"
OUT_DIR = PROJECT_DIR / "datasets" / "preprocessed"
RANDOM_STATE = 42


def parse_arff_file(path: Path) -> pd.DataFrame:
    """Robust custom parser for ARFF files handling whitespace tokens and unquoted delimiters."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    attrs = []
    data_lines = []
    is_data = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        if line.lower().startswith("@attribute"):
            parts = line.split()
            attr_name = parts[1].strip("'\" \t")
            attrs.append(attr_name)
        elif line.lower().startswith("@data"):
            is_data = True
        elif is_data:
            row = [x.strip("'\" \t") for x in line.split(",")]
            if len(row) == len(attrs):
                data_lines.append(row)

    return pd.DataFrame(data_lines, columns=attrs)


# ==============================================================================
# 1. CKD Preprocessing
# ==============================================================================
def load_and_preprocess_ckd() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Chronic Kidney Disease dataset with clinical feature engineering."""
    log.info("Processing CKD dataset...")
    ckd_dir = RAW_DIR / "chronic+kidney+disease"
    arff_path = ckd_dir / "chronic_kidney_disease_full.arff"
    if not arff_path.exists():
        arff_path = ckd_dir / "chronic_kidney_disease.arff"

    if arff_path.exists():
        df = parse_arff_file(arff_path)
    else:
        # Fallback to local CSV or ucimlrepo
        csv_path = ckd_dir / "ckd.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
        else:
            from ucimlrepo import fetch_ucirepo
            ckd = fetch_ucirepo(id=336)
            df = ckd.data.features.copy()
            df["class"] = ckd.data.targets.iloc[:, 0]

    # Standardize string tokens
    df = df.replace(["?", "\t?", " ?", "\t?\t", "", " "], np.nan)
    target_col = "class" if "class" in df.columns else df.columns[-1]

    # Clean target
    df[target_col] = df[target_col].astype(str).str.strip().str.lower()
    df[target_col] = df[target_col].map({"ckd": 1, "notckd": 0, "ckd\t": 1, "1": 1, "0": 0})
    df = df.dropna(subset=[target_col])
    df[target_col] = df[target_col].astype(int)

    # Separate numeric and categorical
    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    # Convert numeric fields
    numeric_candidates = ["age", "bp", "bgr", "bu", "sc", "sod", "pot", "hemo", "pcv", "wbcc", "rbcc", "sg", "al", "su"]
    for col in numeric_candidates:
        if col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    cat_cols = [c for c in X.columns if c not in num_cols]

    # Impute numeric
    if num_cols:
        X[num_cols] = KNNImputer(n_neighbors=5).fit_transform(X[num_cols])
    # Impute and encode categorical
    for c in cat_cols:
        X[c] = SimpleImputer(strategy="most_frequent").fit_transform(X[[c]])[:, 0]
        X[c] = LabelEncoder().fit_transform(X[c].astype(str))

    # Clinical Feature Engineering
    if "bp" in X.columns:
        X["BP_ratio"] = X["bp"] / 80.0
        X["pulse_pressure"] = np.clip(X["bp"] - 80.0, 0, 100)
    if "bgr" in X.columns and "dm" in X.columns:
        X["glucose_diabetes"] = X["bgr"] * X["dm"]
    if "sc" in X.columns and "bu" in X.columns:
        X["creatinine_urea_ratio"] = X["sc"] / (X["bu"] + 1e-5)

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

    # Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # SMOTE on Train only
    if SMOTE is not None:
        smote = SMOTE(random_state=RANDOM_STATE)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    else:
        log.warning("SMOTE not available, using unresampled training data.")
        X_train_res, y_train_res = X_train, y_train

    full_preprocessed = pd.concat([X_scaled, y.reset_index(drop=True)], axis=1)
    train_smote = pd.concat([pd.DataFrame(X_train_res, columns=X.columns), pd.Series(y_train_res, name=target_col)], axis=1)
    test_df = pd.concat([X_test.reset_index(drop=True), y_test.reset_index(drop=True)], axis=1)

    return full_preprocessed, train_smote, test_df


# ==============================================================================
# 2. Hypertension Preprocessing
# ==============================================================================
def load_and_preprocess_hypertension() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Framingham Hypertension dataset with feature engineering."""
    log.info("Processing Hypertension dataset...")
    htn_path = RAW_DIR / "hypertension" / "framingham_heart_study.csv"
    if not htn_path.exists():
        htn_path = RAW_DIR / "hypertension" / "framingham.csv"
    if not htn_path.exists():
        raise FileNotFoundError(f"Missing Hypertension dataset at {RAW_DIR / 'hypertension'}")

    df = pd.read_csv(htn_path)
    df = df.replace(["?", "", " "], np.nan)
    target_col = "prevalentHyp" if "prevalentHyp" in df.columns else ("TenYearCHD" if "TenYearCHD" in df.columns else df.columns[-1])

    # Target
    df = df.dropna(subset=[target_col])
    df[target_col] = df[target_col].astype(int)
    y = df[target_col].copy()
    X = df.drop(columns=[target_col])
    if "TenYearCHD" in X.columns and target_col == "prevalentHyp":
        X = X.drop(columns=["TenYearCHD"])

    # Convert all columns to numeric
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce")

    # KNN Imputation
    num_cols = list(X.columns)
    X[num_cols] = KNNImputer(n_neighbors=5).fit_transform(X[num_cols])

    # Feature Engineering
    if "sysBP" in X.columns and "diaBP" in X.columns:
        X["pulse_pressure"] = X["sysBP"] - X["diaBP"]
        X["MAP"] = X["diaBP"] + (X["sysBP"] - X["diaBP"]) / 3.0
        X["BP_ratio"] = X["sysBP"] / (X["diaBP"] + 1e-5)
    if "age" in X.columns and "BMI" in X.columns:
        X["age_BMI"] = X["age"] * X["BMI"]
    if "totChol" in X.columns and "sysBP" in X.columns:
        X["chol_BP_risk"] = X["totChol"] * X["sysBP"]

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

    # Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # SMOTE on Train only
    if SMOTE is not None:
        smote = SMOTE(random_state=RANDOM_STATE)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    else:
        log.warning("SMOTE not available, using unresampled training data.")
        X_train_res, y_train_res = X_train, y_train

    full_preprocessed = pd.concat([X_scaled, y.reset_index(drop=True)], axis=1)
    train_smote = pd.concat([pd.DataFrame(X_train_res, columns=X.columns), pd.Series(y_train_res, name=target_col)], axis=1)
    test_df = pd.concat([X_test.reset_index(drop=True), y_test.reset_index(drop=True)], axis=1)

    return full_preprocessed, train_smote, test_df


# ==============================================================================
# 3. Diabetes Preprocessing
# ==============================================================================
def load_and_preprocess_diabetes() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Pima Diabetes dataset with biologically valid missing treatment."""
    log.info("Processing Diabetes dataset...")
    diab_path = RAW_DIR / "diabetes" / "diabetes.csv"
    if not diab_path.exists():
        raise FileNotFoundError(f"Missing {diab_path}")

    df = pd.read_csv(diab_path)
    target_col = "Outcome" if "Outcome" in df.columns else df.columns[-1]
    df = df.dropna(subset=[target_col])
    df[target_col] = df[target_col].astype(int)

    # Replace biologically impossible zeros with NaN
    zero_missing_cols = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]
    for col in zero_missing_cols:
        if col in df.columns:
            df.loc[df[col] == 0, col] = np.nan

    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    # Convert all columns to numeric
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce")

    # KNN Imputer
    num_cols = list(X.columns)
    X[num_cols] = KNNImputer(n_neighbors=5).fit_transform(X[num_cols])

    # Feature Engineering
    if "BMI" in X.columns and "Glucose" in X.columns:
        X["BMI_glucose"] = X["BMI"] * X["Glucose"]
        X["BMI_glucose_ratio"] = X["Glucose"] / (X["BMI"] + 1e-5)
    if "Age" in X.columns and "Glucose" in X.columns:
        X["age_glucose"] = X["Age"] * X["Glucose"]
    if "Insulin" in X.columns and "Glucose" in X.columns:
        X["insulin_glucose_ratio"] = X["Insulin"] / (X["Glucose"] + 1e-5)

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

    # Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # SMOTE on Train only
    if SMOTE is not None:
        smote = SMOTE(random_state=RANDOM_STATE)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    else:
        log.warning("SMOTE not available, using unresampled training data.")
        X_train_res, y_train_res = X_train, y_train

    full_preprocessed = pd.concat([X_scaled, y.reset_index(drop=True)], axis=1)
    train_smote = pd.concat([pd.DataFrame(X_train_res, columns=X.columns), pd.Series(y_train_res, name=target_col)], axis=1)
    test_df = pd.concat([X_test.reset_index(drop=True), y_test.reset_index(drop=True)], axis=1)

    return full_preprocessed, train_smote, test_df


# ==============================================================================
# Main Runner
# ==============================================================================
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datasets = {
        "ckd": load_and_preprocess_ckd(),
        "hypertension": load_and_preprocess_hypertension(),
        "diabetes": load_and_preprocess_diabetes(),
    }

    for name, (full, train_smote, test) in datasets.items():
        full_path = OUT_DIR / f"{name}_preprocessed.csv"
        train_path = OUT_DIR / f"{name}_train_smote.csv"
        test_path = OUT_DIR / f"{name}_test.csv"

        full.to_csv(full_path, index=False)
        train_smote.to_csv(train_path, index=False)
        test.to_csv(test_path, index=False)

        log.info(
            f"Saved {name.upper()}: full={full.shape}, train_smote={train_smote.shape}, test={test.shape}"
        )

    log.info("Preprocessing complete! All splits generated successfully.")


if __name__ == "__main__":
    main()
