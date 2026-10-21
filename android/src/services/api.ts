import {
  PatientVitals,
  MultiDiseaseAssessmentResult,
  WeeklyDietPlan,
  PatientPreferences,
  DiseaseAssessment,
} from "../types/clinical";
import { dbManager } from "../db/database";
import { roundToDecimal } from "../utils/formatters";
import { ENV } from "../config/env";

// Default host derived from environment / platform config
export const DEFAULT_BACKEND_URL = ENV.apiUrl;

export interface ChatbotApiResponse {
  reply: string;
  tool_calls_made?: string[];
  escalated?: boolean;
  latency_ms?: number;
  steps?: number;
  engine_mode?: string;
  updated_diet_plan?: any;
}

export class ApiService {
  private static cachedUrl: string | null = null;

  static async getBaseUrl(): Promise<string> {
    if (this.cachedUrl) return this.cachedUrl;
    try {
      const saved = await dbManager.getSetting("backend_url");
      if (saved && saved.trim().length > 0) {
        this.cachedUrl = saved.trim().replace(/\/+$/, "");
        return this.cachedUrl;
      }
    } catch {
      // Fallback to environment default
    }
    this.cachedUrl = ENV.apiUrl;
    return this.cachedUrl;
  }

  static async setBaseUrl(url: string): Promise<void> {
    const clean = url.trim().replace(/\/+$/, "");
    this.cachedUrl = clean;
    await dbManager.saveSetting("backend_url", clean);
  }

