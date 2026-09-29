import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, List, Generator

def get_data_dir() -> Path:
    """Return dedicated directory for patient data (database, saved reports, models, logs).
    If running as a standalone executable:
      - Uses or creates a 'Nutriloop_Data' folder in the directory next to the .exe.
      - If shifted to a new location alone, automatically creates 'Nutriloop_Data' there.
    If running from source code:
      - Uses or creates 'Nutriloop_Data' in the workspace root.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent

    data_dir = base_dir / "Nutriloop_Data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Migrate from legacy NutriMed_Patient_Data if it exists and app_data.db isn't in Nutriloop_Data yet
    legacy_dir = base_dir / "NutriMed_Patient_Data"
    if legacy_dir.exists() and not (data_dir / "app_data.db").exists() and (legacy_dir / "app_data.db").exists():
        try:
            import shutil
            shutil.copy2(str(legacy_dir / "app_data.db"), str(data_dir / "app_data.db"))
        except Exception:
            pass

    return data_dir

BASE_DIR = get_data_dir()
DB_PATH = BASE_DIR / "app_data.db"
REPORTS_DIR = BASE_DIR / "saved_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


@contextmanager
def get_db_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                disease TEXT NOT NULL,
                risk_score REAL NOT NULL,
                predicted_class INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS diet_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                disease TEXT NOT NULL,
                calories_target INTEGER NOT NULL,
                protein_target_g INTEGER NOT NULL,
                carb_target_g INTEGER NOT NULL,
                fat_target_g INTEGER NOT NULL,
                sodium_limit_mg INTEGER NOT NULL,
                potassium_limit_mg INTEGER NOT NULL,
                recommendation_note TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meal_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                planned_calories INTEGER NOT NULL,
                consumed_calories INTEGER NOT NULL,
                deviation_flag INTEGER NOT NULL,
                deviation_percent REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alert (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_explanation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                disease TEXT NOT NULL,
                model_name TEXT NOT NULL,
                predicted_class INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                threshold_moderate REAL NOT NULL,
                threshold_high REAL NOT NULL,
                threshold_band TEXT NOT NULL,
                major_risk_factors_json TEXT NOT NULL,
                validation_warnings_json TEXT NOT NULL,
                raw_inputs_json TEXT NOT NULL,
                transformed_features_json TEXT NOT NULL,
                top_factors_json TEXT NOT NULL,
                calibration_context_json TEXT NOT NULL,
                explanation_text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'api',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS adaptation_action (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action_id TEXT UNIQUE NOT NULL,
                trigger_type TEXT NOT NULL,
                action_type TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                priority INTEGER NOT NULL,
                reason TEXT NOT NULL,
                executed INTEGER NOT NULL DEFAULT 0,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_pattern (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_data_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pattern_type)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                source TEXT NOT NULL,
                rating INTEGER,
                text_feedback TEXT,
                meal_id TEXT,
                recommendation_id TEXT,
                metadata_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS health_outcome (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                outcome_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                baseline_value REAL,
                change_from_baseline REAL,
                clinical_significance TEXT NOT NULL,
                measurement_context_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                conversation_history_json TEXT NOT NULL,
                user_profile_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_test_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                age_years INTEGER NOT NULL,
                sex TEXT NOT NULL,
                body_mass_index REAL NOT NULL,
                systolic_bp_mmhg REAL NOT NULL,
                diastolic_bp_mmhg REAL NOT NULL,
                fasting_glucose_mg_dl REAL NOT NULL,
                hba1c_pct REAL,
                serum_creatinine_mg_dl REAL,
                egfr_ml_min REAL,
                serum_potassium_meq_l REAL,
                serum_sodium_meq_l REAL,
                report_summary_text TEXT,
                raw_inputs_json TEXT NOT NULL,
                detected_conditions_json TEXT NOT NULL,
                assessments_json TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS active_weekly_plan (
                user_id TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def get_app_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
        row = cur.fetchone()
        return str(row["setting_value"]) if row else default
    except Exception:
        return default
    finally:
        conn.close()


def set_app_setting(key: str, value: str) -> None:
    with get_db_conn() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value)
        )


def save_patient_test(
    user_id: str,
    raw_inputs: Dict[str, Any],
    assessments: Dict[str, Any],
    detected_conditions: List[str],
) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        labs = raw_inputs.get("test_reports", raw_inputs)
        age = int(raw_inputs.get("age_years", 50) or 50)
        sex = str(raw_inputs.get("sex", "male")).lower()
        bmi = float(raw_inputs.get("body_mass_index", 25.0) or 25.0)
        sbp = float(labs.get("systolic_bp_mmhg", 120.0) or 120.0)
        dbp = float(labs.get("diastolic_bp_mmhg", 80.0) or 80.0)
        fbg = float(labs.get("fasting_glucose_mg_dl", 100.0) or 100.0)
        hba1c = float(labs.get("hba1c_pct")) if labs.get("hba1c_pct") is not None else None
        sc = float(labs.get("serum_creatinine_mg_dl")) if labs.get("serum_creatinine_mg_dl") is not None else None
        egfr = float(labs.get("egfr_ml_min")) if labs.get("egfr_ml_min") is not None else None
        pot = float(labs.get("serum_potassium_meq_l")) if labs.get("serum_potassium_meq_l") is not None else None
        sod = float(labs.get("serum_sodium_meq_l")) if labs.get("serum_sodium_meq_l") is not None else None
        summary = str(labs.get("report_summary_text", "") or "")

        cur.execute(
            """
            INSERT INTO patient_test_history (
                user_id, age_years, sex, body_mass_index,
                systolic_bp_mmhg, diastolic_bp_mmhg, fasting_glucose_mg_dl,
                hba1c_pct, serum_creatinine_mg_dl, egfr_ml_min,
                serum_potassium_meq_l, serum_sodium_meq_l, report_summary_text,
                raw_inputs_json, detected_conditions_json, assessments_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, age, sex, bmi,
                sbp, dbp, fbg,
                hba1c, sc, egfr,
                pot, sod, summary,
                json.dumps(raw_inputs),
                json.dumps(detected_conditions),
                json.dumps(assessments),
            ),
        )
        test_id = cur.lastrowid
        conn.commit()
        return test_id
    finally:
        conn.close()


