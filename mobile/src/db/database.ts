import * as SQLite from "expo-sqlite";
import { Platform } from "react-native";
import {
  PatientVitals,
  MultiDiseaseAssessmentResult,
  WeeklyDietPlan,
  PatientTestHistoryRecord,
  SavePatientTestResult,
} from "../types/clinical";

class MobileDatabase {
  private db: SQLite.SQLiteDatabase | null = null;
  private memoryHistory: PatientTestHistoryRecord[] = [];
  private memoryPlan: WeeklyDietPlan | null = null;

  private areVitalsEqual(v1: PatientVitals, v2: PatientVitals): boolean {
    if (String(v1.sex || "").toLowerCase().trim() !== String(v2.sex || "").toLowerCase().trim()) {
      return false;
    }
    const numFields: (keyof PatientVitals)[] = [
      "ageYears",
      "bodyMassIndex",
      "systolicBpMmhg",
      "diastolicBpMmhg",
      "fastingGlucoseMgDl",
      "hba1cPct",
      "serumCreatinineMgDl",
      "egfrMlMin",
      "serumPotassiumMeqL",
      "serumSodiumMeqL",
    ];
    for (const f of numFields) {
      const val1 = Number(v1[f]);
      const val2 = Number(v2[f]);
      if (isNaN(val1) && isNaN(val2)) continue;
      if (isNaN(val1) || isNaN(val2)) return false;
      if (Math.abs(val1 - val2) > 0.001) return false;
    }
    return true;
  }

  async getDb(): Promise<SQLite.SQLiteDatabase | null> {
    if (Platform.OS === "web") {
      return null;
    }
    if (!this.db) {
      try {
        this.db = await SQLite.openDatabaseAsync("nutriloop_offline.db");
        await this.initTables(this.db);
      } catch (err) {
        console.warn("SQLite not available on this platform, using memory storage:", err);
        return null;
      }
    }
    return this.db;
  }

  private async initTables(db: SQLite.SQLiteDatabase): Promise<void> {
    await db.execAsync(`
      PRAGMA journal_mode = WAL;

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
        detected_conditions_json TEXT NOT NULL,
        assessments_json TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS active_weekly_plan (
        user_id TEXT PRIMARY KEY,
        plan_json TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
      );
    `);
  }

  async getLatestPatientTest(userId: string = "patient_local"): Promise<PatientTestHistoryRecord | null> {
    const db = await this.getDb();
    if (!db) {
      return this.memoryHistory.length > 0 ? this.memoryHistory[0] : null;
    }

    const row = await db.getFirstAsync<any>(
      `SELECT * FROM patient_test_history WHERE user_id = ? ORDER BY id DESC LIMIT 1;`,
      [userId]
    );

    if (!row) return null;

    return {
      id: row.id,
      userId: row.user_id,
      createdAt: row.created_at,
      vitals: {
        ageYears: row.age_years,
        sex: row.sex as "male" | "female",
        bodyMassIndex: row.body_mass_index,
        systolicBpMmhg: row.systolic_bp_mmhg,
        diastolicBpMmhg: row.diastolic_bp_mmhg,
        fastingGlucoseMgDl: row.fasting_glucose_mg_dl,
        hba1cPct: row.hba1c_pct,
        serumCreatinineMgDl: row.serum_creatinine_mg_dl,
        egfrMlMin: row.egfr_ml_min,
        serumPotassiumMeqL: row.serum_potassium_meq_l,
        serumSodiumMeqL: row.serum_sodium_meq_l,
      },
      detectedConditions: JSON.parse(row.detected_conditions_json || "[]"),
      assessments: JSON.parse(row.assessments_json || "{}"),
    };
  }

