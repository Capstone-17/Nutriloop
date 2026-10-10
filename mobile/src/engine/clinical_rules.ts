import { PatientVitals, DiseaseAssessment, MultiDiseaseAssessmentResult } from "../types/clinical";
import { formatDecimal, roundToDecimal } from "../utils/formatters";

export class ClinicalRulesEngine {
  /**
   * 2021 CKD-EPI Creatinine Equation (Without Race)
   * Recommended by KDIGO & NKF-ASN Task Force 2021
   */
  static calculateCkdEpiEgfr(sc: number, age: number, sex: "male" | "female"): number {
    if (sc <= 0) return 90.0;
    const isFemale = sex === "female";
    const k = isFemale ? 0.7 : 0.9;
    const alpha = isFemale ? -0.241 : -0.302;
    const sexFactor = isFemale ? 1.012 : 1.0;
    const ratio = sc / k;
    const exp = ratio < 1.0 ? alpha : -1.200;
    const val = 142.0 * Math.pow(ratio, exp) * Math.pow(0.9938, age) * sexFactor;
    return roundToDecimal(val, 2);
  }

  /**
   * Continuous KDIGO 2024 Clinical Staging for Chronic Kidney Disease
   */
  static evaluateCkd(vitals: PatientVitals): DiseaseAssessment {
    const isFemale = vitals.sex === "female";
    let egfr = vitals.egfrMlMin;
    if (!egfr || egfr <= 0) {
      egfr = this.calculateCkdEpiEgfr(vitals.serumCreatinineMgDl, vitals.ageYears, vitals.sex);
    }

    // Base KDIGO risk according to eGFR staging
    let baseRisk = 0.04;
    if (egfr >= 90.0) {
      baseRisk = 0.04 + Math.max(0.0, 100.0 - egfr) * 0.0004;
    } else if (egfr >= 60.0) {
      const frac = (90.0 - egfr) / 30.0;
      baseRisk = 0.045 + frac * 0.435;
    } else if (egfr >= 30.0) {
      const frac = (60.0 - egfr) / 30.0;
      baseRisk = 0.52 + frac * 0.32;
    } else {
      const frac = (30.0 - Math.max(8.0, egfr)) / 22.0;
      baseRisk = 0.85 + frac * 0.13;
    }

    // Renal hemodynamic pressure deltas
    let deltaBp = 0.0;
    if (vitals.systolicBpMmhg > 115.0) deltaBp += (vitals.systolicBpMmhg - 115.0) * 0.0018;
    if (vitals.diastolicBpMmhg > 75.0) deltaBp += (vitals.diastolicBpMmhg - 75.0) * 0.0014;

    // Glycemic microvascular stress
    let deltaGlyc = 0.0;
    if (vitals.fastingGlucoseMgDl > 85.0) deltaGlyc += (vitals.fastingGlucoseMgDl - 85.0) * 0.0015;
    if (vitals.hba1cPct > 5.2) deltaGlyc += (vitals.hba1cPct - 5.2) * 0.03;

    // Electrolytes
    let deltaLytes = 0.0;
    if (vitals.serumPotassiumMeqL > 5.0) deltaLytes += (vitals.serumPotassiumMeqL - 5.0) * 0.065;
    if (vitals.serumSodiumMeqL > 145.0) deltaLytes += (vitals.serumSodiumMeqL - 145.0) * 0.005;

    // Creatinine upper limit check
    let deltaSc = 0.0;
    const creatUpper = isFemale ? 1.0 : 1.2;
    if (vitals.serumCreatinineMgDl > creatUpper) {
      deltaSc += Math.min(0.30, (vitals.serumCreatinineMgDl - creatUpper) * 0.25);
    }

    const totalScore = Math.max(0.01, Math.min(0.99, baseRisk + deltaBp + deltaGlyc + deltaLytes + deltaSc));
    const riskLevel: "low" | "moderate" | "high" = totalScore >= 0.70 ? "high" : totalScore >= 0.40 ? "moderate" : "low";

    const drivers: string[] = [];
    const protective: string[] = [];
    if (egfr < 60) drivers.push(`Reduced filtration rate: eGFR ${egfr} mL/min`);
    else protective.push(`Optimal kidney filtration: eGFR ${egfr} mL/min`);

    if (vitals.serumCreatinineMgDl > creatUpper) drivers.push(`Elevated Serum Creatinine (${formatDecimal(vitals.serumCreatinineMgDl, 2)} mg/dL)`);
    if (vitals.serumPotassiumMeqL > 5.0) drivers.push(`Hyperkalemia (${formatDecimal(vitals.serumPotassiumMeqL, 2)} mEq/L) - Renal excretion risk`);
    if (vitals.systolicBpMmhg >= 130) drivers.push(`Renal vascular pressure (BP ${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)})`);

    return {
      disease: "ckd",
      diseaseName: "Chronic Kidney Disease",
      riskScore: roundToDecimal(totalScore, 2),
      riskLevel,
      riskPercentage: roundToDecimal(totalScore * 100, 2),
      primaryDrivers: drivers.length > 0 ? drivers : ["Mild age-related physiological decline"],
      protectiveFactors: protective,
      clinicalSummary: `KDIGO 2024: Estimated filtration is ${formatDecimal(egfr, 2)} mL/min (${riskLevel} risk tier). Potassium & sodium moderation recommended.`
    };
  }

