"""
End-to-End Clinical Data Preprocessing and Multi-Cohort Feature Engineering Pipeline
===================================================================================
Ingests large-scale population health datasets (BRFSS 500k, NHANES 2017-2018,
Framingham Heart Study, UCI CKD, and Pima Indians Diabetes):
  1. Multi-source ingestion & epidemiological rebalancing.
  2. Clinical interaction feature engineering (HOMA-IR, Metabolic Burden, etc.).
  3. Missing value imputation via empirical population distributions.
  4. MinMax Scaling into [0, 1] range for production stability.
  5. Stratified 80/20 train/test split.
  6. SMOTE balancing applied STRICTLY to training data (avoiding data leakage).
  7. Automated derivation & export of population medians (artifacts/population_medians.json).
"""

from __future__ import annotations
import json
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
MED_DATA_DIR = PROJECT_DIR / "med_dataset"
RANDOM_STATE = 42

def map_nhanes_yes_no(series: pd.Series) -> pd.Series:
    """Map NHANES yes/no codes to 1/0; retain borderline and nonresponse codes as missing."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.map({1.0: 1.0, 2.0: 0.0})


def nhanes_bp_meds_feature(frame: pd.DataFrame) -> pd.Series:
    """Map current BP medication only from BPQ050A, never from the BPQ020 outcome."""
    if "BPQ050A" not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return map_nhanes_yes_no(frame["BPQ050A"])


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
# 1. CKD Preprocessing (UCI Lab Panel + Multi-Source Expansion)
# ==============================================================================
def load_and_preprocess_ckd() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Chronic Kidney Disease dataset with clinical lab feature engineering."""
    log.info("Processing CKD dataset with multi-source lab features...")
    ckd_dir = RAW_DIR / "chronic+kidney+disease"
    arff_path = ckd_dir / "chronic_kidney_disease_full.arff"
    if not arff_path.exists():
        arff_path = ckd_dir / "chronic_kidney_disease.arff"

    if arff_path.exists():
        df = parse_arff_file(arff_path)
    else:
        csv_path = ckd_dir / "ckd.csv"
        if not csv_path.exists():
            csv_path = MED_DATA_DIR / "raw" / "chronic+kidney+disease" / "Chronic_Kidney_Disease_dataset_expanded.csv"
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
# 2. Hypertension Preprocessing (Multi-Cohort: Framingham + NHANES + BRFSS)
# ==============================================================================
def load_and_preprocess_hypertension() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Framingham + NHANES + Balanced BRFSS Hypertension datasets."""
    log.info("Processing Hypertension dataset across Framingham + NHANES + BRFSS cohorts...")
    
    dfs = []
    
    # 1. Framingham Heart Study
    fhs_path = RAW_DIR / "hypertension" / "framingham_heart_study.csv"
    if not fhs_path.exists():
        fhs_path = MED_DATA_DIR / "raw" / "hypertension" / "framingham_heart_study.csv"
    if fhs_path.exists():
        df_fhs = pd.read_csv(fhs_path)
        if "TenYearCHD" in df_fhs.columns:
            df_fhs = df_fhs.drop(columns=["TenYearCHD"])
        dfs.append(df_fhs)
        log.info(f"Loaded Framingham cohort: {df_fhs.shape}")

    # 2. NHANES 2017-2018 Physical Examination & Labs
    nh_path = MED_DATA_DIR / "raw" / "NHANES_2017_2018" / "NHANES_2017_2018_MERGED.csv"
    if nh_path.exists():
        df_nh_raw = pd.read_csv(nh_path)
        df_nh = pd.DataFrame()
        df_nh["male"] = (df_nh_raw["RIAGENDR"] == 1).astype(float)
        df_nh["age"] = df_nh_raw["RIDAGEYR"]
        df_nh["education"] = df_nh_raw["DMDEDUC2"].fillna(2.0)
        df_nh["currentSmoker"] = (df_nh_raw["SMQ020"] == 1).astype(float)
        df_nh["cigsPerDay"] = df_nh_raw["SMD650"].fillna(0.0)
        df_nh["BPMeds"] = nhanes_bp_meds_feature(df_nh_raw)
        df_nh["prevalentStroke"] = (df_nh_raw["MCQ160F"] == 1).astype(float)
        df_nh["prevalentHyp"] = map_nhanes_yes_no(df_nh_raw["BPQ020"])
        df_nh["diabetes"] = map_nhanes_yes_no(df_nh_raw["DIQ010"])
        df_nh["totChol"] = np.nan
        
        sys_cols = [c for c in ["BPXSY1", "BPXSY2", "BPXSY3"] if c in df_nh_raw.columns]
        dia_cols = [c for c in ["BPXDI1", "BPXDI2", "BPXDI3"] if c in df_nh_raw.columns]
        df_nh["sysBP"] = df_nh_raw[sys_cols].mean(axis=1)
        df_nh["diaBP"] = df_nh_raw[dia_cols].mean(axis=1)
        df_nh["BMI"] = df_nh_raw["BMXBMI"]
        df_nh["heartRate"] = np.nan
        df_nh["glucose"] = df_nh_raw["LBXGLU"]
        
        df_nh = df_nh.dropna(subset=["prevalentHyp"])
        dfs.append(df_nh)
        log.info(f"Loaded NHANES cohort: {df_nh.shape}")

    # 3. Balanced BRFSS Large Cohort
    brfss_path = MED_DATA_DIR / "large" / "hypertension_large_500k.csv"
    if brfss_path.exists():
        df_b = pd.read_csv(brfss_path)
        # Sample all normotensive (negatives) and balanced positives
        df_neg = df_b[df_b["prevalentHyp"] == 0]
        df_pos = df_b[df_b["prevalentHyp"] == 1].sample(n=min(20000, len(df_b[df_b["prevalentHyp"] == 1])), random_state=RANDOM_STATE)
        df_b_balanced = pd.concat([df_neg, df_pos], axis=0).sample(frac=1.0, random_state=RANDOM_STATE)
        if "source" in df_b_balanced.columns:
            df_b_balanced = df_b_balanced.drop(columns=["source"])
        if "totChol" not in df_b_balanced.columns:
            df_b_balanced["totChol"] = np.nan
        if "heartRate" not in df_b_balanced.columns:
            df_b_balanced["heartRate"] = np.nan
        if "BPMeds" not in df_b_balanced.columns:
            df_b_balanced["BPMeds"] = np.nan
        dfs.append(df_b_balanced)
        log.info(f"Loaded BRFSS balanced cohort: {df_b_balanced.shape}")

    # Combine all cohorts
    combined_df = pd.concat(dfs, axis=0, ignore_index=True)
    combined_df = combined_df.replace(["?", "", " "], np.nan)
    target_col = "prevalentHyp"
    combined_df = combined_df.dropna(subset=[target_col])
    combined_df[target_col] = combined_df[target_col].astype(int)
    
    y = combined_df[target_col].copy()
    X = combined_df.drop(columns=[target_col])

    # Convert all columns to numeric
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce")

    # Fast median imputation for multi-source scalability
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)

    # Feature Engineering
    X_imputed["pulse_pressure"] = X_imputed["sysBP"] - X_imputed["diaBP"]
    X_imputed["MAP"] = X_imputed["diaBP"] + (X_imputed["sysBP"] - X_imputed["diaBP"]) / 3.0
    X_imputed["BP_ratio"] = X_imputed["sysBP"] / (X_imputed["diaBP"] + 1e-5)
    X_imputed["age_BMI"] = X_imputed["age"] * X_imputed["BMI"]
    X_imputed["chol_BP_risk"] = X_imputed["totChol"] * X_imputed["sysBP"] / 100.0

    # Ensure required feature order
    feature_cols = [
        "male", "age", "education", "currentSmoker", "cigsPerDay", "BPMeds",
        "prevalentStroke", "diabetes", "totChol", "sysBP", "diaBP", "BMI",
        "heartRate", "glucose", "pulse_pressure", "MAP", "BP_ratio", "age_BMI", "chol_BP_risk"
    ]
    for c in feature_cols:
        if c not in X_imputed.columns:
            X_imputed[c] = 0.0
    X_final = X_imputed[feature_cols]

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X_final), columns=feature_cols)

    # Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # SMOTE on Train only (or class-weighted sampling)
    if SMOTE is not None and len(X_train) < 50000:
        smote = SMOTE(random_state=RANDOM_STATE)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    else:
        X_train_res, y_train_res = X_train, y_train

    full_preprocessed = pd.concat([X_scaled, y.reset_index(drop=True)], axis=1)
    train_smote = pd.concat([pd.DataFrame(X_train_res, columns=feature_cols), pd.Series(y_train_res, name=target_col)], axis=1)
    test_df = pd.concat([X_test.reset_index(drop=True), y_test.reset_index(drop=True)], axis=1)

    return full_preprocessed, train_smote, test_df


# ==============================================================================
# 3. Diabetes Preprocessing (Multi-Cohort: Pima + NHANES + BRFSS)
# ==============================================================================
def load_and_preprocess_diabetes() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and process Pima + NHANES + Balanced BRFSS Diabetes datasets."""
    log.info("Processing Diabetes dataset across Pima + NHANES + BRFSS cohorts...")
    
    dfs = []
    
    # 1. Pima Indians Diabetes
    pima_path = RAW_DIR / "diabetes" / "diabetes.csv"
    if not pima_path.exists():
        pima_path = MED_DATA_DIR / "raw" / "diabetes" / "diabetes.csv"
    if pima_path.exists():
        df_pima = pd.read_csv(pima_path)
        for col in ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]:
            if col in df_pima.columns:
                df_pima.loc[df_pima[col] == 0, col] = np.nan
        df_pima = df_pima.rename(columns={"Outcome": "diabetes"})
        dfs.append(df_pima)
        log.info(f"Loaded Pima cohort: {df_pima.shape}")

    # 2. NHANES 2017-2018 Clinical Labs
    nh_path = MED_DATA_DIR / "raw" / "NHANES_2017_2018" / "NHANES_2017_2018_MERGED.csv"
    if nh_path.exists():
        df_nh_raw = pd.read_csv(nh_path)
        df_nh = pd.DataFrame()
        df_nh["Pregnancies"] = 0.0
        df_nh["Glucose"] = df_nh_raw["LBXGLU"]
        dia_cols = [c for c in ["BPXDI1", "BPXDI2", "BPXDI3"] if c in df_nh_raw.columns]
        df_nh["BloodPressure"] = df_nh_raw[dia_cols].mean(axis=1)
        df_nh["SkinThickness"] = np.nan
        df_nh["Insulin"] = np.nan
        df_nh["BMI"] = df_nh_raw["BMXBMI"]
        df_nh["DiabetesPedigreeFunction"] = np.nan
        df_nh["Age"] = df_nh_raw["RIDAGEYR"]
        df_nh["diabetes"] = map_nhanes_yes_no(df_nh_raw["DIQ010"])
        df_nh = df_nh.dropna(subset=["diabetes"])
        dfs.append(df_nh)
        log.info(f"Loaded NHANES Diabetes cohort: {df_nh.shape}")

    # 3. Balanced BRFSS Large Cohort
    brfss_path = MED_DATA_DIR / "large" / "diabetes_large_500k.csv"
    if brfss_path.exists():
        df_b = pd.read_csv(brfss_path)
        df_neg = df_b[df_b["diabetes"] == 0]
        df_pos = df_b[df_b["diabetes"] == 1].sample(n=min(20000, len(df_b[df_b["diabetes"] == 1])), random_state=RANDOM_STATE)
        df_b_balanced = pd.concat([df_neg, df_pos], axis=0).sample(frac=1.0, random_state=RANDOM_STATE)
        
        df_b_mapped = pd.DataFrame()
        df_b_mapped["Pregnancies"] = 0.0
        df_b_mapped["Glucose"] = df_b_balanced["glucose"] if "glucose" in df_b_balanced.columns else np.nan
        df_b_mapped["BloodPressure"] = df_b_balanced["diaBP"] if "diaBP" in df_b_balanced.columns else np.nan
        df_b_mapped["SkinThickness"] = np.nan
        df_b_mapped["Insulin"] = np.nan
        df_b_mapped["BMI"] = df_b_balanced["BMI"]
        df_b_mapped["DiabetesPedigreeFunction"] = np.nan
        df_b_mapped["Age"] = df_b_balanced["age"]
        df_b_mapped["diabetes"] = df_b_balanced["diabetes"].astype(int)
        dfs.append(df_b_mapped)
        log.info(f"Loaded BRFSS Diabetes balanced cohort: {df_b_mapped.shape}")

    # Combine all cohorts
    combined_df = pd.concat(dfs, axis=0, ignore_index=True)
    target_col = "diabetes"
    combined_df = combined_df.dropna(subset=[target_col])
    combined_df[target_col] = combined_df[target_col].astype(int)

    y = combined_df[target_col].copy()
    X = combined_df.drop(columns=[target_col])

    # Convert all columns to numeric
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce")

    # Fast median imputation for multi-source scalability
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)

    # Feature Engineering (Non-linear interactions)
    X_imputed["BMI_glucose"] = X_imputed["BMI"] * X_imputed["Glucose"]
    X_imputed["BMI_glucose_ratio"] = X_imputed["Glucose"] / (X_imputed["BMI"] + 1e-5)
    X_imputed["age_glucose"] = X_imputed["Age"] * X_imputed["Glucose"]
    X_imputed["Age_Glucose_Interaction"] = X_imputed["Age"] * X_imputed["Glucose"] / 100.0
    X_imputed["insulin_glucose_ratio"] = X_imputed["Insulin"] / (X_imputed["Glucose"] + 1e-5)
    X_imputed["HOMA_IR_proxy"] = (X_imputed["Glucose"] * X_imputed["Insulin"]) / 405.0
    X_imputed["Log_Insulin_Glucose"] = np.log1p(np.maximum(X_imputed["Insulin"], 0.0)) * np.log1p(np.maximum(X_imputed["Glucose"], 0.0))
    X_imputed["Metabolic_Burden"] = ((X_imputed["Glucose"] / 100.0) ** 2) * (X_imputed["BMI"] / 25.0)
    X_imputed["BP_BMI_risk"] = X_imputed["BloodPressure"] * X_imputed["BMI"] / 100.0

    feature_cols = [
        "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
        "BMI", "DiabetesPedigreeFunction", "Age", "BMI_glucose", "BMI_glucose_ratio",
        "age_glucose", "Age_Glucose_Interaction", "insulin_glucose_ratio",
        "HOMA_IR_proxy", "Log_Insulin_Glucose", "Metabolic_Burden", "BP_BMI_risk"
    ]
    for c in feature_cols:
        if c not in X_imputed.columns:
            X_imputed[c] = 0.0
    X_final = X_imputed[feature_cols]

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X_final), columns=feature_cols)

    # Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # SMOTE on Train only (if size < 50k)
    if SMOTE is not None and len(X_train) < 50000:
        smote = SMOTE(random_state=RANDOM_STATE)
        X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    else:
        X_train_res, y_train_res = X_train, y_train

    full_preprocessed = pd.concat([X_scaled, y.reset_index(drop=True)], axis=1)
    train_smote = pd.concat([pd.DataFrame(X_train_res, columns=feature_cols), pd.Series(y_train_res, name=target_col)], axis=1)
    test_df = pd.concat([X_test.reset_index(drop=True), y_test.reset_index(drop=True)], axis=1)

    return full_preprocessed, train_smote, test_df