  async savePatientTest(
    userId: string,
    vitals: PatientVitals,
    assessmentResult: MultiDiseaseAssessmentResult
  ): Promise<SavePatientTestResult> {
    // Check if the vitals match the latest saved report for this patient
    const latestTest = await this.getLatestPatientTest(userId);
    if (latestTest && this.areVitalsEqual(latestTest.vitals, vitals)) {
      return { id: latestTest.id, isDuplicate: true };
    }

    const db = await this.getDb();
    if (!db) {
      const newRecord: PatientTestHistoryRecord = {
        id: Date.now(),
        userId,
        createdAt: new Date().toISOString(),
        vitals,
        detectedConditions: assessmentResult.detectedConditions,
        assessments: assessmentResult.assessments,
      };
      this.memoryHistory.unshift(newRecord);
      return { id: newRecord.id, isDuplicate: false };
    }

    const result = await db.runAsync(
      `INSERT INTO patient_test_history (
        user_id, age_years, sex, body_mass_index,
        systolic_bp_mmhg, diastolic_bp_mmhg, fasting_glucose_mg_dl,
        hba1c_pct, serum_creatinine_mg_dl, egfr_ml_min,
        serum_potassium_meq_l, serum_sodium_meq_l,
        detected_conditions_json, assessments_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
      [
        userId,
        vitals.ageYears,
        vitals.sex,
        vitals.bodyMassIndex,
        vitals.systolicBpMmhg,
        vitals.diastolicBpMmhg,
        vitals.fastingGlucoseMgDl,
        vitals.hba1cPct,
        vitals.serumCreatinineMgDl,
        vitals.egfrMlMin,
        vitals.serumPotassiumMeqL,
        vitals.serumSodiumMeqL,
        JSON.stringify(assessmentResult.detectedConditions),
        JSON.stringify(assessmentResult.assessments),
      ]
    );
    return { id: result.lastInsertRowId, isDuplicate: false };
  }

  async getPatientTestHistory(userId: string = "patient_local"): Promise<PatientTestHistoryRecord[]> {
    const db = await this.getDb();
    if (!db) {
      return [...this.memoryHistory];
    }

    const rows = await db.getAllAsync<any>(
      `SELECT * FROM patient_test_history WHERE user_id = ? ORDER BY id DESC LIMIT 30;`,
      [userId]
    );

    return rows.map((r) => ({
      id: r.id,
      userId: r.user_id,
      createdAt: r.created_at,
      vitals: {
        ageYears: r.age_years,
        sex: r.sex as "male" | "female",
        bodyMassIndex: r.body_mass_index,
        systolicBpMmhg: r.systolic_bp_mmhg,
        diastolicBpMmhg: r.diastolic_bp_mmhg,
        fastingGlucoseMgDl: r.fasting_glucose_mg_dl,
        hba1cPct: r.hba1c_pct,
        serumCreatinineMgDl: r.serum_creatinine_mg_dl,
        egfrMlMin: r.egfr_ml_min,
        serumPotassiumMeqL: r.serum_potassium_meq_l,
        serumSodiumMeqL: r.serum_sodium_meq_l,
      },
      detectedConditions: JSON.parse(r.detected_conditions_json || "[]"),
      assessments: JSON.parse(r.assessments_json || "{}"),
    }));
  }

  async deletePatientTest(testId: number): Promise<boolean> {
    const db = await this.getDb();
    if (!db) {
      const prevLen = this.memoryHistory.length;
      this.memoryHistory = this.memoryHistory.filter((r) => r.id !== testId);
      return this.memoryHistory.length < prevLen;
    }
    const res = await db.runAsync(`DELETE FROM patient_test_history WHERE id = ?;`, [testId]);
    return res.changes > 0;
  }

  async saveActivePlan(userId: string, plan: WeeklyDietPlan): Promise<void> {
    const db = await this.getDb();
    if (!db) {
      this.memoryPlan = plan;
      return;
    }
    await db.runAsync(
      `INSERT INTO active_weekly_plan (user_id, plan_json, updated_at)
       VALUES (?, ?, CURRENT_TIMESTAMP)
       ON CONFLICT(user_id) DO UPDATE SET plan_json = excluded.plan_json, updated_at = CURRENT_TIMESTAMP;`,
      [userId, JSON.stringify(plan)]
    );
  }

  async getActivePlan(userId: string = "patient_local"): Promise<WeeklyDietPlan | null> {
    const db = await this.getDb();
    if (!db) {
      return this.memoryPlan;
    }
    const row = await db.getFirstAsync<any>(
      `SELECT plan_json FROM active_weekly_plan WHERE user_id = ?;`,
      [userId]
    );
    if (!row || !row.plan_json) return null;
    try {
      return JSON.parse(row.plan_json) as WeeklyDietPlan;
    } catch {
      return null;
    }
  }

  async saveSetting(key: string, value: string): Promise<void> {
    const db = await this.getDb();
    if (!db) return;
    await db.runAsync(
      `INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
       ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value;`,
      [key, value]
    );
  }

  async getSetting(key: string): Promise<string | null> {
    const db = await this.getDb();
    if (!db) return null;
    const row = await db.getFirstAsync<{ setting_value: string }>(
      `SELECT setting_value FROM app_settings WHERE setting_key = ?;`,
      [key]
    );
    return row ? row.setting_value : null;
  }
}

export const dbManager = new MobileDatabase();