def get_patient_test_history(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if user_id and user_id.strip():
            cur.execute(
                """
                SELECT id, user_id, created_at, age_years, sex, body_mass_index,
                       systolic_bp_mmhg, diastolic_bp_mmhg, fasting_glucose_mg_dl,
                       hba1c_pct, serum_creatinine_mg_dl, egfr_ml_min,
                       serum_potassium_meq_l, serum_sodium_meq_l, report_summary_text,
                       detected_conditions_json, assessments_json
                FROM patient_test_history
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (user_id.strip(),),
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, created_at, age_years, sex, body_mass_index,
                       systolic_bp_mmhg, diastolic_bp_mmhg, fasting_glucose_mg_dl,
                       hba1c_pct, serum_creatinine_mg_dl, egfr_ml_min,
                       serum_potassium_meq_l, serum_sodium_meq_l, report_summary_text,
                       detected_conditions_json, assessments_json
                FROM patient_test_history
                ORDER BY id DESC
                """
            )
        rows = cur.fetchall()
        results = []
        for i, r in enumerate(rows):
            results.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "created_at": r["created_at"],
                "is_latest": (i == 0),
                "age_years": r["age_years"],
                "sex": r["sex"],
                "body_mass_index": r["body_mass_index"],
                "systolic_bp_mmhg": r["systolic_bp_mmhg"],
                "diastolic_bp_mmhg": r["diastolic_bp_mmhg"],
                "fasting_glucose_mg_dl": r["fasting_glucose_mg_dl"],
                "hba1c_pct": r["hba1c_pct"],
                "serum_creatinine_mg_dl": r["serum_creatinine_mg_dl"],
                "egfr_ml_min": r["egfr_ml_min"],
                "serum_potassium_meq_l": r["serum_potassium_meq_l"],
                "serum_sodium_meq_l": r["serum_sodium_meq_l"],
                "report_summary_text": r["report_summary_text"],
                "detected_conditions": json.loads(r["detected_conditions_json"]) if r["detected_conditions_json"] else [],
                "assessments": json.loads(r["assessments_json"]) if r["assessments_json"] else {},
            })
        return results
    finally:
        conn.close()


