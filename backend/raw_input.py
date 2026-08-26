"""
Conversational Raw Input Questionnaire and Feature Transformation Engine
========================================================================
Translates patient-facing questionnaire answers and clinical biomarkers into
fully aligned, normalized feature vectors matching the trained ML models.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Set
import numpy as np

from pydantic import ValidationError

from backend.model_registry import registry
from backend.schemas import CKDRawInput, DiabetesRawInput, HypertensionRawInput

MEDIANS_FILE = Path(__file__).resolve().parent.parent / "artifacts" / "population_medians.json"
POPULATION_MEDIANS: Dict[str, Dict[str, Any]] = {}
if MEDIANS_FILE.exists():
    try:
        with open(MEDIANS_FILE, "r", encoding="utf-8") as f:
            POPULATION_MEDIANS = json.load(f)
    except Exception:
        POPULATION_MEDIANS = {}


@dataclass
class RawMappingResult:
    disease: str
    raw_inputs: Dict[str, Any]
    transformed_features: Dict[str, float]
    validation_warnings: List[str]


FIELD_METADATA: Dict[str, List[Dict[str, Any]]] = {
    "ckd": [
        {"name": "age_years", "label": "Age (years)", "required": True},
        {"name": "sex", "label": "Sex (male/female)", "required": True},
        {"name": "body_mass_index", "label": "BMI (kg/m²)", "required": True},
        {"name": "diagnosed_diabetes", "label": "Diagnosed diabetes (true/false)", "required": False},
        {"name": "diagnosed_hypertension", "label": "Diagnosed hypertension (true/false)", "required": False},
        {"name": "systolic_bp_mmhg", "label": "Systolic BP mmHg", "required": False},
        {"name": "diastolic_bp_mmhg", "label": "Diastolic BP mmHg", "required": False},
        {"name": "fasting_glucose_mg_dl", "label": "Fasting glucose mg/dL", "required": False},
        {"name": "serum_creatinine_mg_dl", "label": "Serum creatinine mg/dL", "required": False},
        {"name": "blood_urea_mg_dl", "label": "Blood urea mg/dL", "required": False},
        {"name": "hemoglobin_g_dl", "label": "Hemoglobin g/dL", "required": False},
        {"name": "urine_albumin_dipstick", "label": "Urine albumin (0-4)", "required": False},
    ],
    "hypertension": [
        {"name": "age_years", "label": "Age (years)", "required": True},
        {"name": "sex", "label": "Sex (male/female)", "required": True},
        {"name": "education_level", "label": "Education level (1-4)", "required": False},
        {"name": "current_smoker", "label": "Current smoker (true/false)", "required": False},
        {"name": "cigarettes_per_day", "label": "Cigarettes per day", "required": False},
        {"name": "prior_stroke", "label": "Prior stroke (true/false)", "required": False},
        {"name": "body_mass_index", "label": "BMI (kg/m²)", "required": True},
        {"name": "diagnosed_diabetes", "label": "Diagnosed diabetes (true/false)", "required": False},
        {"name": "systolic_bp_mmhg", "label": "Systolic BP mmHg", "required": False},
        {"name": "diastolic_bp_mmhg", "label": "Diastolic BP mmHg", "required": False},
        {"name": "fasting_glucose_mg_dl", "label": "Fasting glucose mg/dL", "required": False},
        {"name": "total_cholesterol_mg_dl", "label": "Total cholesterol mg/dL", "required": False},
        {"name": "heart_rate_bpm", "label": "Heart rate BPM", "required": False},
        {"name": "blood_pressure_meds", "label": "BP medication (true/false)", "required": False},
    ],
    "diabetes": [
        {"name": "age_years", "label": "Age (years)", "required": True},
        {"name": "sex", "label": "Sex (male/female)", "required": True},
        {"name": "body_mass_index", "label": "BMI (kg/m²)", "required": True},
        {"name": "current_smoker", "label": "Current smoker (true/false)", "required": False},
        {"name": "diagnosed_hypertension", "label": "Diagnosed hypertension (true/false)", "required": False},
        {"name": "systolic_bp_mmhg", "label": "Systolic BP mmHg", "required": False},
        {"name": "diastolic_bp_mmhg", "label": "Diastolic BP mmHg", "required": False},
        {"name": "fasting_glucose_mg_dl", "label": "Fasting glucose mg/dL", "required": False},
        {"name": "fasting_insulin_uIU_ml", "label": "Fasting insulin uIU/mL", "required": False},
        {"name": "hba1c_pct", "label": "HbA1c (%)", "required": False},
        {"name": "skin_thickness_mm", "label": "Skin thickness mm", "required": False},
        {"name": "diabetes_pedigree", "label": "Diabetes pedigree function", "required": False},
    ],
}


RAW_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "ckd": {
        "age_years": 56,
        "sex": "female",
        "body_mass_index": 27.4,
        "diagnosed_diabetes": True,
        "diagnosed_hypertension": True,
        "systolic_bp_mmhg": 142,
        "diastolic_bp_mmhg": 88,
        "fasting_glucose_mg_dl": 132,
        "serum_creatinine_mg_dl": 1.4,
        "blood_urea_mg_dl": 46.0,
    },
    "hypertension": {
        "age_years": 63,
        "sex": "male",
        "education_level": 2,
        "current_smoker": True,
        "cigarettes_per_day": 10,
        "prior_stroke": False,
        "body_mass_index": 31.2,
        "diagnosed_diabetes": True,
        "systolic_bp_mmhg": 154,
        "diastolic_bp_mmhg": 96,
        "fasting_glucose_mg_dl": 140,
        "total_cholesterol_mg_dl": 245,
        "heart_rate_bpm": 78,
    },
    "diabetes": {
        "age_years": 58,
        "sex": "male",
        "body_mass_index": 30.1,
        "current_smoker": False,
        "diagnosed_hypertension": True,
        "systolic_bp_mmhg": 146,
        "diastolic_bp_mmhg": 90,
        "fasting_glucose_mg_dl": 168,
        "fasting_insulin_uIU_ml": 140,
        "hba1c_pct": 7.2,
    },
}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _minmax(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    return _clip01((float(value) - min_value) / (max_value - min_value))


def _binary(value: bool) -> float:
    return 1.0 if bool(value) else 0.0


def _sex_to_male(value: str) -> float:
    return 1.0 if str(value).strip().lower() == "male" else 0.0


def get_raw_template(disease: str) -> Dict[str, Any]:
    if disease not in RAW_EXAMPLES:
        raise ValueError(f"Unsupported disease '{disease}'.")
    return {"disease": disease, "raw_inputs": RAW_EXAMPLES[disease]}


def get_raw_field_metadata(disease: str) -> List[Dict[str, Any]]:
    if disease not in FIELD_METADATA:
        raise ValueError(f"Unsupported disease '{disease}'.")
    return FIELD_METADATA[disease]


def map_raw_payload(disease: str, raw_inputs: Dict[str, Any]) -> RawMappingResult:
    unknown_fields = _find_unknown_raw_fields(disease, raw_inputs)
    if disease == "ckd":
        result = _map_ckd(raw_inputs)
    elif disease == "hypertension":
        result = _map_hypertension(raw_inputs)
    elif disease == "diabetes":
        result = _map_diabetes(raw_inputs)
    else:
        raise ValueError(f"Unsupported disease '{disease}'.")

    if unknown_fields:
        result.validation_warnings.append(
            f"Ignored unrecognized fields for '{disease}': {', '.join(unknown_fields)}"
        )

    result.transformed_features = align_transformed_features(disease, result.transformed_features, result.validation_warnings)
    return result


def _find_unknown_raw_fields(disease: str, raw_inputs: Dict[str, Any]) -> List[str]:
    valid = {f["name"] for f in FIELD_METADATA.get(disease, [])}
    return sorted([k for k in raw_inputs.keys() if k not in valid])


def align_transformed_features(
    disease: str,
    features: Dict[str, float],
    warnings: List[str],
) -> Dict[str, float]:
    expected = registry.get_feature_names(disease)
    aligned: Dict[str, float] = {}
    missing: List[str] = []
    meds = POPULATION_MEDIANS.get(disease, {})

    for feature_name in expected:
        if feature_name in features:
            aligned[feature_name] = float(features[feature_name])
        elif feature_name in meds:
            aligned[feature_name] = float(meds[feature_name])
        else:
            missing.append(feature_name)
            aligned[feature_name] = 0.0

    if missing:
        warnings.append(
            "Mapper defaulted missing features to baseline: " + ", ".join(missing)
        )
    return aligned


def _map_ckd(raw_inputs: Dict[str, Any]) -> RawMappingResult:
    try:
        payload = CKDRawInput(**raw_inputs)
    except ValidationError as ex:
        raise ValueError(ex.json()) from ex

    meds = POPULATION_MEDIANS.get("ckd", {})
    sys_bp = payload.systolic_bp_mmhg or meds.get("systolic_bp_mmhg", 120.0)
    dia_bp = payload.diastolic_bp_mmhg or meds.get("diastolic_bp_mmhg", 80.0)
    glucose = payload.fasting_glucose_mg_dl or meds.get("fasting_glucose_mg_dl", 110.0)
    sc = payload.serum_creatinine_mg_dl or meds.get("serum_creatinine_mg_dl", 1.2)
    bu = payload.blood_urea_mg_dl or meds.get("blood_urea_mg_dl", 42.0)
    hemo = payload.hemoglobin_g_dl or meds.get("hemoglobin_g_dl", 12.5)
    al = float(payload.urine_albumin_dipstick) if payload.urine_albumin_dipstick is not None else float(meds.get("al", 0.0))

    features = {
        "age": _minmax(payload.age_years, 10, 90),
        "bp": _minmax(sys_bp, 50, 180),
        "sg": meds.get("sg", 0.50),
        "al": _minmax(al, 0, 4),
        "su": 0.0,
        "rbc": 0.0,
        "pc": 0.0,
        "pcc": 0.0,
        "ba": 0.0,
        "bgr": _minmax(glucose, 50, 490),
        "bu": _minmax(bu, 1, 390),
        "sc": _minmax(sc, 0.4, 15.0),
        "sod": meds.get("sod", 0.60),
        "pot": 0.08,
        "hemo": _minmax(hemo, 3.1, 17.8),
        "pcv": meds.get("pcv", 0.55),
        "wbcc": 0.25,
        "rbcc": meds.get("rbcc", 0.45),
        "htn": _binary(payload.diagnosed_hypertension),
        "dm": _binary(payload.diagnosed_diabetes),
        "cad": 0.0,
        "appet": 0.0,
        "pe": 0.0,
        "ane": 0.0,
        "BP_ratio": sys_bp / 80.0,
        "pulse_pressure": _minmax(sys_bp - dia_bp, 0, 100),
        "glucose_diabetes": glucose * _binary(payload.diagnosed_diabetes),
        "creatinine_urea_ratio": sc / (bu + 1e-5),
    }
    return RawMappingResult("ckd", payload.model_dump(), features, [])


def _map_hypertension(raw_inputs: Dict[str, Any]) -> RawMappingResult:
    try:
        payload = HypertensionRawInput(**raw_inputs)
    except ValidationError as ex:
        raise ValueError(ex.json()) from ex

    meds = POPULATION_MEDIANS.get("hypertension", {})
    sys_bp = payload.systolic_bp_mmhg or meds.get("systolic_bp_mmhg", 128.0)
    dia_bp = payload.diastolic_bp_mmhg or meds.get("dia_bp_mmhg", 82.0)
    glucose = payload.fasting_glucose_mg_dl or meds.get("fasting_glucose_mg_dl", 80.0)
    bmi = payload.body_mass_index or meds.get("body_mass_index", 25.6)
    cigarettes = payload.cigarettes_per_day if payload.current_smoker else 0.0
    tot_chol = payload.total_cholesterol_mg_dl or meds.get("total_cholesterol_mg_dl", 236.0)
    heart_rate = payload.heart_rate_bpm or meds.get("heart_rate_bpm", 75.0)
    bp_meds = _binary(payload.blood_pressure_meds)

    features = {
        "male": _sex_to_male(payload.sex),
        "age": _minmax(payload.age_years, 18, 80),
        "education": _minmax(payload.education_level or 2, 1, 4),
        "currentSmoker": _binary(payload.current_smoker),
        "cigsPerDay": _minmax(cigarettes, 0, 70),
        "BPMeds": bp_meds,
        "prevalentStroke": _binary(payload.prior_stroke),
        "diabetes": _binary(payload.diagnosed_diabetes),
        "totChol": _minmax(tot_chol, 100, 600),
        "sysBP": _minmax(sys_bp, 80, 295),
        "diaBP": _minmax(dia_bp, 40, 145),
        "BMI": _minmax(bmi, 15, 60),
        "heartRate": _minmax(heart_rate, 40, 150),
        "glucose": _minmax(glucose, 40, 395),
        "pulse_pressure": sys_bp - dia_bp,
        "MAP": dia_bp + (sys_bp - dia_bp) / 3.0,
        "BP_ratio": sys_bp / (dia_bp + 1e-5),
        "age_BMI": payload.age_years * bmi,
        "chol_BP_risk": tot_chol * sys_bp / 100.0,
    }
    return RawMappingResult("hypertension", payload.model_dump(), features, [])


def _map_diabetes(raw_inputs: Dict[str, Any]) -> RawMappingResult:
    try:
        payload = DiabetesRawInput(**raw_inputs)
    except ValidationError as ex:
        raise ValueError(ex.json()) from ex

    meds = POPULATION_MEDIANS.get("diabetes", {})
    glucose = payload.fasting_glucose_mg_dl or meds.get("fasting_glucose_mg_dl", 117.0)
    dia_bp = payload.diastolic_bp_mmhg or meds.get("diastolic_bp_mmhg", 72.0)
    bmi = payload.body_mass_index or meds.get("body_mass_index", 32.3)
    insulin = payload.fasting_insulin_uIU_ml or meds.get("fasting_insulin_uIU_ml", 125.0)
    skin = payload.skin_thickness_mm or meds.get("skin_thickness_mm", 29.0)
    pedigree = payload.diabetes_pedigree or meds.get("diabetes_pedigree", 0.372)

    features = {
        "Pregnancies": 0.0,
        "Glucose": _minmax(glucose, 44, 199),
        "BloodPressure": _minmax(dia_bp, 24, 122),
        "SkinThickness": _minmax(skin, 7, 99),
        "Insulin": _minmax(insulin, 14, 846),
        "BMI": _minmax(bmi, 18, 67),
        "DiabetesPedigreeFunction": _minmax(pedigree, 0.07, 2.42),
        "Age": _minmax(payload.age_years, 21, 81),
        "BMI_glucose": bmi * glucose,
        "BMI_glucose_ratio": glucose / (bmi + 1e-5),
        "age_glucose": payload.age_years * glucose,
        "Age_Glucose_Interaction": payload.age_years * glucose / 100.0,
        "insulin_glucose_ratio": insulin / (glucose + 1e-5),
        "HOMA_IR_proxy": (glucose * insulin) / 405.0,
        "Log_Insulin_Glucose": np.log1p(max(insulin, 0.0)) * np.log1p(max(glucose, 0.0)),
        "Metabolic_Burden": ((glucose / 100.0) ** 2) * (bmi / 25.0),
        "BP_BMI_risk": dia_bp * bmi / 100.0,
    }
    return RawMappingResult("diabetes", payload.model_dump(), features, [])
