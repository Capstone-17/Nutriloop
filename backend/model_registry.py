import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd


ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"


class ModelRegistry:
    def __init__(self) -> None:
        self.models: Dict[str, object] = {}
        self.features: Dict[str, List[str]] = {}
        self.risk_profiles: Dict[str, Dict] = {}
        self._risk_profiles_loaded = False

    def load(self) -> None:
        self.load_feature_metadata()
        self.load_risk_profiles()

    def load_feature_metadata(self) -> None:
        for disease in ["ckd", "hypertension", "diabetes"]:
            if disease in self.features:
                continue
            features_path = ARTIFACT_DIR / f"{disease}_features.json"
            if features_path.exists():
                self.features[disease] = json.loads(features_path.read_text(encoding="utf-8"))

    def load_risk_profiles(self) -> None:
        if self._risk_profiles_loaded:
            return
        risk_profile_path = ARTIFACT_DIR / "risk_thresholds_and_factors.json"
        if risk_profile_path.exists():
            payload = json.loads(risk_profile_path.read_text(encoding="utf-8"))
            self.risk_profiles = payload.get("diseases", payload)
        self._risk_profiles_loaded = True

    def ensure_model_loaded(self, disease: str) -> None:
        if disease in self.models:
            return

        model_path = ARTIFACT_DIR / f"{disease}_model.joblib"
        if not model_path.exists():
            raise ValueError(f"Model artifact not found for disease '{disease}'.")

        model = joblib.load(model_path)
        if not hasattr(model, "multi_class"):
            try:
                setattr(model, "multi_class", "auto")
            except Exception:
                pass
        self.models[disease] = model

    def is_ready(self, disease: str) -> bool:
        self.load_feature_metadata()
        return disease in self.features

    def get_feature_names(self, disease: str) -> List[str]:
        self.load_feature_metadata()
        return self.features.get(disease, [])

    def get_risk_profile(self, disease: str) -> Dict:
        self.load_risk_profiles()
        return self.risk_profiles.get(disease, {})


    def predict(self, disease: str, feature_payload: Dict) -> Tuple[int, float, str]:
        if not self.is_ready(disease):
            raise ValueError(f"Model for disease '{disease}' is not loaded.")
        self.ensure_model_loaded(disease)

        feature_order = self.features[disease]
        row = [feature_payload.get(k, 0.0) for k in feature_order]
        X = np.array([row], dtype=float)

        model = self.models[disease]
        pred = int(model.predict(X)[0])

        if hasattr(model, "predict_proba"):
            score = float(model.predict_proba(X)[0, 1])
        elif hasattr(model, "decision_function"):
            decision = float(model.decision_function(X)[0])
            score = float(1.0 / (1.0 + np.exp(-decision)))
        else:
            score = float(pred)

        model_name = model.__class__.__name__
        return pred, score, model_name

    def predict_risk(
        self, disease: str, feature_payload: Dict
    ) -> Tuple[int, float, str, Dict[str, float], List[Dict[str, Any]]]:
        pred, score, model_name = self.predict(disease, feature_payload)
        profile = self.get_risk_profile(disease)
        thresholds = profile.get("thresholds", {"moderate": 0.4, "high": 0.75})
        top_factors = profile.get("top_factors", [])
        return pred, score, model_name, thresholds, top_factors


registry = ModelRegistry()