  /**
   * Continuous AHA/ACC 2023 Blood Pressure Hemodynamic Evaluation
   */
  static evaluateHypertension(vitals: PatientVitals): DiseaseAssessment {
    let deltaBp = 0.0;
    if (vitals.systolicBpMmhg > 115.0) deltaBp += (vitals.systolicBpMmhg - 115.0) * 0.0055;
    if (vitals.diastolicBpMmhg > 75.0) deltaBp += (vitals.diastolicBpMmhg - 75.0) * 0.0038;

    let deltaBmi = 0.0;
    if (vitals.bodyMassIndex > 22.0) deltaBmi += (vitals.bodyMassIndex - 22.0) * 0.0050;

    let deltaAge = 0.0;
    if (vitals.ageYears > 35.0) deltaAge += (vitals.ageYears - 35.0) * 0.0012;

    let deltaSod = 0.0;
    if (vitals.serumSodiumMeqL > 140.0) deltaSod += (vitals.serumSodiumMeqL - 140.0) * 0.0040;

    const baseRisk = 0.05;
    const totalScore = Math.max(0.01, Math.min(0.99, baseRisk + deltaBp + deltaBmi + deltaAge + deltaSod));
    const riskLevel: "low" | "moderate" | "high" = totalScore >= 0.65 ? "high" : totalScore >= 0.38 ? "moderate" : "low";

    const drivers: string[] = [];
    const protective: string[] = [];
    if (vitals.systolicBpMmhg >= 140 || vitals.diastolicBpMmhg >= 90) {
      drivers.push(`Stage 2 Hypertension pressure (${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg)`);
    } else if (vitals.systolicBpMmhg >= 130 || vitals.diastolicBpMmhg >= 80) {
      drivers.push(`Stage 1 Pre-hypertensive pressure (${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg)`);
    } else {
      protective.push(`Normotensive baseline (${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg)`);
    }

    if (vitals.bodyMassIndex >= 25.0) drivers.push(`Elevated BMI (${formatDecimal(vitals.bodyMassIndex, 2)} kg/m²)`);
    else protective.push(`Healthy Body Mass Index (${formatDecimal(vitals.bodyMassIndex, 2)} kg/m²)`);

    return {
      disease: "hypertension",
      diseaseName: "Hypertension",
      riskScore: roundToDecimal(totalScore, 2),
      riskLevel,
      riskPercentage: roundToDecimal(totalScore * 100, 2),
      primaryDrivers: drivers.length > 0 ? drivers : ["Normotensive arterial pressure"],
      protectiveFactors: protective,
      clinicalSummary: `AHA/ACC: Blood pressure reading is ${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg (${riskLevel} risk tier). DASH sodium restriction recommended.`
    };
  }

