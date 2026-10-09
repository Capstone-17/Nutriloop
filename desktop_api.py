"""
desktop_api.py
──────────────
Python Desktop API bridge for Nutriloop.
Provides in-process bridge methods for pywebview JavaScript interface.
Handles:
  - Local database & persistence in the executable's directory
  - Ollama connectivity & 1-click model installation with streaming progress
  - Multi-disease clinical risk evaluation (CKD, HTN, T2DM)
  - 7-Day Regional Weekly Diet generation & file exporting (JSON/HTML)
  - Pre-LLM safety guardrail & ReAct / deterministic fallback Chatbot
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import sys
from pathlib import Path

# Prevent bytecode generation and __pycache__ directory creation across this process and child processes
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _purge_pycache() -> None:
    """Fast removal of all __pycache__ directories across the repository."""
    try:
        base_dir = Path(__file__).resolve().parent
        for target in base_dir.rglob("__pycache__"):
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


# Purge immediately to destroy any bytecode cached by the import loader before execution began
_purge_pycache()
atexit.register(_purge_pycache)

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import re

from backend.db import (
    BASE_DIR,
    DB_PATH,
    REPORTS_DIR,
    get_conn,
    init_db,
    insert_risk_explanation,
    save_patient_test,
    get_patient_test_history,
    get_patient_test_by_id,
    get_latest_patient_test,
    delete_patient_test,
    save_active_weekly_plan,
    get_active_weekly_plan,
    get_app_setting,
    set_app_setting,
)
from backend.ollama_manager import ollama_manager

log = logging.getLogger(__name__)


class DesktopAPI:
    """Methods exposed directly to the GUI via window.pywebview.api."""

    def __init__(self) -> None:
        init_db()
        self.ollama_base_url = "http://localhost:11434"
        self.recommended_model = "llama3.2:1b"


    # ──────────────────────────────────────────────────────────────────────────
    # System & Environment Info
    # ──────────────────────────────────────────────────────────────────────────

    def get_system_info(self) -> Dict[str, Any]:
        """Return system status, persistence directory, and database statistics."""
        from backend.model_registry import registry
        saved_files = list(REPORTS_DIR.glob("*.*")) if REPORTS_DIR.exists() else []

        # Count records in SQLite
        conn = get_conn()
        try:
            total_logs = conn.execute("SELECT COUNT(*) FROM risk_explanation_log;").fetchone()[0]
            total_meals = conn.execute("SELECT COUNT(*) FROM meal_log;").fetchone()[0]
        except Exception:
            total_logs = 0
            total_meals = 0
        finally:
            conn.close()

        ollama_status = self.check_ollama()

        return {
            "app_title": "Nutriloop - Clinical Nutrition & Risk Management",
            "version": "1.0.0 (Portable Standalone)",
            "user_data_dir": str(BASE_DIR),
            "db_path": str(DB_PATH),
            "reports_dir": str(REPORTS_DIR),
            "total_saved_reports": len(saved_files),
            "total_audit_logs": total_logs,
            "total_logged_meals": total_meals,
            "ollama": ollama_status,
            "models_loaded": {
                "ckd": registry.is_ready("ckd"),
                "hypertension": registry.is_ready("hypertension"),
                "diabetes": registry.is_ready("diabetes"),
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Ollama Model Manager
    # ──────────────────────────────────────────────────────────────────────────

    def check_ollama(self) -> Dict[str, Any]:
        """Check whether the model is installed on disk and service state."""
        is_running = ollama_manager.is_service_running()
        is_installed = ollama_manager.is_model_installed()
        has_binary = ollama_manager.is_binary_available()

        return {
            "running": is_running,
            "installed_models": [ollama_manager.recommended_model] if is_installed else [],
            "recommended_model": ollama_manager.recommended_model,
            "model_installed": is_installed,
            "binary_available": has_binary,
            "message": (
                "Model Ready (llama3.2:3b)" if is_installed
                else "Model Not Installed (Click Install in Settings)"
            ),
        }

    def start_model_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Trigger background pull of the model. Terminates daemon immediately when completed."""
        return ollama_manager.start_model_download(model_name)

    def pause_model_download(self) -> Dict[str, Any]:
        """Pause active model download and shut down background Ollama daemon."""
        return ollama_manager.pause_model_download()

    def resume_model_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Resume a paused model download from where it left off."""
        return ollama_manager.resume_model_download(model_name)

    def cancel_model_download(self) -> Dict[str, Any]:
        """Cancel model download, delete partial files, and shut down daemon."""
        return ollama_manager.cancel_model_download()

    def get_model_download_progress(self) -> Dict[str, Any]:
        """Return real-time pull status for UI progress bars."""
        return ollama_manager.get_download_progress()

    def terminate_ollama(self) -> Dict[str, Any]:
        """Explicitly terminate background Ollama daemon."""
        ollama_manager.terminate_service()
        return {"status": "terminated"}

    # ──────────────────────────────────────────────────────────────────────────
    # Patient Test History & Lab Text Parser
    # ──────────────────────────────────────────────────────────────────────────

    def list_patient_tests(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return catalog of previously saved test records for the patient."""
        try:
            records = get_patient_test_history(user_id)
            history_list = []
            for r in records:
                dt_str = r["created_at"][:16].replace("T", " ")
                status_tag = "Latest" if r.get("is_latest") else "Past"
                sbp_int = int(r["systolic_bp_mmhg"]) if r["systolic_bp_mmhg"] is not None else 120
                dbp_int = int(r["diastolic_bp_mmhg"]) if r["diastolic_bp_mmhg"] is not None else 80
                fbg_int = int(r["fasting_glucose_mg_dl"]) if r["fasting_glucose_mg_dl"] is not None else 100
                cr_str = f"{r['serum_creatinine_mg_dl']:.1f}" if r["serum_creatinine_mg_dl"] is not None else "N/A"
                label = f"{dt_str} ({status_tag}) — BP {sbp_int}/{dbp_int}, Gluc {fbg_int}, Cr {cr_str}"
                history_list.append({
                    "id": str(r["id"]),
                    "label": label,
                    "created_at": r["created_at"],
                    "is_latest": bool(r.get("is_latest")),
                    "user_id": r["user_id"],
                })
            return history_list
        except Exception as exc:
            log.warning("Failed to list patient test history: %s", exc)
            return []

    # Backward compatibility stub
    def list_demo_cases(self) -> List[Dict[str, str]]:
        return self.list_patient_tests()

    def load_patient_test(self, test_id: int) -> Dict[str, Any]:
        """Load and return a specific historical patient test record."""
        try:
            record = get_patient_test_by_id(int(test_id))
            if not record:
                return {"error": f"Test report #{test_id} not found."}
            return record
        except Exception as exc:
            return {"error": f"Failed to load test report: {exc}"}

    # Backward compatibility stub
    def load_demo_case(self, test_id: str) -> Dict[str, Any]:
        try:
            return self.load_patient_test(int(test_id))
        except Exception:
            return {"error": "Invalid test identifier."}

    def get_latest_test(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Return the latest test record for startup pre-population."""
        try:
            record = get_latest_patient_test(user_id)
            if not record:
                return {"found": False}
            record["found"] = True
            return record
        except Exception as exc:
            return {"found": False, "error": str(exc)}

    def delete_patient_test(self, test_id: int) -> Dict[str, Any]:
        """Delete an old test record from the database."""
        try:
            ok = delete_patient_test(int(test_id))
            return {"status": "success" if ok else "error", "deleted": ok}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def parse_lab_text(self, text: str) -> Dict[str, Any]:
        """
        Intelligently extracts patient vitals and biomarkers from unstructured
        clinical notes, lab reports, doctor summaries, or raw text paste.
        """
        if not text or not text.strip():
            return {"extracted": {}, "count": 0, "message": "No text provided to parse."}

        t = text.lower()
        extracted: Dict[str, Any] = {}

        # 1. Blood Pressure (e.g. 142/90, 130 / 85 mmHg, BP: 140/90, SBP 140 DBP 90)
        bp_match = re.search(r'(?:bp|blood\s*pressure)?(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3})\s*[/]\s*(\d{2,3})', t)
        if bp_match:
            sys_val = float(bp_match.group(1))
            dia_val = float(bp_match.group(2))
            if 60 <= sys_val <= 260 and 35 <= dia_val <= 160:
                extracted["systolic_bp_mmhg"] = int(sys_val)
                extracted["diastolic_bp_mmhg"] = int(dia_val)
        else:
            sbp_m = re.search(r'(?:systolic|sbp)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3})', t)
            if sbp_m:
                v = float(sbp_m.group(1))
                if 60 <= v <= 260:
                    extracted["systolic_bp_mmhg"] = int(v)
            dbp_m = re.search(r'(?:diastolic|dbp)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3})', t)
            if dbp_m:
                v = float(dbp_m.group(1))
                if 35 <= v <= 160:
                    extracted["diastolic_bp_mmhg"] = int(v)

        # 2. Fasting Blood Glucose (e.g. FBG: 126, FBS 110 mg/dL, Fasting glucose 95, Blood Sugar 140)
        fbg_match = re.search(
            r'(?:fasting\s*(?:blood\s*)?glucose|fasting\s*blood\s*sugar|fbg|fbs|fasting\s*sugar)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl)?',
            t
        )
        if fbg_match:
            val = float(fbg_match.group(1))
            if 40 <= val <= 450:
                extracted["fasting_glucose_mg_dl"] = round(val, 1)
        else:
            gluc_m = re.search(r'(?:blood\s*glucose|glucose)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl)?', t)
            if gluc_m:
                val = float(gluc_m.group(1))
                if 40 <= val <= 450:
                    extracted["fasting_glucose_mg_dl"] = round(val, 1)

        # 3. HbA1c (e.g. HbA1c: 7.2%, A1C 6.5, Glycated Hemoglobin 7.8%, Glycosylated Hb (HbA1c) 7.1%)
        hba1c_match = re.search(
            r'(?:hba1c|a1c|glyc(?:ated|osylated)\s*h(?:a?emoglobin)?)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*%?',
            t
        )
        if hba1c_match:
            val = float(hba1c_match.group(1))
            if 3.0 <= val <= 20.0:
                extracted["hba1c_pct"] = round(val, 1)

        # 4. Serum Creatinine (e.g. Serum Creatinine: 1.4 mg/dL, S. Creat 1.1, Creatinine 0.9)
        cr_match = re.search(
            r'(?:serum\s*creatinine|s\.?\s*creat(?:inine)?|creatinine|s\.?\s*cr)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:mg/dl)?',
            t
        )
        if cr_match:
            val = float(cr_match.group(1))
            if 0.1 <= val <= 25.0:
                extracted["serum_creatinine_mg_dl"] = round(val, 2)

        # 5. eGFR (e.g. eGFR: 45 mL/min, GFR 58, Estimated GFR: 92)
        egfr_match = re.search(
            r'(?:egfr|estimated\s*(?:glomerular\s*filtration\s*rate|gfr)|gfr)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:ml/min)?',
            t
        )
        if egfr_match:
            val = float(egfr_match.group(1))
            if 5.0 <= val <= 160.0:
                extracted["egfr_ml_min"] = round(val, 1)

        # 6. Serum Potassium (e.g. Potassium: 4.5, K+: 4.8 mEq/L, Serum K 4.2)
        pot_match = re.search(
            r'(?:serum\s*potassium|potassium|k\+?)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:meq/l|mmol/l)?',
            t
        )
        if pot_match:
            val = float(pot_match.group(1))
            if 2.0 <= val <= 8.5:
                extracted["serum_potassium_meq_l"] = round(val, 1)

        # 7. Serum Sodium (e.g. Sodium: 139, Na+: 141 mEq/L, Serum Na 140)
        sod_match = re.search(
            r'(?:serum\s*sodium|sodium|na\+?)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3}(?:\.\d{1,2})?)\s*(?:meq/l|mmol/l)?',
            t
        )
        if sod_match:
            val = float(sod_match.group(1))
            if 100.0 <= val <= 180.0:
                extracted["serum_sodium_meq_l"] = int(val)

        # 8. BMI (e.g. BMI: 28.4 kg/m2, Body Mass Index: 24.5)
        bmi_match = re.search(
            r'(?:body\s*mass\s*index|bmi)(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:kg/m2)?',
            t
        )
        if bmi_match:
            val = float(bmi_match.group(1))
            if 10.0 <= val <= 90.0:
                extracted["body_mass_index"] = round(val, 1)

        # 9. Age (e.g. 56-year-old, 56 yo, Age: 52, 45M)
        age_match = re.search(
            r'(?:age\s*[:=]?\s*(\d{1,3})|(\d{1,3})\s*(?:-|–|\s)?(?:year(?:s)?(?:-|\s)?old|yo|y/o|yr(?:s)?)\b)',
            t
        )
        if age_match:
            val_str = age_match.group(1) or age_match.group(2)
            if val_str:
                val = int(val_str)
                if 18 <= val <= 100:
                    extracted["age_years"] = val
        else:
            shorthand = re.search(r'\b(\d{2})\s*([mf])\b', t)
            if shorthand:
                val = int(shorthand.group(1))
                if 18 <= val <= 100:
                    extracted["age_years"] = val
                    extracted["sex"] = "male" if shorthand.group(2) == 'm' else "female"

        # 10. Sex (e.g. male, female, man, woman)
        if "sex" not in extracted:
            if re.search(r'\b(?:female|woman)\b', t):
                extracted["sex"] = "female"
            elif re.search(r'\b(?:male|man)\b', t):
                extracted["sex"] = "male"

        count = len(extracted)
        names = list(extracted.keys())
        return {
            "extracted": extracted,
            "count": count,
            "fields": names,
            "message": f"Successfully extracted {count} biomarker(s) from report text!" if count > 0 else "No recognized clinical biomarkers found in the pasted text.",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Multi-Disease Risk Assessment
    # ──────────────────────────────────────────────────────────────────────────

    def assess_patient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate multi-disease risk across CKD, Hypertension, and Diabetes.
        Computes calibrated scores, top risk factors, and logs to SQLite.
        """
        user_id = payload.get("user_id", "patient_local")
        raw_inputs = payload.get("raw_inputs", payload.get("test_reports", payload))

        # Flatten test_reports & top-level fields for mapping if needed
        merged_inputs = dict(raw_inputs)
        for k in ("age_years", "sex", "body_mass_index"):
            if k in payload and k not in merged_inputs:
                merged_inputs[k] = payload[k]

        # 1. Strict Outpatient Physiological Validation
        val_errors = []
        sbp = merged_inputs.get("systolic_bp_mmhg")
        dbp = merged_inputs.get("diastolic_bp_mmhg")
        fbg = merged_inputs.get("fasting_glucose_mg_dl")
        hba1c = merged_inputs.get("hba1c_pct")
        sc = merged_inputs.get("serum_creatinine_mg_dl")
        egfr = merged_inputs.get("egfr_ml_min")
        sod = merged_inputs.get("serum_sodium_meq_l")
        pot = merged_inputs.get("serum_potassium_meq_l")
        age = merged_inputs.get("age_years")
        bmi = merged_inputs.get("body_mass_index")

        if sod is not None and (sod < 100.0 or sod > 180.0):
            val_errors.append(
                f"Serum Sodium ({sod} mEq/L) is outside human physiological boundaries (100–180 mEq/L).\n"
                "Normal adult blood serum sodium is strictly 135–145 mEq/L.\n"
                "Did you accidentally enter dietary sodium intake in milligrams (e.g. 1000 mg salt) instead of blood Serum Sodium (mEq/L)?"
            )
        if pot is not None and (pot < 2.0 or pot > 8.5):
            val_errors.append(f"Serum Potassium ({pot} mEq/L) is outside physiological limits (2.0–8.5 mEq/L). Normal reference: 3.5–5.0 mEq/L.")
        if hba1c is not None and (hba1c < 3.0 or hba1c > 20.0):
            val_errors.append(f"HbA1c ({hba1c}%) is outside clinical laboratory limits (3.0%–20.0%). Normal reference: < 5.7%.")
        if egfr is not None and (egfr < 5.0 or egfr > 160.0):
            val_errors.append(f"Estimated GFR ({egfr} mL/min) is outside valid clinical limits (5–160 mL/min).")
        if fbg is not None and (fbg < 40.0 or fbg > 450.0):
            val_errors.append(f"Fasting Glucose ({fbg} mg/dL) is outside outpatient limits (40–450 mg/dL).")
        if sbp is not None and (sbp < 70.0 or sbp > 260.0):
            val_errors.append(f"Systolic Blood Pressure ({sbp} mmHg) is outside physiological boundaries (70–260 mmHg).")
        if dbp is not None and (dbp < 40.0 or dbp > 160.0):
            val_errors.append(f"Diastolic Blood Pressure ({dbp} mmHg) is outside physiological boundaries (40–160 mmHg).")
        if sc is not None and (sc < 0.1 or sc > 25.0):
            val_errors.append(f"Serum Creatinine ({sc} mg/dL) is outside clinical limits (0.1–25.0 mg/dL).")

        if val_errors:
            return {
                "status": "error",
                "message": "\n\n".join(val_errors),
                "field_errors": val_errors,
            }

        assessments = {}
        detected_conditions = []
        now = datetime.now(timezone.utc).isoformat()

        from backend.model_registry import registry
        from backend.raw_input import map_raw_payload
        from backend.rules import (
            build_calibration_context,
            calibrate_disease_risk,
            classify_risk_level,
            explain_disease_risk,
        )

        for disease in ["ckd", "hypertension", "diabetes"]:
            try:
                mapping_res = map_raw_payload(disease, merged_inputs)
                features = mapping_res.transformed_features

                pred_class, raw_risk_score, model_name, thresholds, top_factors = registry.predict_risk(
                    disease, features
                )
                risk_score = calibrate_disease_risk(disease, raw_risk_score, merged_inputs)
                risk_level = classify_risk_level(risk_score, thresholds)
                pred_class = 1 if risk_level in ["moderate", "high"] else 0
                calib = build_calibration_context(disease, risk_score, thresholds, top_factors)
                explanation = explain_disease_risk(disease, risk_score, risk_level, merged_inputs)

                if risk_level in ["moderate", "high"]:
                    name_map = {
                        "ckd": "Chronic Kidney Disease (CKD)",
                        "hypertension": "Hypertension",
                        "diabetes": "Type 2 Diabetes Mellitus",
                    }
                    detected_conditions.append(name_map[disease])

                # Log to local SQLite DB
                insert_risk_explanation(
                    disease=disease,
                    model_name=model_name,
                    predicted_class=pred_class,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    threshold_moderate=thresholds.get("moderate", 0.35),
                    threshold_high=thresholds.get("high", 0.65),
                    threshold_band=calib.get("band_label", risk_level),
                    major_risk_factors=explanation.get("risk_drivers", []),
                    validation_warnings=mapping_res.validation_warnings,
                    raw_inputs=merged_inputs,
                    transformed_features=features,
                    top_factors=top_factors,
                    calibration_context=calib,
                    explanation_text=explanation.get("clinical_summary", f"Risk assessed as {risk_level}."),
                    user_id=user_id,
                    source="desktop_gui_assessment",
                )

                assessments[disease] = {
                    "disease": disease,
                    "risk_score": round(risk_score, 4),
                    "risk_level": risk_level,
                    "predicted_class": int(pred_class),
                    "thresholds": thresholds,
                    "top_factors": top_factors[:5],
                    "calibration": calib,
                    "explanation": explanation,
                    "warnings": mapping_res.validation_warnings,
                }
            except Exception as exc:
                log.exception("Assessment error for %s", disease)
                assessments[disease] = {
                    "disease": disease,
                    "error": str(exc),
                    "risk_level": "unknown",
                    "risk_score": 0.0,
                }

        # 2. Comprehensive Electrolyte & Laboratory Comorbidity Detection
        sex = str(merged_inputs.get("sex", "male")).lower()
        if sod is not None:
            if sod > 145:
                detected_conditions.append(f"Hypernatremia (High Sodium: {int(sod)} mEq/L)")
            elif sod < 135:
                detected_conditions.append(f"Hyponatremia (Low Sodium: {int(sod)} mEq/L)")
        if pot is not None:
            if pot > 5.0:
                detected_conditions.append(f"Hyperkalemia (High Potassium: {pot:.1f} mEq/L - Renal Risk)")
            elif pot < 3.5:
                detected_conditions.append(f"Hypokalemia (Low Potassium: {pot:.1f} mEq/L)")

        if egfr is not None and egfr < 60:
            stage_str = "Stage 4-5 Severe" if egfr < 30 else "Stage 3"
            if not any("Chronic Kidney Disease" in c for c in detected_conditions):
                detected_conditions.append(f"Renal Impairment ({stage_str} CKD, eGFR {int(egfr)} mL/min)")
        creat_upper = 1.2 if sex == "male" else 1.0
        if sc is not None and sc > creat_upper:
            detected_conditions.append(f"Elevated Serum Creatinine ({sc:.1f} mg/dL)")

        if sbp is not None and dbp is not None:
            if sbp >= 140 or dbp >= 90:
                if not any("Hypertension" in c for c in detected_conditions):
                    detected_conditions.append(f"Stage 2 Hypertension ({int(sbp)}/{int(dbp)} mmHg)")
            elif (130 <= sbp < 140) or (80 <= dbp < 90):
                if not any("Hypertension" in c for c in detected_conditions):
                    detected_conditions.append(f"Stage 1 Hypertension ({int(sbp)}/{int(dbp)} mmHg)")

        if (fbg is not None and fbg >= 126) or (hba1c is not None and hba1c >= 6.5):
            if not any("Diabetes" in c for c in detected_conditions):
                detected_conditions.append("Type 2 Diabetes (Diagnostic Glycemia)")
        elif (fbg is not None and 100 <= fbg < 126) or (hba1c is not None and 5.7 <= hba1c < 6.5):
            detected_conditions.append("Prediabetes (Impaired Glucose / HbA1c)")

        # Deduplicate detected conditions
        detected_conditions = list(dict.fromkeys(detected_conditions))

        # Deduplicate error notices if multiple disease models failed on the same input
        error_items = [v["error"] for v in assessments.values() if "error" in v]
        unique_errors = list(dict.fromkeys(error_items))
        validation_notice = "\n\n".join(unique_errors) if unique_errors else None

        # Check if the inputs match the latest saved test report for this patient
        is_duplicate = False
        saved_test_id = None
        try:
            latest_test = get_latest_patient_test(user_id)
            if latest_test:
                prev_labs = latest_test.get("test_reports", {})
                fields_to_compare = [
                    "systolic_bp_mmhg",
                    "diastolic_bp_mmhg",
                    "fasting_glucose_mg_dl",
                    "hba1c_pct",
                    "serum_creatinine_mg_dl",
                    "egfr_ml_min",
                    "serum_potassium_meq_l",
                    "serum_sodium_meq_l",
                    "age_years",
                    "sex",
                    "body_mass_index",
                ]
                all_match = True
                for field in fields_to_compare:
                    curr_val = merged_inputs.get(field)
                    prev_val = latest_test.get(field, prev_labs.get(field))
                    if isinstance(curr_val, str) or isinstance(prev_val, str):
                        if str(curr_val or "").strip().lower() != str(prev_val or "").strip().lower():
                            all_match = False
                            break
                    else:
                        c_num = float(curr_val) if curr_val is not None else None
                        p_num = float(prev_val) if prev_val is not None else None
                        if c_num is None and p_num is None:
                            continue
                        if c_num is None or p_num is None or abs(c_num - p_num) > 0.001:
                            all_match = False
                            break
                if all_match:
                    is_duplicate = True
                    saved_test_id = latest_test["id"]

            if not is_duplicate:
                saved_test_id = save_patient_test(
                    user_id=user_id,
                    raw_inputs=merged_inputs,
                    assessments=assessments,
                    detected_conditions=detected_conditions,
                )
        except Exception as exc:
            log.warning("Failed to save patient test to history: %s", exc)

        return {
            "status": "success",
            "user_id": user_id,
            "timestamp": now,
            "saved_test_id": saved_test_id,
            "is_duplicate": is_duplicate,
            "detected_conditions": detected_conditions,
            "assessments": assessments,
            "raw_inputs": merged_inputs,
            "validation_notice": validation_notice,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 7-Day Regional Weekly Diet Plan
    # ──────────────────────────────────────────────────────────────────────────

    def generate_weekly_diet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a 7-Day, 5-interval personalized meal plan with regional cuisine."""
        try:
            from backend.schemas import WeeklyDietPlanRequest
            from backend.weekly_diet_engine import weekly_diet_engine
            req = WeeklyDietPlanRequest.model_validate(payload)
            plan = weekly_diet_engine.generate_weekly_plan(req)
            plan_dict = plan.model_dump()
            # Synchronize with active_weekly_plan database table
            save_active_weekly_plan(req.user_id, plan_dict)
            return {"status": "success", "plan": plan_dict}
        except Exception as exc:
            log.exception("Weekly diet generation failed")
            return {"status": "error", "message": str(exc)}

    def save_weekly_diet_report(self, plan_data: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
        """
        Save the generated 7-Day diet plan to the local user's folder as both
        structured JSON and a self-contained, printable HTML report.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_pid = "".join(c for c in patient_id if c.isalnum() or c in ("-", "_")) or "patient"
        json_file = REPORTS_DIR / f"{safe_pid}_weekly_diet_{timestamp}.json"
        html_file = REPORTS_DIR / f"{safe_pid}_weekly_diet_{timestamp}.html"

        # 1. Save JSON
        json_file.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 2. Save Printable HTML Report
        html_content = self._render_diet_html(plan_data)
        html_file.write_text(html_content, encoding="utf-8")

        return {
            "status": "saved",
            "json_path": str(json_file),
            "html_path": str(html_file),
            "filename": html_file.name,
        }

    def _render_diet_html(self, plan_data: Dict[str, Any]) -> str:
        """Render self-contained, printable HTML report with modern clinical styling."""
        pid = plan_data.get("user_id") or plan_data.get("patient_id", "Patient")
        reg = (plan_data.get("patient_summary") or {}).get("native_region") or plan_data.get("regional_cuisine", "Regional Cuisine")
        conds = ", ".join(plan_data.get("detected_conditions", [])) or "General Health Maintenance"
        ct = plan_data.get("clinical_targets") or {}
        cal = ct.get("calories_kcal") or plan_data.get("caloric_target_kcal", 1800)
        sod = ct.get("sodium_limit_mg") or plan_data.get("sodium_target_mg", 1500)
        pot = ct.get("potassium_guidance_mg", 2000)
        pro = ct.get("protein_g") or plan_data.get("protein_target_g", 60)
        alerts = plan_data.get("medication_alerts") or plan_data.get("active_medication_alerts", [])

        alerts_html = ""
        if alerts:
            alerts_html = "<div class='alerts-box'><h3>⚠️ Active Medication & Pharmacopeia Alerts</h3><ul>"
            for a in alerts:
                alerts_html += f"<li>{a}</li>"
            alerts_html += "</ul></div>"

        craving_html = ""
        cs = plan_data.get("smart_craving_strategy")
        if cs and cs.get("requested_craving"):
            craving_html = f"""
            <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 14px 18px; margin-bottom: 24px; border-radius: 6px;">
              <h3 style="margin-top: 0; color: #1d4ed8; font-size: 15px;">🎯 Smart Craving Budgeting: <span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{cs.get('requested_craving')}</span></h3>
              <p style="margin: 4px 0; font-size: 13.5px;"><strong>Scheduled Indulgence:</strong> {cs.get('scheduled_day')} ({cs.get('scheduled_meal')}) — <em>{cs.get('indulgence_title')}</em></p>
              <p style="margin: 4px 0; font-size: 12.5px; color: #334155;">⚖️ <strong>Metabolic Balance:</strong> {cs.get('metabolic_rebalance_note')}</p>
              <p style="margin: 4px 0; font-size: 12px; color: #2563eb;">🔒 <strong>Strict 6-Day Lock:</strong> {cs.get('six_day_lock_note')}</p>
            </div>
            """

        days_html = ""
        for day in plan_data.get("days", []):
            d_num = day.get("day_number", 1)
            d_name = day.get("day_name", f"Day {d_num}")
            totals = day.get("daily_total_nutrients", {})
            days_html += f"""
            <div class="day-card">
              <div class="day-header">
                <h2>Day {d_num}: {d_name}</h2>
                <div class="nutri-pill">
                  {totals.get('calories', cal)} kcal | P: {totals.get('protein_g', pro)}g | 
                  Na: {totals.get('sodium_mg', sod)}mg | K: {totals.get('potassium_mg', pot)}mg
                </div>
              </div>
              <table class="meal-table">
                <thead>
                  <tr>
                    <th>Time / Interval</th>
                    <th>Meal Title & Items</th>
                    <th>Calories</th>
                    <th>Protein</th>
                    <th>Sodium</th>
                    <th>Clinical Guidance</th>
                  </tr>
                </thead>
                <tbody>
            """
            for inv in day.get("intervals", []):
                items_str = "<br>".join(
                    f"• <strong>{it.get('item_name')}</strong> ({it.get('portion', '')})"
                    for it in inv.get("items", [])
                )
                nut = inv.get("total_nutrients", {})
                days_html += f"""
                  <tr>
                    <td><strong>{inv.get('interval_name')}</strong><br><small>{inv.get('time_window')}</small></td>
                    <td><div class="meal-title">{inv.get('meal_title')}</div><small>{items_str}</small></td>
                    <td>{nut.get('calories', '-')} kcal</td>
                    <td>{nut.get('protein_g', '-')} g</td>
                    <td>{nut.get('sodium_mg', '-')} mg</td>
                    <td><small>{inv.get('clinical_justification', '')}</small></td>
                  </tr>
                """
            days_html += "</tbody></table></div>"
        cat_groceries = plan_data.get("categorized_grocery_checklist", {})
        if cat_groceries:
            sec_html = ""
            for cat_title, items in cat_groceries.items():
                items_li = "".join(f"<li>{it}</li>" for it in items)
                sec_html += f"<div style='margin-bottom: 12px;'><strong style='color:#065f46;'>{cat_title}</strong><ul style='margin: 4px 0 0; padding-left: 20px;'>{items_li}</ul></div>"
            grocery_block = f"""
            <div class="grocery-box">
              <h3>🛒 Weekly Categorized Grocery Checklist</h3>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 10px;">
                {sec_html}
              </div>
            </div>
            """
        else:
            grocery_items = "".join(f"<li>{g}</li>" for g in plan_data.get("grocery_checklist", []))
            grocery_block = f"""
            <div class="grocery-box">
              <h3>🛒 Weekly Grocery Checklist</h3>
              <ul>{grocery_items}</ul>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>7-Day Medical Nutrition Plan - {pid}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 24px; }}
  .container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  h1 {{ color: #0f172a; margin-top: 0; font-size: 26px; border-bottom: 2px solid #06b6d4; padding-bottom: 8px; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 16px 0 24px; background: #f1f5f9; padding: 16px; border-radius: 8px; font-size: 14px; }}
  .alerts-box {{ background: #fff1f2; border-left: 4px solid #f43f5e; padding: 16px; margin-bottom: 24px; border-radius: 6px; }}
  .alerts-box h3 {{ margin-top: 0; color: #be123c; font-size: 16px; }}
  .day-card {{ margin-bottom: 28px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
  .day-header {{ background: #0f172a; color: #ffffff; padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; }}
  .day-header h2 {{ margin: 0; font-size: 18px; }}
  .nutri-pill {{ background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 12px; font-size: 13px; }}
  .meal-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .meal-table th, .meal-table td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; text-align: left; vertical-align: top; }}
  .meal-table th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
  .meal-title {{ font-weight: 600; color: #0284c7; margin-bottom: 4px; }}
  .grocery-box {{ margin-top: 32px; padding: 20px; background: #ecfdf5; border-left: 4px solid #10b981; border-radius: 6px; }}
  .grocery-box ul {{ columns: 2; margin: 8px 0 0; padding-left: 20px; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .container {{ box-shadow: none; padding: 0; }} .day-card {{ page-break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>Nutriloop - 7-Day Personalized Regional Nutrition Plan</h1>
  <div class="meta-grid">
    <div><strong>Patient ID:</strong> {pid}</div>
    <div><strong>Region & Diet:</strong> {reg}</div>
    <div><strong>Conditions:</strong> {conds}</div>
    <div><strong>Targets:</strong> {cal} kcal | Na &le; {sod}mg | K &le; {pot}mg | Pro: {pro}g</div>
  </div>
  {alerts_html}
  {craving_html}
  {days_html}
  {grocery_block}
</div>
</body>
</html>"""

    # ──────────────────────────────────────────────────────────────────────────
    # AI Clinical Nutritionist (Chatbot)
    # ──────────────────────────────────────────────────────────────────────────

    def send_chat_message(
        self,
        user_id: str,
        message: str,
        disease: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send consultation message to Dr. Nutriloop AI."""
        try:
            from backend.chatbot.agent import run_agent
            result = run_agent(
                user_id=user_id,
                message=message,
                disease=disease or "general",
                conversation_history=conversation_history,
                provider=provider,
                api_key=api_key,
            )
            return result
        except Exception as exc:
            log.exception("Chat execution failure")
            return {
                "reply": f"Dr. Nutriloop: An error occurred while processing your message: {exc}",
                "tool_calls_made": [],
                "escalated": False,
                "latency_ms": 0.0,
                "steps": 0,
                "engine_mode": "Error",
            }

    def save_ai_settings(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Save AI provider preference and optional API key."""
        try:
            prov = (provider or "auto").strip().lower()
            set_app_setting("ai_provider", prov)
            if api_key is not None:
                cleaned_key = api_key.strip()
                if cleaned_key:
                    if prov == "gemini":
                        set_app_setting("gemini_api_key", cleaned_key)
                    elif prov == "openai":
                        set_app_setting("openai_api_key", cleaned_key)
            return {"status": "success", "provider": prov}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_ai_settings(self) -> Dict[str, Any]:
        """Return saved AI provider and masked key status."""
        try:
            prov = get_app_setting("ai_provider", "auto")
            gemini_key = get_app_setting("gemini_api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
            openai_key = get_app_setting("openai_api_key") or os.getenv("OPENAI_API_KEY") or ""

            def mask(k: str) -> str:
                if not k or len(k) < 8:
                    return ""
                return f"{k[:4]}...{k[-4:]}"

            return {
                "provider": prov,
                "has_gemini_key": bool(gemini_key),
                "gemini_masked": mask(gemini_key),
                "has_openai_key": bool(openai_key),
                "openai_masked": mask(openai_key),
            }
        except Exception as exc:
            return {"provider": "auto", "has_gemini_key": False, "has_openai_key": False, "error": str(exc)}

    def get_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch past audit logs for this patient from the local SQLite DB."""
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                SELECT id, disease, risk_level, explanation_text, raw_inputs_json, created_at
                FROM risk_explanation_log
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 25;
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "disease": r["disease"],
                    "risk_level": r["risk_level"],
                    "summary": r["explanation_text"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ──────────────────────────────────────────────────────────────────────────
    # Local Reports & Storage Explorer
    # ──────────────────────────────────────────────────────────────────────────

    def list_saved_reports(self) -> List[Dict[str, Any]]:
        """List all generated reports in the user's local folder."""
        if not REPORTS_DIR.exists():
            return []

        reports = []
        for p in sorted(REPORTS_DIR.glob("*.*"), key=os.path.getmtime, reverse=True):
            stat = p.stat()
            reports.append({
                "filename": p.name,
                "path": str(p),
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "is_html": p.suffix.lower() == ".html",
                "is_json": p.suffix.lower() == ".json",
            })
        return reports

    def open_reports_folder(self) -> Dict[str, Any]:
        """Open the local saved_reports directory in Windows File Explorer."""
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(REPORTS_DIR))
            return {"status": "opened", "path": str(REPORTS_DIR)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