def get_patient_test_by_id(test_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, created_at, age_years, sex, body_mass_index,
                   systolic_bp_mmhg, diastolic_bp_mmhg, fasting_glucose_mg_dl,
                   hba1c_pct, serum_creatinine_mg_dl, egfr_ml_min,
                   serum_potassium_meq_l, serum_sodium_meq_l, report_summary_text,
                   raw_inputs_json, detected_conditions_json, assessments_json
            FROM patient_test_history
            WHERE id = ?
            """,
            (test_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        labs_dict = {
            "systolic_bp_mmhg": r["systolic_bp_mmhg"],
            "diastolic_bp_mmhg": r["diastolic_bp_mmhg"],
            "fasting_glucose_mg_dl": r["fasting_glucose_mg_dl"],
            "hba1c_pct": r["hba1c_pct"],
            "serum_creatinine_mg_dl": r["serum_creatinine_mg_dl"],
            "egfr_ml_min": r["egfr_ml_min"],
            "serum_potassium_meq_l": r["serum_potassium_meq_l"],
            "serum_sodium_meq_l": r["serum_sodium_meq_l"],
            "report_summary_text": r["report_summary_text"],
        }
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "created_at": r["created_at"],
            "age_years": r["age_years"],
            "sex": r["sex"],
            "body_mass_index": r["body_mass_index"],
            "systolic_bp_mmhg": r["systolic_bp_mmhg"],
            "diastolic_bp_mmhg": r["diastolic_bp_mmhg"],
            "fasting_glucose_mg_dl": r["fasting_glucose_mg_dl"],
            "hba1c_pct": r["hba1c_pct"],
            "serum_creatinine_mg_dl": r["serum_creatinine_mg_dl"],
            "egfr_ml_min": r["egfr_ml_min"],
            "serum_potassium_meq_l": r["serum_potassium_meq_l"],
            "serum_sodium_meq_l": r["serum_sodium_meq_l"],
            "report_summary_text": r["report_summary_text"],
            "test_reports": labs_dict,
            "raw_inputs": json.loads(r["raw_inputs_json"]) if r["raw_inputs_json"] else {},
            "detected_conditions": json.loads(r["detected_conditions_json"]) if r["detected_conditions_json"] else [],
            "assessments": json.loads(r["assessments_json"]) if r["assessments_json"] else {},
        }
    finally:
        conn.close()


def get_latest_patient_test(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if user_id and user_id.strip():
            cur.execute(
                """
                SELECT id FROM patient_test_history
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (user_id.strip(),),
            )
        else:
            cur.execute(
                """
                SELECT id FROM patient_test_history
                ORDER BY id DESC LIMIT 1
                """
            )
        r = cur.fetchone()
        if not r:
            return None
        return get_patient_test_by_id(r["id"])
    finally:
        conn.close()


def delete_patient_test(test_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM patient_test_history WHERE id = ?", (test_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()



def insert_risk_profile(user_id: str, disease: str, risk_score: float, predicted_class: int) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO risk_profile (user_id, disease, risk_score, predicted_class) VALUES (?, ?, ?, ?)",
        (user_id, disease, risk_score, predicted_class),
    )
    conn.commit()
    conn.close()


def insert_diet_plan(user_id: str, disease: str, plan: Dict[str, Any]) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO diet_plan (
            user_id, disease, calories_target, protein_target_g, carb_target_g,
            fat_target_g, sodium_limit_mg, potassium_limit_mg, recommendation_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            disease,
            plan["calories_target"],
            plan["protein_target_g"],
            plan["carb_target_g"],
            plan["fat_target_g"],
            plan["sodium_limit_mg"],
            plan["potassium_limit_mg"],
            plan["recommendation_note"],
        ),
    )
    conn.commit()
    conn.close()


def insert_meal_log(user_id: str, planned_calories: int, consumed_calories: int, deviation_flag: bool, deviation_percent: float, notes: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO meal_log (user_id, planned_calories, consumed_calories, deviation_flag, deviation_percent, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, planned_calories, consumed_calories, int(deviation_flag), deviation_percent, notes),
    )
    conn.commit()
    meal_id = cur.lastrowid
    conn.close()
    return int(meal_id)