  /**
   * Resilient HTTP fetch wrapper with AbortController timeout and exponential-backoff retries.
   */
  private static async fetchWithTimeoutAndRetry(
    url: string,
    options: RequestInit,
    timeoutMs: number = ENV.timeouts.defaultMs,
    maxAttempts: number = ENV.retries.maxAttempts,
    baseDelayMs: number = ENV.retries.baseDelayMs
  ): Promise<Response> {
    let lastError: any = null;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });
        clearTimeout(timer);

        // Retry on 502/503/504 server gateway issues
        if ([502, 503, 504].includes(response.status) && attempt < maxAttempts) {
          await new Promise((res) => setTimeout(res, baseDelayMs * Math.pow(2, attempt - 1)));
          continue;
        }

        return response;
      } catch (err: any) {
        clearTimeout(timer);
        lastError = err;

        if (err.name === "AbortError") {
          lastError = new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
        }

        if (attempt < maxAttempts) {
          await new Promise((res) => setTimeout(res, baseDelayMs * Math.pow(2, attempt - 1)));
        }
      }
    }

    throw lastError || new Error(`Network request failed for ${url}`);
  }

  /**
   * Health ping to check if the Nutriloop backend server is reachable.
   */
  static async checkServerHealth(): Promise<boolean> {
    try {
      const baseUrl = await this.getBaseUrl();
      const res = await this.fetchWithTimeoutAndRetry(
        `${baseUrl}/health`,
        { method: "GET" },
        5000,
        1
      );
      return res.ok;
    } catch {
      return false;
    }
  }

  /**
   * Run multi-disease risk evaluation by calling Python backend /assess-patient.
   */
  static async assessPatient(vitals: PatientVitals): Promise<MultiDiseaseAssessmentResult> {
    const baseUrl = await this.getBaseUrl();
    const payload = {
      user_id: "patient_mobile",
      age_years: vitals.ageYears,
      sex: vitals.sex,
      body_mass_index: vitals.bodyMassIndex,
      systolic_bp_mmhg: vitals.systolicBpMmhg,
      diastolic_bp_mmhg: vitals.diastolicBpMmhg,
      fasting_glucose_mg_dl: vitals.fastingGlucoseMgDl,
      hba1c_pct: vitals.hba1cPct,
      serum_creatinine_mg_dl: vitals.serumCreatinineMgDl,
      egfr_ml_min: vitals.egfrMlMin,
      serum_potassium_meq_l: vitals.serumPotassiumMeqL,
      serum_sodium_meq_l: vitals.serumSodiumMeqL,
    };

    const response = await this.fetchWithTimeoutAndRetry(
      `${baseUrl}/assess-patient`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      ENV.timeouts.assessmentMs
    );

    if (!response.ok) {
      throw new Error(`Assessment API returned HTTP ${response.status}`);
    }

    const data = await response.json();
    const assessmentsRaw = data.assessments || {};

    const mapDisease = (
      disKey: "ckd" | "hypertension" | "diabetes",
      name: string
    ): DiseaseAssessment => {
      const item = assessmentsRaw[disKey] || {};
      const exp = item.explanation || {};
      const score = typeof item.risk_score === "number" ? item.risk_score : 0.0;
      const level = (item.risk_level || "low").toLowerCase() as "low" | "moderate" | "high";

      return {
        disease: disKey,
        diseaseName: exp.disease_name || name,
        riskScore: roundToDecimal(score, 2),
        riskLevel: level,
        riskPercentage: roundToDecimal(score * 100, 2),
        primaryDrivers: exp.risk_drivers || [],
        protectiveFactors: exp.protective_factors || [],
        clinicalSummary:
          exp.clinical_summary ||
          `Clinical evaluation indicates ${level} risk profile.`,
      };
    };

    return {
      timestamp: new Date().toISOString(),
      detectedConditions: data.detected_conditions || [],
      assessments: {
        ckd: mapDisease("ckd", "Chronic Kidney Disease"),
        hypertension: mapDisease("hypertension", "Hypertension"),
        diabetes: mapDisease("diabetes", "Type 2 Diabetes Mellitus"),
      },
      vitals: { ...vitals },
    };
  }

  /**
   * Generate 7-Day Regional Weekly Diet Plan by calling Python backend /recommend-weekly-plan.
   */
  static async generateWeeklyDiet(
    vitals: PatientVitals,
    prefs: PatientPreferences,
    reportDate?: string,
    isHistorical?: boolean
  ): Promise<WeeklyDietPlan> {
    const baseUrl = await this.getBaseUrl();
    const payload = {
      user_id: "patient_mobile",
      age_years: vitals.ageYears,
      sex: vitals.sex,
      body_mass_index: vitals.bodyMassIndex,
      systolic_bp_mmhg: vitals.systolicBpMmhg,
      diastolic_bp_mmhg: vitals.diastolicBpMmhg,
      fasting_glucose_mg_dl: vitals.fastingGlucoseMgDl,
      hba1c_pct: vitals.hba1cPct,
      serum_creatinine_mg_dl: vitals.serumCreatinineMgDl,
      egfr_ml_min: vitals.egfrMlMin,
      serum_potassium_meq_l: vitals.serumPotassiumMeqL,
      serum_sodium_meq_l: vitals.serumSodiumMeqL,
      region: prefs.nativeRegion,
      dietary_type: prefs.dietaryType,
      calorie_target_kcal: prefs.calorieOverride,
      food_allergies: prefs.allergies || [],
      preferred_choices: prefs.interestsAndLikes || [],
      smart_craving: prefs.cravingOrTreat,
      active_medications: prefs.activeMedications || [],
      cooking_skills: prefs.cookingSkill || "intermediate",
      prep_time_limit_mins: prefs.maxPrepTimeMins || 45,
    };

    const response = await this.fetchWithTimeoutAndRetry(
      `${baseUrl}/recommend-weekly-plan`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      ENV.timeouts.dietPlanMs
    );

    if (!response.ok) {
      throw new Error(`Weekly diet API returned HTTP ${response.status}`);
    }

    const data = await response.json();
    const ct = data.clinical_targets || {};

    const days = (data.days || []).map((d: any) => ({
      dayNumber: d.day_number,
      dayName: d.day_name,
      intervals: (d.intervals || []).map((inv: any) => ({
        intervalName: inv.interval_name,
        timeWindow: inv.time_window,
        mealTitle: inv.meal_title,
        items: (inv.items || []).map((it: any) => ({
          itemName: it.item_name,
          portion: it.portion,
          nutrients: {
            calories: it.nutrients?.calories,
            proteinG: it.nutrients?.protein_g,
            sodiumMg: it.nutrients?.sodium_mg,
            potassiumMg: it.nutrients?.potassium_mg,
            carbsG: it.nutrients?.carbs_g,
          },
        })),
        totalNutrients: {
          calories: roundToDecimal(inv.total_nutrients?.calories || 0, 2),
          proteinG: roundToDecimal(inv.total_nutrients?.protein_g || 0, 2),
          sodiumMg: roundToDecimal(inv.total_nutrients?.sodium_mg || 0, 2),
          potassiumMg: roundToDecimal(inv.total_nutrients?.potassium_mg || 0, 2),
          carbsG: roundToDecimal(inv.total_nutrients?.carbs_g || 0, 2),
        },
        clinicalJustification: inv.clinical_justification || "",
        prepTips: inv.prep_tips || "",
      })),
      dailyTotalNutrients: {
        calories: roundToDecimal(d.daily_total_nutrients?.calories || 0, 2),
        proteinG: roundToDecimal(d.daily_total_nutrients?.protein_g || 0, 2),
        sodiumMg: roundToDecimal(d.daily_total_nutrients?.sodium_mg || 0, 2),
        potassiumMg: roundToDecimal(d.daily_total_nutrients?.potassium_mg || 0, 2),
      },
    }));

    return {
      userId: data.user_id || "patient_mobile",
      generatedAt: data.generated_at || new Date().toISOString(),
      testReportDate: reportDate,
      isHistoricalTest: isHistorical,
      calibratedVitals: { ...vitals },
      nativeRegion: (data.native_region || prefs.nativeRegion).toUpperCase().replace("_", " "),
      dietaryType: (data.dietary_type || prefs.dietaryType).toUpperCase(),
      caloricTargetKcal: roundToDecimal(data.caloric_target_kcal || ct.calories_kcal || 1800, 2),
      proteinTargetG: roundToDecimal(data.protein_target_g || ct.protein_g || 60, 2),
      sodiumTargetMg: roundToDecimal(data.sodium_target_mg || ct.sodium_limit_mg || 1500, 2),
      potassiumTargetMg: roundToDecimal(data.potassium_target_mg || ct.potassium_guidance_mg || 2000, 2),
      carbohydrateTargetG: roundToDecimal(ct.carbohydrate_g || 220, 2),
      fatTargetG: roundToDecimal(ct.fat_g || 50, 2),
      fiberTargetG: roundToDecimal(ct.fiber_target_g || 28, 2),
      phosphorusTargetMg: roundToDecimal(ct.phosphorus_limit_mg || 1000, 2),
      fluidIntakeMl: roundToDecimal(ct.fluid_intake_ml || 2000, 2),
      clinicalTargets: {
        calories_kcal: roundToDecimal(ct.calories_kcal || 1800, 2),
        protein_g: roundToDecimal(ct.protein_g || 60, 2),
        carbohydrate_g: roundToDecimal(ct.carbohydrate_g || 220, 2),
        fat_g: roundToDecimal(ct.fat_g || 50, 2),
        fiber_target_g: roundToDecimal(ct.fiber_target_g || 28, 2),
        sodium_limit_mg: roundToDecimal(ct.sodium_limit_mg || 1500, 2),
        potassium_guidance_mg: roundToDecimal(ct.potassium_guidance_mg || 2000, 2),
        phosphorus_limit_mg: roundToDecimal(ct.phosphorus_limit_mg || 1000, 2),
        fluid_intake_ml: roundToDecimal(ct.fluid_intake_ml || 2000, 2),
      },
      detectedConditions: data.detected_conditions || [],
      medicationAlerts: data.medication_alerts || [],
      days,
      categorizedGroceries: data.categorized_groceries || {},
      cravingStrategy: data.craving_strategy
        ? {
            requestedCraving: data.craving_strategy.requested_craving,
            scheduledDay: data.craving_strategy.scheduled_day,
            scheduledMeal: data.craving_strategy.scheduled_meal,
            metabolicRebalanceNote: data.craving_strategy.metabolic_rebalance_note,
            sixDayLockNote: data.craving_strategy.six_day_lock_note,
          }
        : undefined,
    };
  }

  /**
   * Primary clinical AI chat calling FastAPI POST /chatbot/chat.
   * Zero client-side API keys required — all LLM and tool inference is securely handled server-side.
   */
  static async sendChatMessage(
    message: string,
    history: { role: "user" | "assistant"; content: string }[],
    disease: string = "ckd",
    userId: string = "patient_mobile"
  ): Promise<string> {
    const baseUrl = await this.getBaseUrl();
    const payload = {
      user_id: userId,
      message,
      disease,
      diseases: ["ckd", "hypertension", "diabetes"],
      conversation_history: history.map((m) => ({
        role: m.role,
        content: m.content,
      })),
    };

    try {
      const response = await this.fetchWithTimeoutAndRetry(
        `${baseUrl}/chatbot/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        ENV.timeouts.chatMs,
        1 // Chat calls are not automatically retried to avoid duplicate agent turns
      );

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data: ChatbotApiResponse = await response.json();
      return (
        data.reply ||
        "I have processed your clinical dietary query based on standard KDIGO/ADA guidelines."
      );
    } catch (err: any) {
      console.warn("Server chatbot call failed, activating graceful clinical fallback:", err);
      // Graceful clinical fallback if server is unreachable
      return (
        `⚠️ Dr. Nutriloop Clinical Advisory (Offline Reference):\n\n` +
        `We could not reach the clinical AI reasoning server (${err?.message || "connection error"}).\n\n` +
        `• Sodium: Maintain <1500–2000 mg/day (AHA DASH / KDIGO standard).\n` +
        `• Potassium: Consult your latest serum test (normal 3.5–5.0 mEq/L) before high-potassium foods.\n` +
        `• Hydration: Confirm fluid limits with your nephrologist if experiencing edema.\n\n` +
        `Please ensure the Nutriloop backend server is running and verify the host setting.`
      );
    }
  }

  /**
   * Deprecated: legacy direct-LLM chat with user-provided key.
   * Re-routes directly to server-side sendChatMessage to keep bundle secret-free.
   */
  static async chatWithUserApiKey(
    message: string,
    history: { role: "user" | "assistant"; content: string }[],
    _apiKey?: string,
    _vitalsSummary?: string
  ): Promise<string> {
    return this.sendChatMessage(message, history);
  }
}
