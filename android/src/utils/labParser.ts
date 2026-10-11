import { PatientVitals } from "../types/clinical";
import { roundToDecimal } from "./formatters";

/**
 * Client-side clinical lab report regex parser.
 * Extracts vital signs and biomarkers from pasted OCR / lab reports.
 */
export function parseLabReportText(text: string): Partial<PatientVitals> {
  const result: Partial<PatientVitals> = {};
  if (!text) return result;

  // 1. Blood Pressure: e.g. "BP: 135/85", "120/80 mmHg"
  const bpMatch = text.match(/(?:BP|blood\s*pressure)?[:\s]*(\d{2,3})\s*[\/|\\]\s*(\d{2,3})/i);
  if (bpMatch) {
    const sbp = parseInt(bpMatch[1], 10);
    const dbp = parseInt(bpMatch[2], 10);
    if (sbp >= 60 && sbp <= 260) result.systolicBpMmhg = sbp;
    if (dbp >= 40 && dbp <= 160) result.diastolicBpMmhg = dbp;
  }

  // 2. Fasting Blood Sugar / Glucose: e.g. "Glucose: 110 mg/dL", "FBS: 125"
  const glucMatch = text.match(/(?:fasting\s*glucose|glucose|fbs|fbg|blood\s*sugar)[:\s]*(\d{2,3}(?:\.\d+)?)/i);
  if (glucMatch) {
    const val = parseFloat(glucMatch[1]);
    if (val >= 40 && val <= 500) result.fastingGlucoseMgDl = roundToDecimal(val, 2);
  }

  // 3. HbA1c: e.g. "HbA1c: 6.5%", "Glycated Hemoglobin: 7.1"
  const a1cMatch = text.match(/(?:hba1c|a1c|glycated\s*h(?:a)?emoglobin)[:\s]*(\d{1,2}(?:\.\d+)?)/i);
  if (a1cMatch) {
    const val = parseFloat(a1cMatch[1]);
    if (val >= 3.0 && val <= 20.0) result.hba1cPct = roundToDecimal(val, 2);
  }

  // 4. Serum Creatinine: e.g. "Creatinine: 1.2 mg/dL", "s.creat: 0.9"
  const creatMatch = text.match(/(?:serum\s*creatinine|creatinine|creat|s\.cr)[:\s]*(\d{1,2}(?:\.\d+)?)/i);
  if (creatMatch) {
    const val = parseFloat(creatMatch[1]);
    if (val >= 0.2 && val <= 15.0) result.serumCreatinineMgDl = roundToDecimal(val, 2);
  }

  // 5. eGFR: e.g. "eGFR: 65 mL/min", "GFR: 82"
  const egfrMatch = text.match(/(?:egfr|gfr|estimated\s*gfr)[:\s]*(\d{1,3}(?:\.\d+)?)/i);
  if (egfrMatch) {
    const val = parseFloat(egfrMatch[1]);
    if (val >= 3 && val <= 160) result.egfrMlMin = roundToDecimal(val, 2);
  }

  // 6. Serum Potassium: e.g. "Potassium: 4.5 mEq/L", "K+: 5.1"
  const potMatch = text.match(/(?:serum\s*potassium|potassium|k\+?)[:\s]*(\d(?:\.\d+)?)/i);
  if (potMatch) {
    const val = parseFloat(potMatch[1]);
    if (val >= 1.5 && val <= 9.0) result.serumPotassiumMeqL = roundToDecimal(val, 2);
  }

  // 7. Serum Sodium: e.g. "Sodium: 138 mEq/L", "Na+: 142"
  const sodMatch = text.match(/(?:serum\s*sodium|sodium|na\+?)[:\s]*(\d{2,3}(?:\.\d+)?)/i);
  if (sodMatch) {
    const val = parseFloat(sodMatch[1]);
    if (val >= 100 && val <= 180) result.serumSodiumMeqL = roundToDecimal(val, 2);
  }

  // 8. Body Mass Index (BMI): e.g. "BMI: 26.4"
  const bmiMatch = text.match(/(?:body\s*mass\s*index|bmi)[:\s]*(\d{1,2}(?:\.\d+)?)/i);
  if (bmiMatch) {
    const val = parseFloat(bmiMatch[1]);
    if (val >= 10 && val <= 70) result.bodyMassIndex = roundToDecimal(val, 2);
  }

  return result;
}

/**
 * Standard CKD-EPI 2021 race-free equation for estimated glomerular filtration rate.
 */
export function calculateCkdEpiEgfr(
  serumCreatinine: number,
  age: number,
  sex: "male" | "female"
): number {
  if (!serumCreatinine || serumCreatinine <= 0) return 90;
  const isFemale = String(sex || "male").toLowerCase() === "female";
  const kappa = isFemale ? 0.7 : 0.9;
  const alpha = isFemale ? -0.241 : -0.302;
  const scr = serumCreatinine;
  const minVal = Math.min(scr / kappa, 1.0);
  const maxVal = Math.max(scr / kappa, 1.0);
  const femaleFactor = isFemale ? 1.012 : 1.0;
  const egfr =
    142.0 *
    Math.pow(minVal, alpha) *
    Math.pow(maxVal, -1.2) *
    Math.pow(0.9938, age) *
    femaleFactor;
  return roundToDecimal(Math.max(3.0, Math.min(egfr, 150.0)), 2);
}
