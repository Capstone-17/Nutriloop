import type { UserProfile } from "./auth-context";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type DiseaseType = "ckd" | "hypertension" | "diabetes";

export interface RiskReportResponse {
  disease: DiseaseType;
  risk_score: number;
  risk_level: "low" | "moderate" | "high";
  model_name: string;
  thresholds: Record<string, number>;
  report_text?: string;
  plan?: Record<string, number | string | string[]>;
  recommended_foods?: Array<Record<string, unknown>>;
}

const rawPayloads: Record<DiseaseType, Record<string, unknown>> = {
  ckd: {
    age_years: 56,
    sex: "female",
    body_mass_index: 27.4,
    diagnosed_diabetes: true,
    diagnosed_hypertension: true,
    systolic_bp_mmhg: 142,
    diastolic_bp_mmhg: 88,
    fasting_glucose_mg_dl: 132,
  },
  hypertension: {
    age_years: 63,
    sex: "male",
    education_level: 5,
    current_smoker: true,
    cigarettes_per_day: 10,
    prior_stroke: false,
    body_mass_index: 31.2,
    diagnosed_diabetes: true,
    systolic_bp_mmhg: 154,
    diastolic_bp_mmhg: 96,
    fasting_glucose_mg_dl: 140,
  },
  diabetes: {
    age_years: 58,
    sex: "male",
    body_mass_index: 30.1,
    current_smoker: false,
    diagnosed_hypertension: true,
    systolic_bp_mmhg: 146,
    diastolic_bp_mmhg: 90,
    fasting_glucose_mg_dl: 168,
  },
};

export async function fetchDashboardRiskSummary(profile?: UserProfile, disease: DiseaseType = "diabetes", userId?: string): Promise<RiskReportResponse> {
  const selectedProfile = profile ?? {
    age: 58,
    sex: "male" as const,
    weight: 86.5,
    height: 169.5,
    activityLevel: "light",
    selectedDiseases: ["diabetes"],
    healthMetrics: { glucose: 168, systolic: 146, diastolic: 90 },
  };
  const bmi = selectedProfile.weight / Math.pow(selectedProfile.height / 100, 2);
  const selectedDiseases = selectedProfile.selectedDiseases;
  const rawInputs: Record<string, unknown> = {
    age_years: selectedProfile.age,
    sex: selectedProfile.sex,
    body_mass_index: Number(bmi.toFixed(1)),
    current_smoker: false,
    diagnosed_diabetes: selectedDiseases.includes("diabetes"),
    diagnosed_hypertension: selectedDiseases.includes("hypertension"),
    systolic_bp_mmhg: selectedProfile.healthMetrics.systolic,
    diastolic_bp_mmhg: selectedProfile.healthMetrics.diastolic,
    fasting_glucose_mg_dl: selectedProfile.healthMetrics.glucose,
  };

  if (disease === "hypertension") {
    rawInputs.education_level = 5;
    rawInputs.cigarettes_per_day = 0;
    rawInputs.prior_stroke = false;
  }

  const response = await fetch(`${API_BASE_URL}/risk-report-raw`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      disease,
      raw_inputs: rawInputs,
      user_id: userId,
      profile: {
        age: selectedProfile.age,
        bmi,
        activity_level: selectedProfile.activityLevel,
      },
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`Unable to reach backend risk API: ${message || response.statusText}`);
  }

  return response.json() as Promise<RiskReportResponse>;
}

export async function predictRiskRaw(params: {
  disease: DiseaseType;
  raw_inputs: Record<string, unknown>;
  user_id?: string;
}): Promise<RiskReportResponse> {
  const response = await fetch(`${API_BASE_URL}/risk-report-raw`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      disease: params.disease,
      raw_inputs: params.raw_inputs,
      user_id: params.user_id,
      profile: {},
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`Unable to reach backend risk API: ${message || response.statusText}`);
  }

  return response.json() as Promise<RiskReportResponse>;
}