  /**
   * Continuous ADA 2024 Glycemic & Insulin Resistance Evaluation
   */
  static evaluateDiabetes(vitals: PatientVitals): DiseaseAssessment {
    let deltaFbg = 0.0;
    if (vitals.fastingGlucoseMgDl > 95.0) {
      if (vitals.fastingGlucoseMgDl <= 125.0) {
        deltaFbg += (vitals.fastingGlucoseMgDl - 95.0) * 0.0070; // Impaired fasting glycemia
      } else {
        deltaFbg += (125.0 - 95.0) * 0.0070 + (vitals.fastingGlucoseMgDl - 125.0) * 0.0055; // Diagnostic diabetes
      }
    }

    let deltaHba1c = 0.0;
    if (vitals.hba1cPct > 5.4) {
      if (vitals.hba1cPct <= 6.4) {
        deltaHba1c += (vitals.hba1cPct - 5.4) * 0.14; // Prediabetic zone
      } else {
        deltaHba1c += (6.4 - 5.4) * 0.14 + (vitals.hba1cPct - 6.4) * 0.11; // Diabetic glycated hemoglobin
      }
    }

    let deltaBmi = 0.0;
    if (vitals.bodyMassIndex > 23.0) deltaBmi += (vitals.bodyMassIndex - 23.0) * 0.0045;

    const baseRisk = 0.04;
    const totalScore = Math.max(0.01, Math.min(0.99, baseRisk + deltaFbg + deltaHba1c + deltaBmi));
    const riskLevel: "low" | "moderate" | "high" = totalScore >= 0.65 ? "high" : totalScore >= 0.38 ? "moderate" : "low";

    const drivers: string[] = [];
    const protective: string[] = [];
    if (vitals.hba1cPct >= 6.5) drivers.push(`Diagnostic glycated hemoglobin: HbA1c ${formatDecimal(vitals.hba1cPct, 2)}%`);
    else if (vitals.hba1cPct >= 5.7) drivers.push(`Prediabetic glycated hemoglobin: HbA1c ${formatDecimal(vitals.hba1cPct, 2)}%`);
    else protective.push(`Optimal HbA1c (${formatDecimal(vitals.hba1cPct, 2)}%)`);

    if (vitals.fastingGlucoseMgDl >= 126) drivers.push(`Diagnostic fasting glucose (${formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL)`);
    else if (vitals.fastingGlucoseMgDl >= 100) drivers.push(`Impaired fasting glucose (${formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL)`);
    else protective.push(`Normal fasting blood sugar (${formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL)`);

    return {
      disease: "diabetes",
      diseaseName: "Type 2 Diabetes",
      riskScore: roundToDecimal(totalScore, 2),
      riskLevel,
      riskPercentage: roundToDecimal(totalScore * 100, 2),
      primaryDrivers: drivers.length > 0 ? drivers : ["Normoglycemic metabolic state"],
      protectiveFactors: protective,
      clinicalSummary: `ADA 2024: Fasting glucose is ${formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL and HbA1c is ${formatDecimal(vitals.hba1cPct, 2)}% (${riskLevel} risk tier). Glycemic index control recommended.`
    };
  }

  /**
   * Concurrently evaluates all 3 diseases & detects comorbid clinical conditions
   */
  static assessPatient(vitals: PatientVitals): MultiDiseaseAssessmentResult {
    const ckd = this.evaluateCkd(vitals);
    const htn = this.evaluateHypertension(vitals);
    const dm = this.evaluateDiabetes(vitals);

    const conditions: string[] = [];
    if (vitals.egfrMlMin < 60) {
      const stage = vitals.egfrMlMin < 30 ? "Stage 4-5 Severe" : "Stage 3";
      conditions.push(`Renal Impairment (${stage} CKD, eGFR ${formatDecimal(vitals.egfrMlMin, 2)} mL/min)`);
    } else if (ckd.riskLevel !== "low") {
      conditions.push("Chronic Kidney Disease Risk");
    }

    if (vitals.systolicBpMmhg >= 140 || vitals.diastolicBpMmhg >= 90) {
      conditions.push(`Stage 2 Hypertension (${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg)`);
    } else if (vitals.systolicBpMmhg >= 130 || vitals.diastolicBpMmhg >= 80) {
      conditions.push(`Stage 1 Hypertension (${Math.round(vitals.systolicBpMmhg)}/${Math.round(vitals.diastolicBpMmhg)} mmHg)`);
    }

    if (vitals.fastingGlucoseMgDl >= 126 || vitals.hba1cPct >= 6.5) {
      conditions.push("Type 2 Diabetes (Diagnostic Glycemia)");
    } else if (vitals.fastingGlucoseMgDl >= 100 || vitals.hba1cPct >= 5.7) {
      conditions.push("Prediabetes (Impaired Glucose Tolerance)");
    }

    if (vitals.serumPotassiumMeqL > 5.0) conditions.push(`Hyperkalemia (High Potassium: ${formatDecimal(vitals.serumPotassiumMeqL, 2)} mEq/L)`);
    if (vitals.serumPotassiumMeqL < 3.5) conditions.push(`Hypokalemia (Low Potassium: ${formatDecimal(vitals.serumPotassiumMeqL, 2)} mEq/L)`);
    if (vitals.serumSodiumMeqL > 145) conditions.push(`Hypernatremia (Sodium: ${formatDecimal(vitals.serumSodiumMeqL, 2)} mEq/L)`);
    if (vitals.serumSodiumMeqL < 135) conditions.push(`Hyponatremia (Sodium: ${formatDecimal(vitals.serumSodiumMeqL, 2)} mEq/L)`);

    return {
      timestamp: new Date().toISOString(),
      detectedConditions: conditions.length > 0 ? conditions : ["General Metabolic Health Maintenance"],
      assessments: {
        ckd,
        hypertension: htn,
        diabetes: dm
      },
      vitals
    };
  }