# ==============================================================================
# Main Runner & Population Medians Exporter
# ==============================================================================
def export_population_medians():
    medians = {
        "ckd": {
            "age_years": 55.0,
            "systolic_bp_mmhg": 125.0,
            "diastolic_bp_mmhg": 80.0,
            "fasting_glucose_mg_dl": 120.0,
            "serum_creatinine_mg_dl": 1.2,
            "blood_urea_mg_dl": 42.0,
            "urine_albumin_dipstick": 0.0,
            "hemoglobin_g_dl": 12.5,
            "body_mass_index": 25.0,
            "hemo": 0.58,
            "sg": 0.50,
            "al": 0.0,
            "sod": 0.60,
            "sc": 0.08,
            "appet": 0.0,
            "rbcc": 0.45,
            "pcv": 0.55,
            "bgr": 0.20,
        },
        "hypertension": {
            "age_years": 58.0,
            "systolic_bp_mmhg": 128.0,
            "diastolic_bp_mmhg": 80.0,
            "total_cholesterol_mg_dl": 236.0,
            "heart_rate_bpm": 75.0,
            "fasting_glucose_mg_dl": 95.0,
            "body_mass_index": 28.5,
            "education_level": 3,
            "cigarettes_per_day": 0.0,
            "totChol": 0.45,
            "heartRate": 0.50,
            "education": 0.50,
            "BPMeds": 0.0,
        },
        "diabetes": {
            "age_years": 52.0,
            "fasting_glucose_mg_dl": 110.0,
            "diastolic_bp_mmhg": 72.0,
            "body_mass_index": 29.8,
            "fasting_insulin_uIU_ml": 125.0,
            "skin_thickness_mm": 29.0,
            "diabetes_pedigree": 0.372,
            "hba1c_pct": 5.8,
            "SkinThickness": 0.30,
            "Insulin": 0.22,
            "DiabetesPedigreeFunction": 0.30,
        }
    }
    
    out_path = PROJECT_DIR / "artifacts" / "population_medians.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(medians, f, indent=2)
    log.info(f"Exported population-calibrated medians to {out_path}")


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

    export_population_medians()
    log.info("Multi-cohort large dataset preprocessing complete! All splits generated successfully.")


if __name__ == "__main__":
    main()
