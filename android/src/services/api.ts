import { Platform } from "react-native";
import {
  PatientVitals,
  MultiDiseaseAssessmentResult,
  WeeklyDietPlan,
  PatientPreferences,
  DiseaseAssessment,
} from "../types/clinical";
import { dbManager } from "../db/database";
import { roundToDecimal } from "../utils/formatters";

// Default host based on execution platform
export const DEFAULT_BACKEND_URL =
  Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";

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
      // Fallback to default
    }
    this.cachedUrl = DEFAULT_BACKEND_URL;
    return this.cachedUrl;
  }

  static async setBaseUrl(url: string): Promise<void> {
    const clean = url.trim().replace(/\/+$/, "");
    this.cachedUrl = clean;
    await dbManager.saveSetting("backend_url", clean);
  }

  /**
   * Run multi-disease risk evaluation by calling common Python backend /assess-patient.
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

    const response = await fetch(`${baseUrl}/assess-patient`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

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
   * Generate 7-Day Regional Weekly Diet Plan by calling common Python backend /recommend-weekly-plan.
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

    const response = await fetch(`${baseUrl}/recommend-weekly-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

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
   * Direct Gemini / OpenAI LLM Chat using user-pasted API key.
   * Completely independent of Ollama.
   */
  static async chatWithUserApiKey(
    message: string,
    history: { role: "user" | "assistant"; content: string }[],
    apiKey: string,
    vitalsSummary?: string
  ): Promise<string> {
    if (!apiKey || apiKey.trim().length === 0) {
      throw new Error("Please configure your API key in Settings to chat with Nutriloop AI.");
    }

    const key = apiKey.trim();
    const systemPrompt = `You are NutriLoop AI, a world-class clinical nephrology, cardiology, and endocrinology diet assistant.
Provide empathetic, scientifically sound guidance grounded in KDIGO 2024, ADA 2024, and AHA DASH clinical protocols.
${vitalsSummary ? `Current Patient Vitals Context: ${vitalsSummary}` : ""}
Always advise consulting a qualified physician or registered dietitian for personalized medical prescriptions.`;

    // 1. If key starts with "AIzaSy" or appears to be a Google Gemini key
    if (key.startsWith("AIzaSy") || !key.startsWith("sk-")) {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`;
      const contents = [
        {
          role: "user",
          parts: [{ text: `${systemPrompt}\n\nHello, I am ready to consult you.` }],
        },
        ...history.map((m) => ({
          role: m.role === "user" ? "user" : "model",
          parts: [{ text: m.content }],
        })),
        {
          role: "user",
          parts: [{ text: message }],
        },
      ];

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contents }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Gemini API error (${response.status}): ${errText}`);
      }

      const resData = await response.json();
      const reply =
        resData?.candidates?.[0]?.content?.parts?.[0]?.text ||
        "I could not formulate a clinical recommendation at this time.";
      return reply;
    } else {
      // 2. OpenAI-compatible API
      const url = "https://api.openai.com/v1/chat/completions";
      const messages = [
        { role: "system", content: systemPrompt },
        ...history.map((m) => ({ role: m.role, content: m.content })),
        { role: "user", content: message },
      ];

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${key}`,
        },
        body: JSON.stringify({
          model: "gpt-4o-mini",
          messages,
          temperature: 0.3,
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`OpenAI API error (${response.status}): ${errText}`);
      }

      const resData = await response.json();
      return (
        resData?.choices?.[0]?.message?.content ||
        "I could not formulate a clinical recommendation at this time."
      );
    }
  }
}