  /**
   * Intelligently parses unstructured clinical notes and doctor reports
   */
  static parseLabText(text: string): Partial<PatientVitals> {
    if (!text || !text.trim()) return {};
    const t = text.toLowerCase();
    const extracted: Partial<PatientVitals> = {};

    // 1. Blood Pressure: e.g. "140/90", "BP: 130 / 85 mmHg"
    const bpMatch = t.match(/(?:bp|blood\s*pressure)?(?:\s*\([^)]*\))?\s*[:=]?\s*(\d{2,3})\s*[/]\s*(\d{2,3})/);
    if (bpMatch) {
      const sbp = parseInt(bpMatch[1], 10);
      const dbp = parseInt(bpMatch[2], 10);
      if (sbp >= 60 && sbp <= 260 && dbp >= 35 && dbp <= 160) {
        extracted.systolicBpMmhg = sbp;
        extracted.diastolicBpMmhg = dbp;
      }
    }

    // 2. Fasting Blood Glucose: e.g. "FBG: 126", "fasting blood sugar 140"
    const fbgMatch = t.match(/(?:fasting\s*(?:blood\s*)?glucose|fasting\s*blood\s*sugar|fbg|fbs)[:=\s]+(\d{2,3}(?:\.\d+)?)/);
    if (fbgMatch) {
      const val = parseFloat(fbgMatch[1]);
      if (val >= 40 && val <= 450) extracted.fastingGlucoseMgDl = roundToDecimal(val, 2);
    }

    // 3. HbA1c: e.g. "HbA1c: 7.2%", "A1c 6.5"
    const a1cMatch = t.match(/(?:hba1c|a1c|glycated\s*hemoglobin)[:=\s]+(\d{1,2}(?:\.\d{1,2})?)/);
    if (a1cMatch) {
      const val = parseFloat(a1cMatch[1]);
      if (val >= 3.0 && val <= 20.0) extracted.hba1cPct = roundToDecimal(val, 2);
    }

    // 4. Serum Creatinine: e.g. "Creatinine: 1.4 mg/dL", "S. Creat 1.1"
    const crMatch = t.match(/(?:serum\s*creatinine|creatinine|s\.?\s*creat)[:=\s]+(\d{1,2}(?:\.\d{1,2})?)/);
    if (crMatch) {
      const val = parseFloat(crMatch[1]);
      if (val >= 0.1 && val <= 25.0) extracted.serumCreatinineMgDl = roundToDecimal(val, 2);
    }

    // 5. eGFR: e.g. "eGFR: 45 mL/min", "GFR 58"
    const egfrMatch = t.match(/(?:egfr|estimated\s*gfr|gfr)[:=\s]+(\d{1,3}(?:\.\d{1,2})?)/);
    if (egfrMatch) {
      const val = parseFloat(egfrMatch[1]);
      if (val >= 5 && val <= 160) extracted.egfrMlMin = roundToDecimal(val, 2);
    }

    // 6. Serum Potassium: e.g. "Potassium: 4.5", "K+ 4.8"
    const potMatch = t.match(/(?:serum\s*potassium|potassium|k\+?)[:=\s]+(\d{1,2}(?:\.\d{1,2})?)/);
    if (potMatch) {
      const val = parseFloat(potMatch[1]);
      if (val >= 2.0 && val <= 8.5) extracted.serumPotassiumMeqL = roundToDecimal(val, 2);
    }

    // 7. Serum Sodium: e.g. "Sodium: 139", "Na+ 141"
    const sodMatch = t.match(/(?:serum\s*sodium|sodium|na\+?)[:=\s]+(\d{2,3}(?:\.\d{1,2})?)/);
    if (sodMatch) {
      const val = parseFloat(sodMatch[1]);
      if (val >= 100 && val <= 180) extracted.serumSodiumMeqL = roundToDecimal(val, 2);
    }

    // 8. BMI: e.g. "BMI: 28.4 kg/m2"
    const bmiMatch = t.match(/(?:bmi|body\s*mass\s*index)[:=\s]+(\d{1,2}(?:\.\d{1,2})?)/);
    if (bmiMatch) {
      const val = parseFloat(bmiMatch[1]);
      if (val >= 10 && val <= 90) extracted.bodyMassIndex = roundToDecimal(val, 2);
    }

    // 9. Age
    const ageMatch = t.match(/(?:age[:=\s]+(\d{1,3})|(\d{1,3})\s*(?:years?\s*old|yo|yr|y\/o))/);
    if (ageMatch) {
      const val = parseInt(ageMatch[1] || ageMatch[2], 10);
      if (val >= 18 && val <= 100) extracted.ageYears = val;
    }

    // 10. Sex
    if (/\b(?:female|woman)\b/.test(t)) extracted.sex = "female";
    else if (/\b(?:male|man)\b/.test(t)) extracted.sex = "male";

    return extracted;
  }
}
