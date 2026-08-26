import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, Optional, List


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "app_data.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
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

    conn.commit()
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