def insert_alert(user_id: str, severity: str, message: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alert (user_id, severity, message) VALUES (?, ?, ?)",
        (user_id, severity, message),
    )
    conn.commit()
    alert_id = cur.lastrowid
    conn.close()
    return int(alert_id)


def get_open_alert_count(user_id: Optional[str] = None) -> int:
    conn = get_conn()
    if user_id:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM alert WHERE status = 'open' AND user_id = ?",
            (user_id,),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS count FROM alert WHERE status = 'open'").fetchone()
    conn.close()
    return int(row["count"]) if row else 0


def insert_risk_explanation(
    disease: str,
    model_name: str,
    predicted_class: int,
    risk_score: float,
    risk_level: str,
    threshold_moderate: float,
    threshold_high: float,
    threshold_band: str,
    major_risk_factors: List[str],
    validation_warnings: List[str],
    raw_inputs: Dict[str, Any],
    transformed_features: Dict[str, Any],
    top_factors: List[Dict[str, Any]],
    calibration_context: Dict[str, Any],
    explanation_text: str,
    user_id: Optional[str] = None,
    source: str = "api",
) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO risk_explanation_log (
            user_id,
            disease,
            model_name,
            predicted_class,
            risk_score,
            risk_level,
            threshold_moderate,
            threshold_high,
            threshold_band,
            major_risk_factors_json,
            validation_warnings_json,
            raw_inputs_json,
            transformed_features_json,
            top_factors_json,
            calibration_context_json,
            explanation_text,
            source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            disease,
            model_name,
            int(predicted_class),
            float(risk_score),
            risk_level,
            float(threshold_moderate),
            float(threshold_high),
            threshold_band,
            json.dumps(major_risk_factors),
            json.dumps(validation_warnings),
            json.dumps(raw_inputs),
            json.dumps(transformed_features),
            json.dumps(top_factors),
            json.dumps(calibration_context),
            explanation_text,
            source,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return int(row_id)


def get_risk_explanations(
    disease: Optional[str] = None,
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    where_parts: List[str] = []
    params: List[Any] = []

    if disease:
        where_parts.append("disease = ?")
        params.append(disease)
    if user_id:
        where_parts.append("user_id = ?")
        params.append(user_id)
    if source:
        where_parts.append("source = ?")
        params.append(source)
    if from_ts:
        where_parts.append("created_at >= ?")
        params.append(from_ts)
    if to_ts:
        where_parts.append("created_at <= ?")
        params.append(to_ts)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    rows = conn.execute(
        f"""
        SELECT
            id,
            user_id,
            disease,
            model_name,
            predicted_class,
            risk_score,
            risk_level,
            threshold_moderate,
            threshold_high,
            threshold_band,
            major_risk_factors_json,
            validation_warnings_json,
            raw_inputs_json,
            transformed_features_json,
            top_factors_json,
            calibration_context_json,
            explanation_text,
            source,
            created_at
        FROM risk_explanation_log
        {where_clause}
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, int(limit), int(offset)),
    ).fetchall()
    conn.close()

    items: List[Dict[str, Any]] = []
    for row in rows:
        major_risk_factors = json.loads(row["major_risk_factors_json"])
        validation_warnings = json.loads(row["validation_warnings_json"])
        raw_inputs = json.loads(row["raw_inputs_json"])
        transformed_features = json.loads(row["transformed_features_json"])
        top_factors = json.loads(row["top_factors_json"])
        calibration_context = json.loads(row["calibration_context_json"])
        items.append(
            {
                "id": int(row["id"]),
                "user_id": row["user_id"],
                "disease": row["disease"],
                "model_name": row["model_name"],
                "predicted_class": int(row["predicted_class"]),
                "risk_score": float(row["risk_score"]),
                "risk_level": row["risk_level"],
                "thresholds": {
                    "moderate": float(row["threshold_moderate"]),
                    "high": float(row["threshold_high"]),
                },
                "threshold_band": row["threshold_band"],
                "major_risk_factors": major_risk_factors,
                "validation_warnings": validation_warnings,
                "raw_inputs": raw_inputs,
                "transformed_features": transformed_features,
                "top_factors": top_factors,
                "calibration_context": calibration_context,
                "explanation_text": row["explanation_text"],
                "source": row["source"],
                "created_at": row["created_at"],
            }
        )
    return items


def get_risk_explanation_summary() -> Dict[str, Any]:
    conn = get_conn()

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM risk_explanation_log"
    ).fetchone()
    by_source_rows = conn.execute(
        "SELECT source, COUNT(*) AS c FROM risk_explanation_log GROUP BY source ORDER BY c DESC"
    ).fetchall()
    by_disease_rows = conn.execute(
        "SELECT disease, COUNT(*) AS c FROM risk_explanation_log GROUP BY disease ORDER BY c DESC"
    ).fetchall()
    by_risk_rows = conn.execute(
        "SELECT risk_level, COUNT(*) AS c FROM risk_explanation_log GROUP BY risk_level ORDER BY c DESC"
    ).fetchall()

    latest = conn.execute(
        """
        SELECT id, disease, source, risk_level, created_at
        FROM risk_explanation_log
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 5
        """
    ).fetchall()
    conn.close()

    return {
        "total": int(total_row["c"]) if total_row else 0,
        "by_source": {str(r["source"]): int(r["c"]) for r in by_source_rows},
        "by_disease": {str(r["disease"]): int(r["c"]) for r in by_disease_rows},
        "by_risk_level": {str(r["risk_level"]): int(r["c"]) for r in by_risk_rows},
        "latest": [
            {
                "id": int(r["id"]),
                "disease": str(r["disease"]),
                "source": str(r["source"]),
                "risk_level": str(r["risk_level"]),
                "created_at": str(r["created_at"]),
            }
            for r in latest
        ],
    }


# ==============================================================================
# Persistent Helpers: Adaptation Actions & User Patterns
# ==============================================================================
def insert_adaptation_action(
    user_id: str,
    action_id: str,
    trigger_type: str,
    action_type: str,
    parameters: Dict[str, Any],
    priority: int,
    reason: str,
    executed: bool = False,
    result: Optional[str] = None,
) -> int:
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO adaptation_action (
                user_id, action_id, trigger_type, action_type, parameters_json, priority, reason, executed, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                action_id,
                trigger_type,
                action_type,
                json.dumps(parameters),
                int(priority),
                reason,
                int(executed),
                result,
            ),
        )
        return int(cur.lastrowid)


def get_adaptation_actions(user_id: Optional[str] = None, executed_only: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_conn() as conn:
        query = "SELECT * FROM adaptation_action WHERE 1=1"
        params: List[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if executed_only is not None:
            query += " AND executed = ?"
            params.append(1 if executed_only else 0)
        query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
        params.append(int(limit))

        rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": int(r["id"]),
                "user_id": r["user_id"],
                "action_id": r["action_id"],
                "trigger_type": r["trigger_type"],
                "action_type": r["action_type"],
                "parameters": json.loads(r["parameters_json"]),
                "priority": int(r["priority"]),
                "reason": r["reason"],
                "executed": bool(r["executed"]),
                "result": r["result"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def upsert_user_pattern(
    user_id: str,
    pattern_type: str,
    pattern_data: Dict[str, Any],
    confidence: float,
    sample_size: int,
) -> None:
    with get_db_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_pattern (user_id, pattern_type, pattern_data_json, confidence, sample_size, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, pattern_type) DO UPDATE SET
                pattern_data_json = excluded.pattern_data_json,
                confidence = excluded.confidence,
                sample_size = excluded.sample_size,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, pattern_type, json.dumps(pattern_data), float(confidence), int(sample_size)),
        )


def get_user_patterns(user_id: str) -> Dict[str, Dict[str, Any]]:
    with get_db_conn() as conn:
        rows = conn.execute(
            "SELECT pattern_type, pattern_data_json, confidence, sample_size FROM user_pattern WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {
            r["pattern_type"]: {
                "data": json.loads(r["pattern_data_json"]),
                "confidence": float(r["confidence"]),
                "sample_size": int(r["sample_size"]),
            }
            for r in rows
        }


# ==============================================================================
# Persistent Helpers: Feedback & Health Outcomes
# ==============================================================================
def insert_feedback_record(
    user_id: str,
    feedback_type: str,
    source: str,
    rating: Optional[int] = None,
    text_feedback: Optional[str] = None,
    meal_id: Optional[str] = None,
    recommendation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO feedback_record (
                user_id, feedback_type, source, rating, text_feedback, meal_id, recommendation_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                feedback_type,
                source,
                rating,
                text_feedback,
                meal_id,
                recommendation_id,
                json.dumps(metadata or {}),
            ),
        )
        return int(cur.lastrowid)


def get_feedback_records(user_id: Optional[str] = None, feedback_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_conn() as conn:
        query = "SELECT * FROM feedback_record WHERE 1=1"
        params: List[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if feedback_type:
            query += " AND feedback_type = ?"
            params.append(feedback_type)
        query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
        params.append(int(limit))

        rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": int(r["id"]),
                "user_id": r["user_id"],
                "feedback_type": r["feedback_type"],
                "source": r["source"],
                "rating": r["rating"],
                "text_feedback": r["text_feedback"],
                "meal_id": r["meal_id"],
                "recommendation_id": r["recommendation_id"],
                "metadata": json.loads(r["metadata_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def insert_health_outcome(
    user_id: str,
    outcome_type: str,
    value: float,
    unit: str,
    baseline_value: Optional[float] = None,
    change_from_baseline: Optional[float] = None,
    clinical_significance: str = "neutral",
    measurement_context: Optional[Dict[str, Any]] = None,
) -> int:
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO health_outcome (
                user_id, outcome_type, value, unit, baseline_value, change_from_baseline, clinical_significance, measurement_context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                outcome_type,
                float(value),
                unit,
                float(baseline_value) if baseline_value is not None else None,
                float(change_from_baseline) if change_from_baseline is not None else None,
                clinical_significance,
                json.dumps(measurement_context or {}),
            ),
        )
        return int(cur.lastrowid)


def get_health_outcomes(user_id: Optional[str] = None, outcome_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_conn() as conn:
        query = "SELECT * FROM health_outcome WHERE 1=1"
        params: List[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if outcome_type:
            query += " AND outcome_type = ?"
            params.append(outcome_type)
        query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
        params.append(int(limit))

        rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": int(r["id"]),
                "user_id": r["user_id"],
                "outcome_type": r["outcome_type"],
                "value": float(r["value"]),
                "unit": r["unit"],
                "baseline_value": float(r["baseline_value"]) if r["baseline_value"] is not None else None,
                "change_from_baseline": float(r["change_from_baseline"]) if r["change_from_baseline"] is not None else None,
                "clinical_significance": r["clinical_significance"],
                "measurement_context": json.loads(r["measurement_context_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


# ==============================================================================
# Persistent Helpers: Agent Sessions
# ==============================================================================
def upsert_agent_session(user_id: str, conversation_history: List[Dict[str, Any]], user_profile: Dict[str, Any]) -> None:
    with get_db_conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_session (user_id, conversation_history_json, user_profile_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                conversation_history_json = excluded.conversation_history_json,
                user_profile_json = excluded.user_profile_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, json.dumps(conversation_history), json.dumps(user_profile)),
        )


def get_agent_session(user_id: str) -> Optional[Dict[str, Any]]:
    with get_db_conn() as conn:
        row = conn.execute(
            "SELECT conversation_history_json, user_profile_json, updated_at FROM agent_session WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "conversation_history": json.loads(row["conversation_history_json"]),
            "user_profile": json.loads(row["user_profile_json"]),
            "updated_at": row["updated_at"],
        }


# ==============================================================================
# Persistent Helpers: Active Weekly Diet Plan
# ==============================================================================
def save_active_weekly_plan(user_id: str, plan_data: Dict[str, Any]) -> None:
    """Persist or overwrite the latest 7-Day Regional Weekly Diet Plan for this patient."""
    with get_db_conn() as conn:
        conn.execute(
            """
            INSERT INTO active_weekly_plan (user_id, plan_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                plan_json = excluded.plan_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, json.dumps(plan_data, ensure_ascii=False)),
        )


def get_active_weekly_plan(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current active 7-Day Weekly Diet Plan for this patient."""
    with get_db_conn() as conn:
        row = conn.execute(
            "SELECT plan_json, updated_at FROM active_weekly_plan WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["plan_json"])
        except Exception:
            return None


# Initialize schema automatically
init_db()

