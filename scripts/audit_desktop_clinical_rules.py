"""Probe the linked desktop app's CKD explanation with a synthetic demo case.

This is a deterministic source-behavior audit, not a clinical validation study.
Run from the repository root in an environment with the repository requirements installed.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = ROOT
OUTPUT = ROOT / "reports" / "clinical_validation" / "synthetic_ckd_rule_probe.json"
sys.path.insert(0, str(DESKTOP_ROOT))

from backend.rules import calibrate_disease_risk, explain_disease_risk  # noqa: E402


def main() -> None:
    # These are the synthetic defaults visible in the desktop UI screenshot.
    synthetic_inputs = {
        "age_years": 45,
        "sex": "male",
        "body_mass_index": 22.0,
        "systolic_bp_mmhg": 115.0,
        "diastolic_bp_mmhg": 75.0,
        "fasting_glucose_mg_dl": 90.0,
        "hba1c_pct": 5.2,
        "serum_creatinine_mg_dl": 0.9,
        "egfr_ml_min": 100.0,
        "serum_potassium_meq_l": 4.2,
        "serum_sodium_meq_l": 140.0,
    }

    disease_probes = {}
    for disease in ("ckd", "hypertension", "diabetes"):
        score_low_raw = calibrate_disease_risk(disease, 0.01, synthetic_inputs)
        score_high_raw = calibrate_disease_risk(disease, 0.99, synthetic_inputs)
        explanation = explain_disease_risk(
            disease, score_low_raw, "low", synthetic_inputs
        )
        disease_probes[disease] = {
            "raw_classifier_score_0_01_result": score_low_raw,
            "raw_classifier_score_0_99_result": score_high_raw,
            "score_unchanged_when_raw_classifier_score_changes": math.isclose(
                score_low_raw, score_high_raw, rel_tol=0.0, abs_tol=1e-12
            ),
            "first_generated_reason": explanation["why_reasons"][0],
            "generated_action_steps": explanation["action_steps"],
        }
    result = {
        "validation_type": "deterministic synthetic source-behavior probe",
        "synthetic_only": True,
        "clinical_performance_evidence": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": "Capstone-17/6th_Sem main @ cba57d92ea7271bed8789495be6739b212d4125b",
        "inputs": synthetic_inputs,
        "probes": disease_probes,
        "interpretation": (
            "A source-level behavior check only. Equal CKD scores despite raw model scores 0.01 and 0.99 "
            "show that the CKD score path is driven by hand-coded rules for this input. Hypertension and "
            "diabetes scores add hand-set adjustments to the raw score and clip it; this is not evidence "
            "of empirical calibration. The probe does not measure discrimination, calibration, safety, "
            "or clinical utility."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
