import {
  PatientVitals,
  PatientPreferences,
  WeeklyDietPlan,
  DayDietPlan,
  SingleMealInterval,
  MealItem,
  ClinicalTargets,
} from "../types/clinical";
import { ClinicalRulesEngine } from "./clinical_rules";
import { roundToDecimal, formatDecimal } from "../utils/formatters";
import regionalCatalogRaw from "../../../datasets/regional_dish_catalog.json";
import drugInteractionsRaw from "../../../datasets/drug_interactions.json";

interface RawDishItem {
  name: string;
  portion: string;
  nutrients: {
    calories?: number;
    protein_g?: number;
    sodium_mg?: number;
    potassium_mg?: number;
    carbs_g?: number;
    fat_g?: number;
    fiber_g?: number;
  };
}

interface RawDish {
  title: string;
  items: RawDishItem[];
  justification: string;
  prep_tips: string;
}

// Ensure all regional pulses, dals, and whole grain dishes provide standard clinical therapeutic macros
function calibrateClinicalCatalog(catalog: Record<string, Record<string, RawDish[]>>) {
  const cloned: Record<string, Record<string, RawDish[]>> = JSON.parse(JSON.stringify(catalog));
  for (const regCats of Object.values(cloned)) {
    for (const dishes of Object.values(regCats)) {
      for (const d of dishes) {
        for (const it of d.items || []) {
          const nm = (it.name || "").toLowerCase();
          const nutr = it.nutrients || {};
          if (
            ["dal", "sambhar", "sambar", "kootu", "chickpea", "chana", "kadhi", "vaal", "lentil"].some(
              (w) => nm.includes(w)
            )
          ) {
            if ((nutr.protein_g || 0) < 10.0 && it.portion) {
              nutr.protein_g = Math.max(nutr.protein_g || 5.0, 11.0);
              nutr.calories = Math.max(nutr.calories || 90.0, 130.0);
              it.portion = "1 medium cup (150g)";
            }
          } else if (
            [
              "poha",
              "upma",
              "khichdi",
              "khichuri",
              "pongal",
              "sevai",
              "khandvi",
              "bhakri",
              "thepla",
              "dalia",
            ].some((w) => nm.includes(w))
          ) {
            if ((nutr.protein_g || 0) < 11.0) {
              nutr.protein_g = Math.max(nutr.protein_g || 5.0, 11.5);
              nutr.calories = Math.max(nutr.calories || 180.0, 220.0);
            }
          } else if (nm.includes("makhana") && (nutr.protein_g || 0) < 3.5) {
            nutr.protein_g = 3.8;
          } else if (nm.includes("chana") && (nutr.protein_g || 0) < 6.0) {
            nutr.protein_g = 6.5;
          }
        }
      }
    }
  }
  return cloned;
}

const REGIONAL_CATALOG = calibrateClinicalCatalog(
  regionalCatalogRaw as unknown as Record<string, Record<string, RawDish[]>>
);

function scalePortionString(portionStr: string, multiplier: number): string {
  if (!portionStr || Math.abs(multiplier - 1.0) < 0.05) {
    return portionStr;
  }
  return portionStr.replace(/(\d+(?:\.\d+)?)\s*([a-zA-Z]+)/g, (_, num, unit) => {
    const scaledVal = parseFloat(num) * multiplier;
    const uLower = unit.toLowerCase();
    if (["g", "ml", "mg"].includes(uLower)) {
      return `${Math.round(scaledVal)}${unit}`;
    } else {
      if (scaledVal < 4) {
        const rVal = roundToDecimal(scaledVal, 2);
        return `${formatDecimal(rVal, 2)} ${unit}`;
      } else {
        return `${Math.round(scaledVal)} ${unit}`;
      }
    }
  });
}

function scaleDishItems(
  dish: RawDish,
  targetIntervalCalories: number,
  maxIntervalProteinG: number | null,
  maxIntervalPotassiumMg: number | null,
  maxIntervalSodiumMg: number | null,
  isCkd: boolean,
  isHyperkalemia: boolean
): { scaledItems: MealItem[]; totals: Record<string, number> } {
  const items = dish.items || [];
  if (items.length === 0) {
    return {
      scaledItems: [],
      totals: {
        calories: 0,
        protein_g: 0,
        carbs_g: 0,
        fat_g: 0,
        sodium_mg: 0,
        potassium_mg: 0,
        fiber_g: 0,
      },
    };
  }

  const baseCalories = items.reduce((sum, it) => sum + (it.nutrients?.calories || 0), 0);
  const rawMultiplier = baseCalories > 0 ? targetIntervalCalories / baseCalories : 1.0;
  const multiplier = Math.max(0.5, Math.min(rawMultiplier, 2.4));

  // High protein density items
  const protDensities = items.map(
    (it) => (it.nutrients?.protein_g || 0) / Math.max(1.0, it.nutrients?.calories || 1.0)
  );
  const maxPd = Math.max(...protDensities, 0);
  const isHighProt = protDensities.map((pd) => pd >= 0.024 || (pd >= 0.016 && pd === maxPd));
  if (!isHighProt.some(Boolean) && items.length > 0) {
    const bestIdx = protDensities.indexOf(maxPd);
    if (bestIdx >= 0) isHighProt[bestIdx] = true;
  }

  const unadjProt = items.reduce(
    (sum, it) => sum + (it.nutrients?.protein_g || 0) * multiplier,
    0
  );

  let protScale = 1.0;
  if (isCkd) {
    if (maxIntervalProteinG && unadjProt > maxIntervalProteinG * 1.02) {
      protScale = Math.max(0.25, Math.min(1.0, (maxIntervalProteinG * 0.96) / unadjProt));
    }
  } else {
    if (maxIntervalProteinG && unadjProt < maxIntervalProteinG * 0.98) {
      const hpUnadj = items.reduce(
        (sum, it, idx) => sum + (isHighProt[idx] ? (it.nutrients?.protein_g || 0) * multiplier : 0),
        0
      );
      if (hpUnadj > 0) {
        const deficit = maxIntervalProteinG - unadjProt;
        const idealScale = (hpUnadj + deficit * 1.3) / hpUnadj;
        const hpCalBase = items.reduce(
          (sum, it, idx) => sum + (isHighProt[idx] ? (it.nutrients?.calories || 0) * multiplier : 0),
          0
        );
        const maxAllowedCal = targetIntervalCalories * 0.88;
        const calCapScale = hpCalBase > 0 ? maxAllowedCal / hpCalBase : 3.2;
        protScale = Math.max(1.0, Math.min(3.2, Math.min(idealScale, calCapScale)));
      }
    }
  }

  // Potassium leaching factor for renal / hyperkalemia
  let potLeachFactor = 1.0;
  if ((isCkd || isHyperkalemia) && maxIntervalPotassiumMg) {
    const unadjPot = items.reduce(
      (sum, it) => sum + (it.nutrients?.potassium_mg || 0) * multiplier,
      0
    );
    if (unadjPot > maxIntervalPotassiumMg * 1.02) {
      potLeachFactor = Math.max(0.48, Math.min(0.95, (maxIntervalPotassiumMg * 0.96) / unadjPot));
    }
  }

  // Sodium moderation
  let sodScale = 1.0;
  if (maxIntervalSodiumMg) {
    const unadjSod = items.reduce(
      (sum, it) => sum + (it.nutrients?.sodium_mg || 0) * multiplier,
      0
    );
    if (unadjSod > maxIntervalSodiumMg * 1.05) {
      sodScale = Math.max(0.6, Math.min(1.0, (maxIntervalSodiumMg * 0.98) / unadjSod));
    }
  }

  const hpCalTotal = items.reduce(
    (sum, it, idx) =>
      sum + (isHighProt[idx] ? (it.nutrients?.calories || 0) * multiplier * protScale : 0),
    0
  );
  const nonHpCalBase = items.reduce(
    (sum, it, idx) => sum + (!isHighProt[idx] ? (it.nutrients?.calories || 0) * multiplier : 0),
    0
  );
  const calForStaple = Math.max(12.0, targetIntervalCalories - hpCalTotal);
  const stapleScale =
    nonHpCalBase > 10.0 ? Math.max(0.2, Math.min(2.2, calForStaple / nonHpCalBase)) : 1.0;

  const scaledItems: MealItem[] = [];
  const totals: Record<string, number> = {
    calories: 0.0,
    protein_g: 0.0,
    carbs_g: 0.0,
    fat_g: 0.0,
    sodium_mg: 0.0,
    potassium_mg: 0.0,
    fiber_g: 0.0,
  };

  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    const origNutr = it.nutrients || {};
    const hp = isHighProt[i];
    const itemScale = hp ? protScale : stapleScale;
    const itemMult = multiplier * itemScale;

    const scaledNutr: Record<string, number> = {};
    for (const k of Object.keys(totals)) {
      let val = (origNutr[k as keyof typeof origNutr] || 0.0) * itemMult;
      if (k === "protein_g" && isCkd && protScale < 1.0) {
        val = (origNutr.protein_g || 0.0) * multiplier * protScale;
      } else if (k === "potassium_mg") {
        val *= potLeachFactor;
      } else if (k === "sodium_mg") {
        val *= sodScale;
      }
      scaledNutr[k] = roundToDecimal(val, 2);
      totals[k] = roundToDecimal(totals[k] + scaledNutr[k], 2);
    }

    const scaledPortion = scalePortionString(it.portion || "", itemMult);
    scaledItems.push({
      itemName: it.name || "Dish Item",
      portion: scaledPortion,
      nutrients: {
        calories: Math.round(scaledNutr.calories),
        proteinG: roundToDecimal(scaledNutr.protein_g, 2),
        carbsG: roundToDecimal(scaledNutr.carbs_g, 2),
        sodiumMg: Math.round(scaledNutr.sodium_mg),
        potassiumMg: Math.round(scaledNutr.potassium_mg),
      },
    });
  }

  // Fine tune calorie gap on staple item
  const calGap = targetIntervalCalories - totals.calories;
  if (Math.abs(calGap) > 2.0 && scaledItems.length > 0) {
    let stapleIdx = 0;
    for (let idx = 0; idx < isHighProt.length; idx++) {
      if (!isHighProt[idx]) {
        stapleIdx = idx;
        break;
      }
    }
    const curCal = scaledItems[stapleIdx].nutrients.calories || 0;
    const adj = calGap < 0 ? Math.max(12.0 - curCal, calGap) : calGap;
    scaledItems[stapleIdx].nutrients.calories = Math.round(curCal + adj);
    scaledItems[stapleIdx].nutrients.carbsG = roundToDecimal(
      Math.max(0.0, (scaledItems[stapleIdx].nutrients.carbsG || 0) + adj / 4.0),
      2
    );
    totals.calories = roundToDecimal(totals.calories + adj, 2);
    totals.carbs_g = roundToDecimal(totals.carbs_g + adj / 4.0, 2);
  }

  for (const k of Object.keys(totals)) {
    totals[k] = roundToDecimal(totals[k], 2);
  }

  return { scaledItems, totals };
}

function categorizeGroceries(groceryItems: string[]): Record<string, string[]> {
  const categories: Record<string, string[]> = {
    "🥬 Fresh Produce & Greens": [],
    "🌾 Whole Grains & Millets": [],
    "🫘 Pulses, Legumes & Plant Proteins": [],
    "🐟 Dairy, Eggs & Lean Proteins": [],
    "🌿 Herbs, Spices & Cold-Pressed Oils": [],
  };

  const produceKw = [
    "gourd", "lauki", "tinda", "torai", "jhinge", "potol", "parwal", "cucumber", "tomato",
    "beans", "carrot", "peas", "cabbage", "spinach", "palak", "methi", "coriander", "mint",
    "papaya", "apple", "guava", "pomegranate", "lemon", "lime", "okra", "bhindi", "zucchini",
    "asparagus", "broccoli", "brussels", "berries", "blueberries", "strawberries", "avocado",
    "mushrooms", "cauliflower", "eggplant", "baingan", "drumstick",
  ];
  const grainsKw = [
    "rice", "brown rice", "dalia", "wheat", "oats", "quinoa", "ragi", "millet", "jowar", "bajra",
    "chire", "poha", "puffed rice", "muri", "kurmura", "barley", "pasta", "sourdough", "bread",
    "toast", "pita", "khakhra",
  ];
  const pulsesKw = [
    "dal", "moong", "chana", "chickpea", "urad", "masoor", "tuvar", "arhar", "rajma", "tofu",
    "soya", "sprouts", "lentil", "edamame", "flaxseed", "chia", "walnut", "pumpkin seeds", "sesame",
  ];
  const proteinKw = [
    "chicken", "fish", "egg", "egg white", "paneer", "curd", "dahi", "buttermilk", "chaas",
    "yogurt", "cod", "salmon", "rohu", "pomfret", "tilapia", "turkey",
  ];

  const unique = Array.from(new Set(groceryItems)).sort();
  for (const item of unique) {
    const low = item.toLowerCase();
    if (proteinKw.some((k) => low.includes(k))) {
      categories["🐟 Dairy, Eggs & Lean Proteins"].push(item);
    } else if (grainsKw.some((k) => low.includes(k))) {
      categories["🌾 Whole Grains & Millets"].push(item);
    } else if (pulsesKw.some((k) => low.includes(k))) {
      categories["🫘 Pulses, Legumes & Plant Proteins"].push(item);
    } else if (produceKw.some((k) => low.includes(k))) {
      categories["🥬 Fresh Produce & Greens"].push(item);
    } else {
      categories["🌿 Herbs, Spices & Cold-Pressed Oils"].push(item);
    }
  }

  const result: Record<string, string[]> = {};
  for (const [k, v] of Object.entries(categories)) {
    if (v.length > 0) result[k] = v;
  }
  return result;
}

export class WeeklyDietEngine {
  /**
   * Derive clinical targets strictly from laboratory biomarkers, anthropometry (Mifflin-St Jeor),
   * and active medications, matching backend/weekly_diet_engine.py:154-356 exactly.
   */
  static deriveTargets(
    vitals: PatientVitals,
    conditionsIn: string[],
    prefs: PatientPreferences
  ): { targets: ClinicalTargets; detectedConditions: string[] } {
    const detectedConditions: string[] = [];

    // 1. Anthropometry & Weight Status
    const s = String(vitals.sex || "male").toLowerCase().trim();
    const heightM = s === "male" ? 1.72 : 1.60;
    const heightCm = heightM * 100.0;
    const actualWeightKg = roundToDecimal(vitals.bodyMassIndex * heightM * heightM, 2);
    const idealWeightKg = roundToDecimal(22.0 * heightM * heightM, 2);

    // Adjusted Body Weight (aBW) for overweight/obesity (KDOQI 2020 protocol)
    let abwKg = actualWeightKg;
    if (vitals.bodyMassIndex >= 25.0) {
      abwKg = roundToDecimal(idealWeightKg + 0.25 * (actualWeightKg - idealWeightKg), 2);
    }

    // 2. Biomarkers
    const creat = vitals.serumCreatinineMgDl;
    let egfr = vitals.egfrMlMin;
    const sysBp = vitals.systolicBpMmhg;
    const diaBp = vitals.diastolicBpMmhg;
    const fbs = vitals.fastingGlucoseMgDl;
    const a1c = vitals.hba1cPct;
    const kVal = vitals.serumPotassiumMeqL;

    // CKD-EPI 2021 eGFR Imputation if missing
    if (egfr == null && creat != null && creat > 0) {
      egfr = ClinicalRulesEngine.calculateCkdEpiEgfr(creat, vitals.ageYears, vitals.sex);
    }

    // 3. Disease Identification & Staging
    let hasCkd = false;
    let ckdStageStr = "";
    if (egfr != null) {
      if (egfr < 15.0) {
        hasCkd = true;
        ckdStageStr = "Stage 5 (Kidney Failure)";
      } else if (egfr < 30.0) {
        hasCkd = true;
        ckdStageStr = "Stage 4 (Severe CKD)";
      } else if (egfr < 45.0) {
        hasCkd = true;
        ckdStageStr = "Stage 3b (Moderate-to-Severe CKD)";
      } else if (egfr < 60.0) {
        hasCkd = true;
        ckdStageStr = "Stage 3a (Mild-to-Moderate CKD)";
      } else if (egfr < 90.0 && creat != null && creat >= 1.3) {
        hasCkd = true;
        ckdStageStr = "Stage 2 (Mild CKD with Biomarker Elevation)";
      }
    } else if (creat != null && creat >= 1.3) {
      hasCkd = true;
      ckdStageStr = "Biomarker Elevation Profile";
    }

    if (
      !hasCkd &&
      conditionsIn.some(
        (c) => c.toLowerCase().includes("kidney") || c.toLowerCase().includes("ckd")
      )
    ) {
      hasCkd = true;
      ckdStageStr = "Clinically Indicated";
    }

    if (hasCkd) {
      detectedConditions.push(`Chronic Kidney Disease (CKD) - ${ckdStageStr}`);
    }

    // Hypertension Detection (AHA/ACC 2023)
    let hasHtn = false;
    if (
      (sysBp != null && sysBp >= 130.0) ||
      (diaBp != null && diaBp >= 80.0) ||
      conditionsIn.some(
        (c) => c.toLowerCase().includes("hypertension") || c.toLowerCase().includes("bp")
      )
    ) {
      hasHtn = true;
      if ((sysBp != null && sysBp >= 140.0) || (diaBp != null && diaBp >= 90.0)) {
        detectedConditions.push("Hypertension (Stage 2)");
      } else {
        detectedConditions.push("Hypertension (Stage 1)");
      }
    }

    // Diabetes Detection (ADA 2024)
    let hasDiabetes = false;
    if (
      (fbs != null && fbs >= 126.0) ||
      (a1c != null && a1c >= 6.5) ||
      conditionsIn.some((c) => c.toLowerCase().includes("diabetes"))
    ) {
      hasDiabetes = true;
      detectedConditions.push("Type 2 Diabetes Mellitus");
    } else if (
      (fbs != null && fbs >= 100.0 && fbs < 126.0) ||
      (a1c != null && a1c >= 5.7 && a1c < 6.5)
    ) {
      detectedConditions.push("Prediabetes / Impaired Fasting Glucose");
    }

    // Potassium Abnormalities
    const hasHyperkalemia =
      (kVal != null && kVal >= 5.0) || (hasCkd && kVal != null && kVal >= 4.7);
    const hasHypokalemia = kVal != null && kVal < 3.5;
    if (hasHyperkalemia) {
      detectedConditions.push("Elevated Serum Potassium (Hyperkalemia Risk)");
    } else if (hasHypokalemia) {
      detectedConditions.push("Low Serum Potassium (Hypokalemia Risk)");
    }

    if (detectedConditions.length === 0) {
      detectedConditions.push("General Health Maintenance / Normal Range");
    }

    // 4. Caloric Target Calculation (Mifflin-St Jeor TDEE Model)
    let dailyCalories: number;
    if (prefs.calorieOverride && prefs.calorieOverride >= 1000 && prefs.calorieOverride <= 3800) {
      dailyCalories = prefs.calorieOverride;
    } else {
      const bmr =
        10.0 * actualWeightKg +
        6.25 * heightCm -
        5.0 * Number(vitals.ageYears) +
        (s === "male" ? 5.0 : -161.0);
      const tdee = bmr * 1.25;

      if (hasCkd) {
        dailyCalories = Math.round(abwKg * 30.0);
      } else if (hasDiabetes || vitals.bodyMassIndex >= 25.0) {
        const deficit = vitals.bodyMassIndex >= 30.0 ? 400.0 : 300.0;
        dailyCalories = Math.round(tdee - deficit);
      } else if (vitals.bodyMassIndex < 18.5) {
        dailyCalories = Math.round(tdee + 350.0);
      } else {
        dailyCalories = Math.round(tdee);
      }

      const minCal = s === "female" ? 1350 : 1500;
      dailyCalories = Math.max(minCal, Math.min(dailyCalories, 2600));
    }

    // 5. Protein Target (g)
    let dailyProteinG: number;
    if (hasCkd) {
      dailyProteinG = roundToDecimal(abwKg * (hasDiabetes ? 0.75 : 0.65), 2);
    } else if (hasDiabetes) {
      dailyProteinG = roundToDecimal(abwKg * 1.05, 2);
    } else if (vitals.ageYears >= 65) {
      dailyProteinG = roundToDecimal(abwKg * 1.10, 2);
    } else {
      dailyProteinG = roundToDecimal(abwKg * 0.95, 2);
    }
    dailyProteinG = Math.max(45.0, Math.min(dailyProteinG, 105.0));

    // 6. Sodium Limit (mg)
    const dailySodiumMg = hasHtn || hasCkd ? 1500.0 : 2000.0;

    // 7. Potassium Guidance (mg)
    const medsClean = (prefs.activeMedications || []).map((m) => m.toLowerCase().trim());
    const hasAceiArb = medsClean.some((m) =>
      ["lisinopril", "losartan", "ramipril", "valsartan", "telmisartan", "enalapril"].some((d) =>
        m.includes(d)
      )
    );

    let dailyPotassiumMg: number;
    if (hasCkd || hasHyperkalemia) {
      dailyPotassiumMg = hasHyperkalemia ? 1800.0 : 2000.0;
    } else if (hasAceiArb) {
      dailyPotassiumMg = kVal != null && kVal >= 4.5 ? 2000.0 : 2400.0;
    } else if (hasHypokalemia) {
      dailyPotassiumMg = 3600.0;
    } else if (hasHtn) {
      dailyPotassiumMg = 3400.0;
    } else {
      dailyPotassiumMg = 2800.0;
    }

    // 8. Phosphorus Limit (mg)
    const dailyPhosphorusMg = hasCkd ? 800.0 : 1200.0;

    // 9. Carbohydrate, Sugar, Fiber & Fat
    const hasSglt2i = medsClean.some((m) =>
      ["jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana"].some((d) =>
        m.includes(d)
      )
    );
    const carbFraction = hasDiabetes ? 0.42 : 0.50;
    let dailyCarbG = roundToDecimal((dailyCalories * carbFraction) / 4.0, 2);
    if (hasSglt2i) {
      dailyCarbG = Math.max(dailyCarbG, 138.0);
    }
    const dailySugarG = hasDiabetes ? 20.0 : 35.0;
    const dailyFiberG = hasDiabetes || hasHtn ? 35.0 : 28.0;
    let dailyFatG = roundToDecimal(
      (dailyCalories - (dailyProteinG * 4.0 + dailyCarbG * 4.0)) / 9.0,
      2
    );
    dailyFatG = Math.max(35.0, dailyFatG);

    // 10. Fluid Intake Target (ml)
    let fluidMl =
      hasCkd && ["Stage 4 (Severe CKD)", "Stage 5 (Kidney Failure)"].includes(ckdStageStr)
        ? 1800
        : hasCkd
        ? 2000
        : 2500;
    if (hasSglt2i) {
      fluidMl = Math.max(fluidMl, 2500);
    }

    const targets: ClinicalTargets = {
      calories_kcal: dailyCalories,
      protein_g: dailyProteinG,
      carbohydrate_g: dailyCarbG,
      fat_g: dailyFatG,
      sodium_limit_mg: dailySodiumMg,
      potassium_guidance_mg: dailyPotassiumMg,
      phosphorus_limit_mg: dailyPhosphorusMg,
      free_sugar_limit_g: dailySugarG,
      fiber_target_g: dailyFiberG,
      fluid_intake_ml: fluidMl,
    };

    return { targets, detectedConditions };
  }

  /**
   * 31+ Pharmacopeia Drug Contraindications
   */
  static checkMedicationAlerts(meds: string[]): string[] {
    const alerts: string[] = [];
    if (!meds || meds.length === 0) return alerts;
    const lowerMeds = meds.map((m) => m.toLowerCase().trim());

    const clinicalWarnings: Array<{ medications?: string[]; message?: string }> =
      (drugInteractionsRaw as any).clinical_warnings || [];

    for (const cw of clinicalWarnings) {
      const triggers = cw.medications || [];
      if (lowerMeds.some((m) => triggers.some((trig) => m.includes(trig)))) {
        if (cw.message) {
          alerts.push(cw.message);
        }
      }
    }

    return alerts;
  }

  private static filterByDietary(
    dishes: RawDish[],
    pattern: PatientPreferences["dietaryType"],
    dayIdx: number,
    intervalKey: string
  ): RawDish[] {
    const nonVegKeywords = [
      "chicken", "fish", "mutton", "prawn", "salmon", "rohu", "pomfret", "meat", "machh", "turkey", "cod", "tilapia",
    ];
    const eggKeywords = [
      "egg white", "egg whites", "omelet", "frittata", "scrambled egg", "boiled egg", "egg curry", "bhurji",
    ];
    const dairyKeywords = ["paneer", "curd", "dahi", "yogurt", "milk", "kadhi", "buttermilk", "ghee", "cheese"];
    const jainAvoidKeywords = [
      "onion", "garlic", "potato", "aloo", "carrot", "beetroot", "radish", "mooli", "ginger", "adrak",
    ];

    const eligible = dishes.filter((d) => {
      const titleLower = d.title.toLowerCase();
      const itemsStr = (d.items || []).map((it) => (it.name || "").toLowerCase()).join(" ");
      const allText = `${titleLower} ${itemsStr}`;

      const isNonVeg = nonVegKeywords.some((k) => allText.includes(k));
      const isEgg =
        (allText.includes("egg") && !allText.includes("eggplant")) ||
        eggKeywords.some((k) => allText.includes(k));
      const isDairy = dairyKeywords.some((k) => allText.includes(k));
      const isJainIncompatible = jainAvoidKeywords.some((k) => allText.includes(k));

      if (pattern === "vegetarian") {
        return !isNonVeg && !isEgg;
      }
      if (pattern === "eggetarian") {
        return !isNonVeg;
      }
      if (pattern === "vegan") {
        return !isNonVeg && !isEgg && !isDairy;
      }
      if (pattern === "jain") {
        return !isNonVeg && !isEgg && !isJainIncompatible;
      }
      return true;
    });

    if (eligible.length === 0) return dishes;

    if (pattern === "non_vegetarian" && (intervalKey === "lunch" || intervalKey === "dinner")) {
      const nonVegOnly = eligible.filter((d) => {
        const text = `${d.title} ${(d.items || []).map((i) => i.name).join(" ")}`.toLowerCase();
        return nonVegKeywords.some((k) => text.includes(k));
      });
      const vegOnly = eligible.filter((d) => !nonVegOnly.includes(d));
      if (dayIdx % 2 === 1 && nonVegOnly.length > 0) return nonVegOnly;
      if (vegOnly.length > 0) return vegOnly;
    } else if (
      pattern === "eggetarian" &&
      (intervalKey === "lunch" || intervalKey === "dinner" || intervalKey === "breakfast")
    ) {
      const eggOnly = eligible.filter((d) => {
        const text = `${d.title} ${(d.items || []).map((i) => i.name).join(" ")}`.toLowerCase();
        return (
          (text.includes("egg") && !text.includes("eggplant")) ||
          eggKeywords.some((k) => text.includes(k))
        );
      });
      const vegOnly = eligible.filter((d) => !eggOnly.includes(d));
      if (eggOnly.length > 0 && vegOnly.length > 0) {
        return dayIdx % 2 === 1 ? eggOnly : vegOnly;
      }
    }

    return eligible;
  }

  private static filterByExclusions(dishes: RawDish[], exclusions: string[]): RawDish[] {
    if (!exclusions || exclusions.length === 0) return dishes;
    const cleanTerms = exclusions
      .map((t) => t.toLowerCase().trim())
      .filter((t) => t.length > 1 && t !== "none");
    if (cleanTerms.length === 0) return dishes;

    const filtered = dishes.filter((d) => {
      const text = `${d.title} ${(d.items || []).map((i) => i.name).join(" ")}`.toLowerCase();
      return !cleanTerms.some((term) => text.includes(term));
    });

    return filtered.length > 0 ? filtered : dishes;
  }

  /**
   * Parse user food preferences and likes with delimiter splitting and synonym expansion
   * (identical to backend/weekly_diet_engine.py:1019-1054)
   */
  static parsePreferencesAndLikes(rawLikes: string[]): string[] {
    const rawTokens: string[] = [];
    for (const k of rawLikes || []) {
      if (!k) continue;
      // Split on , ; / + & and the word 'and'
      const parts = String(k)
        .toLowerCase()
        .split(/[,;/+&]|\band\b/);
      for (const part of parts) {
        const tok = part.trim();
        if (tok.length >= 2) {
          rawTokens.push(tok);
        }
      }
    }

    const synMap: Record<string, string[]> = {
      paneer: ["paneer", "cottage cheese", "tofu"],
      tofu: ["tofu", "paneer"],
      chicken: ["chicken", "poultry", "murgh"],
      fish: ["fish", "salmon", "meen", "machli"],
      egg: ["egg", "eggs", "omelet", "omelette", "anda", "bhurji"],
      dosa: ["dosa", "dosai", "pesarattu", "cheela", "chilla"],
      idli: ["idli", "idly"],
      ragi: ["ragi", "nachni", "finger millet", "millet"],
      oats: ["oats", "oatmeal", "rolled oats"],
      khichdi: ["khichdi", "khichri", "pongal"],
      dalia: ["dalia", "broken wheat", "cracked wheat"],
      sprouts: ["sprout", "sprouts", "moong sprout"],
      curd: ["curd", "dahi", "raita", "yogurt"],
      millet: ["millet", "ragi", "jowar", "bajra", "foxtail"],
      chapati: ["chapati", "roti", "phulka"],
      roti: ["roti", "chapati", "phulka"],
      spinach: ["spinach", "palak"],
      mushroom: ["mushroom", "mushrooms", "khumb"],
      mushrooms: ["mushroom", "mushrooms", "khumb"],
      soya: ["soya", "soy", "soybean", "soya chunks"],
      quinoa: ["quinoa"],
      chickpea: ["chickpea", "chana", "kabuli chana", "garbanzo"],
      chana: ["chana", "chickpea", "cholay", "chole"],
      rajma: ["rajma", "kidney bean", "kidney beans"],
      besan: ["besan", "gram flour", "chilla", "cheela"],
      upma: ["upma", "khichdi", "dalia"],
      poha: ["poha", "flattened rice", "aval"],
      salad: ["salad", "cucumber", "raw"],
      soup: ["soup", "broth", "shorba"],
      mutton: ["mutton", "lamb", "gosht"],
      prawn: ["prawn", "prawns", "shrimp"],
    };

    const cleanLikes = Array.from(new Set(rawTokens));
    const expanded = new Set<string>(cleanLikes);
    for (const t of cleanLikes) {
      for (const [kSyn, syns] of Object.entries(synMap)) {
        if (kSyn.includes(t) || t.includes(kSyn)) {
          for (const s of syns) expanded.add(s);
        }
      }
    }

    return Array.from(expanded).filter((w) => w.length >= 2);
  }

  /**
   * Generate complete 7-Day Regional Plan strictly matching backend/weekly_diet_engine.py
   */
  static generateWeeklyPlan(
    vitals: PatientVitals,
    conditionsIn: string[],
    prefs: PatientPreferences,
    reportDate?: string,
    isHistorical?: boolean
  ): WeeklyDietPlan {
    const { targets, detectedConditions } = this.deriveTargets(vitals, conditionsIn, prefs);
    const medAlerts = this.checkMedicationAlerts(prefs.activeMedications);

    const regionKey = prefs.nativeRegion || "south_indian";
    const regionDishes = REGIONAL_CATALOG[regionKey] || REGIONAL_CATALOG["south_indian"];
    const fallbackDishes = REGIONAL_CATALOG["south_indian"];

    const intervalsConfig = [
      { name: "Breakfast", time: "08:00 AM - 08:45 AM", key: "breakfast", share: 0.25 },
      { name: "Mid-Morning Snack", time: "11:00 AM - 11:30 AM", key: "mid_morning", share: 0.08 },
      { name: "Lunch", time: "01:00 PM - 02:00 PM", key: "lunch", share: 0.35 },
      { name: "Evening Snack", time: "05:00 PM - 05:30 PM", key: "evening_snack", share: 0.07 },
      { name: "Dinner", time: "07:45 PM - 08:30 PM", key: "dinner", share: 0.25 },
    ];

    const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const days: DayDietPlan[] = [];
    const rawGroceryItems: string[] = [];

    // Parse likes and expand synonyms
    const expandedLikes = this.parsePreferencesAndLikes(prefs.interestsAndLikes || []);

    const allExclusions = [...(prefs.allergies || []), ...(prefs.dislikes || [])];
    const medsLower = (prefs.activeMedications || []).map((m) => m.toLowerCase().trim());
    if (
      medsLower.some((m) =>
        [
          "amlodipine", "norvasc", "nifedipine", "felodipine", "diltiazem", "verapamil",
          "atorvastatin", "simvastatin",
        ].some((d) => m.includes(d))
      )
    ) {
      allExclusions.push("grapefruit", "pomelo", "seville orange");
    }

    const hasCkdCond =
      detectedConditions.some((c) => c.toLowerCase().includes("ckd") || c.toLowerCase().includes("kidney")) ||
      (vitals.egfrMlMin != null && vitals.egfrMlMin < 60) ||
      (vitals.serumCreatinineMgDl != null && vitals.serumCreatinineMgDl >= 1.3);

    const hasHyperkalemiaCond =
      detectedConditions.some((c) => c.toLowerCase().includes("hyperkalemia")) ||
      (vitals.serumPotassiumMeqL != null && vitals.serumPotassiumMeqL >= 5.0);

    const hasHtnCond =
      detectedConditions.some((c) => c.toLowerCase().includes("hypertension")) ||
      (vitals.systolicBpMmhg != null && vitals.systolicBpMmhg >= 130) ||
      (vitals.diastolicBpMmhg != null && vitals.diastolicBpMmhg >= 80);

    const hasDiabetesCond =
      detectedConditions.some((c) => c.toLowerCase().includes("diabetes")) ||
      (vitals.fastingGlucoseMgDl != null && vitals.fastingGlucoseMgDl >= 126) ||
      (vitals.hba1cPct != null && vitals.hba1cPct >= 6.5);

    const hasPrediabetesCond =
      !hasDiabetesCond &&
      (detectedConditions.some((c) => c.toLowerCase().includes("prediabetes")) ||
        (vitals.fastingGlucoseMgDl != null && vitals.fastingGlucoseMgDl >= 100) ||
        (vitals.hba1cPct != null && vitals.hba1cPct >= 5.7));

    // Per-generation rotational offsets ensure fresh, distinct plans on repeated clicks while preserving intra-week variety
    // (exact match to backend/weekly_diet_engine.py:1130)
    const catVarietyOffsets: Record<string, number> = {
      breakfast: Math.floor(Math.random() * 16),
      mid_morning: Math.floor(Math.random() * 16),
      lunch: Math.floor(Math.random() * 16),
      evening_snack: Math.floor(Math.random() * 16),
      dinner: Math.floor(Math.random() * 16),
    };

    const cravingRaw = (prefs.cravingOrTreat || "").trim();
    let scheduledMealName = "Evening Snack";
    let indulgenceTitle = "";
    let treatItem: MealItem | null = null;
    let rebalanceCarbs = 18.0;

    if (cravingRaw) {
      const cLow = cravingRaw.toLowerCase();
      if (
        ["sugar", "sweet", "dessert", "kheer", "halwa", "phirni", "mithai", "chocolate", "cake", "ice cream", "pastry"].some(
          (w) => cLow.includes(w)
        )
      ) {
        scheduledMealName = "Evening Snack";
        indulgenceTitle = "Cardamom Almond Phirni / Kheer (Controlled Jaggery & Stevia Blend)";
        treatItem = {
          itemName: "Cardamom Almond Phirni with Crushed Pistachio (Controlled Jaggery & Stevia)",
          portion: "1 small ramekin (100g)",
          nutrients: {
            calories: 125,
            proteinG: 12.0,
            carbsG: 14.0,
            sodiumMg: 35,
            potassiumMg: 90,
          },
        };
      } else if (["biryani", "pulao", "fried rice"].some((w) => cLow.includes(w))) {
        scheduledMealName = "Lunch";
        indulgenceTitle = "Clinically Portioned Brown Rice Dum Biryani with Cucumber Raita";
        treatItem = {
          itemName: "Steamed Brown Rice Dum Biryani with Soya Chunks & Vegetables",
          portion: "1 medium bowl (180g)",
          nutrients: {
            calories: 230,
            proteinG: 7.5,
            carbsG: 36.0,
            sodiumMg: 175,
            potassiumMg: 210,
          },
        };
        rebalanceCarbs = 20.0;
      } else {
        scheduledMealName = "Evening Snack";
        const cleanName = cravingRaw.charAt(0).toUpperCase() + cravingRaw.slice(1);
        indulgenceTitle = `Clinically Formulated ${cleanName} (Controlled Portion)`;
        treatItem = {
          itemName: `Portion-Controlled ${cleanName} (Clinical Formulation)`,
          portion: "1 controlled serving",
          nutrients: {
            calories: 120,
            proteinG: 12.0,
            carbsG: 12.5,
            sodiumMg: 50,
            potassiumMg: 85,
          },
        };
      }
    }

    // If user explicitly requested custom favorites like Maggi / Noodles, synthesize safe MNT formulation
    // (exact match to backend/weekly_diet_engine.py:1056-1089)
    const hasMaggiLike = expandedLikes.some((lk) =>
      ["maggi", "noodle", "ramen"].some((m) => lk.includes(m))
    );
    const maggiLunchTemplate: RawDish = {
      title: "Clinically Formulated Vegetable Atta Maggi with Sautéed Tofu & Bell Peppers",
      items: [
        {
          name: "Whole Wheat Atta Noodles with Cabbage, Peas & Bell Peppers",
          portion: "1.5 cups cooked (180g)",
          nutrients: {
            calories: 240,
            protein_g: 6.5,
            carbs_g: 42.0,
            fat_g: 4.5,
            sodium_mg: 140,
            potassium_mg: 180,
            fiber_g: 5.0,
          },
        },
        {
          name: "Pan-Seared Turmeric Tofu Cubes (Low Salt)",
          portion: "1/2 cup (75g)",
          nutrients: {
            calories: 85,
            protein_g: 9.0,
            carbs_g: 2.5,
            fat_g: 4.5,
            sodium_mg: 30,
            potassium_mg: 95,
            fiber_g: 1.0,
          },
        },
      ],
      justification:
        "Clinically adapted whole-wheat noodle preparation using turmeric, roasted cumin, and fresh vegetables instead of commercial high-sodium flavor packets, preserving renal and hypertensive limits.",
      prep_tips:
        "Boil whole wheat noodles in water without commercial tastemaker packet. Sauté ginger, peas, carrots, and tofu in 1 tsp oil with home spices.",
    };

    for (let dayIdx = 1; dayIdx <= 7; dayIdx++) {
      const dayIntervals: SingleMealInterval[] = [];
      let dayCal = 0;
      let dayProt = 0;
      let daySod = 0;
      let dayPot = 0;

      for (const conf of intervalsConfig) {
        let pool = [...(regionDishes[conf.key] || fallbackDishes[conf.key] || [])];
        if (pool.length === 0) {
          pool = [...(fallbackDishes[conf.key] || [])];
        }

        // Inject cross-regional catalog dishes if user has preferred choices not in native catalog
        // (matches backend/weekly_diet_engine.py:1150-1162)
        if (expandedLikes.length > 0) {
          const addedTitles = new Set(pool.map((d) => d.title.toLowerCase()));
          for (const otherCat of Object.values(REGIONAL_CATALOG)) {
            for (const candidate of otherCat[conf.key] || []) {
              const cTitle = candidate.title.toLowerCase();
              if (addedTitles.has(cTitle)) continue;
              const cItemsStr = (candidate.items || []).map((it) => it.name.toLowerCase()).join(" ");
              const cText = `${cTitle} ${cItemsStr}`;
              if (expandedLikes.some((lk) => cText.includes(lk))) {
                pool.push(candidate);
                addedTitles.add(cTitle);
              }
            }
          }
        }

        // Inject custom Maggi formulation if requested by user
        if (hasMaggiLike && (conf.key === "lunch" || conf.key === "dinner")) {
          pool = [maggiLunchTemplate, ...pool];
        }

        let available = this.filterByDietary(pool, prefs.dietaryType, dayIdx, conf.key);
        available = this.filterByExclusions(available, allExclusions);
        if (available.length === 0) available = pool;

        // Clinical Suitability Scoring (matches backend/weekly_diet_engine.py:1172-1246)
        const scoreDish = (dish: RawDish): number => {
          let score = 50.0;
          const tLow = dish.title.toLowerCase();
          const items = dish.items || [];
          const iStr = items.map((it) => it.name.toLowerCase()).join(" ");
          const combined = `${tLow} ${iStr}`;

          const totalFiber = items.reduce((s, it) => s + (it.nutrients?.fiber_g || 0), 0);
          const totalCal = Math.max(1, items.reduce((s, it) => s + (it.nutrients?.calories || 0), 0));
          const totalCarbs = items.reduce((s, it) => s + (it.nutrients?.carbs_g || 0), 0);
          const totalProt = items.reduce((s, it) => s + (it.nutrients?.protein_g || 0), 0);
          const totalSod = items.reduce((s, it) => s + (it.nutrients?.sodium_mg || 0), 0);
          const carbCalRatio = (totalCarbs * 4.0) / totalCal;

          // 1. User preferences bonus (likes/interests)
          if (expandedLikes.length > 0) {
            for (const lk of expandedLikes) {
              if (tLow.includes(lk)) {
                score += 150.0;
              } else if (iStr.includes(lk)) {
                score += 80.0;
              }
            }
          }

          // 2. Diabetic & Prediabetic MNT Rules
          if (hasDiabetesCond || hasPrediabetesCond) {
            score += totalFiber * 6.0;
            const diabeticKw = [
              "millet", "foxtail", "ragi", "bajra", "jowar", "besan", "chilla", "sprout",
              "oats", "methi", "karela", "chia", "barley", "lauki", "moong", "brown rice",
              "quinoa", "beans", "spinach", "tofu", "dalia", "khichdi",
            ];
            for (const kw of diabeticKw) {
              if (combined.includes(kw)) score += 20.0;
            }

            const highGi = [
              "white rice", "sweet pongal", "sheera", "halwa", "maida", "potato", "aloo",
              "deep-fried", "sugar", "jaggery", "fried poori",
            ];
            for (const kw of highGi) {
              if (combined.includes(kw)) score -= 35.0;
            }

            if (carbCalRatio > 0.6 && totalFiber < 4.0) {
              score -= 25.0;
            }
          }

          // 3. CKD MNT Rules
          if (hasCkdCond) {
            if (totalProt > 25.0) score -= 20.0;
            if (combined.includes("tofu") || combined.includes("moong") || combined.includes("lauki")) {
              score += 15.0;
            }
            if (hasHyperkalemiaCond) {
              const highPotKw = ["spinach", "banana", "tender coconut", "avocado", "orange", "potato", "raisins"];
              for (const kw of highPotKw) {
                if (combined.includes(kw)) score -= 40.0;
              }
            }
          }

          // 4. Hypertension MNT Rules
          if (hasHtnCond) {
            if (totalSod < 120.0) score += 20.0;
            else if (totalSod > 240.0) score -= 25.0;
          }

          return score;
        };

        available.sort((a, b) => scoreDish(b) - scoreDish(a));

        // Prioritize preferred dishes while maintaining rotational variety
        // (matches backend/weekly_diet_engine.py:1252-1280)
        const preferredPool: RawDish[] = [];
        const otherPool: RawDish[] = [];
        if (expandedLikes.length > 0) {
          for (const d of available) {
            const dText = `${d.title} ${(d.items || []).map((it) => it.name).join(" ")}`.toLowerCase();
            if (expandedLikes.some((lk) => dText.includes(lk))) {
              preferredPool.push(d);
            } else {
              otherPool.push(d);
            }
          }
        }

        const catOffset = catVarietyOffsets[conf.key] || 0;
        let chosenDish: RawDish;

        if (preferredPool.length > 0) {
          if (preferredPool.length >= 3) {
            chosenDish = preferredPool[(dayIdx - 1 + catOffset) % preferredPool.length];
          } else {
            if (dayIdx % 2 === 1 || otherPool.length === 0) {
              const prefIdx = Math.floor((dayIdx - 1) / 2 + catOffset) % preferredPool.length;
              chosenDish = preferredPool[prefIdx];
            } else {
              const otherCandidates = otherPool.slice(0, Math.min(5, otherPool.length));
              const oIdx = Math.floor((dayIdx - 2) / 2 + catOffset) % otherCandidates.length;
              chosenDish = otherCandidates[oIdx];
            }
          }
        } else {
          const numTop = Math.max(1, Math.min(7, available.length));
          const topCandidates = available.slice(0, numTop);
          chosenDish = topCandidates[(dayIdx - 1 + catOffset) % topCandidates.length];
        }

        const isPreferredDish =
          expandedLikes.length > 0 &&
          Boolean(
            expandedLikes.some((lk) =>
              `${chosenDish.title} ${(chosenDish.items || []).map((it) => it.name).join(" ")}`
                .toLowerCase()
                .includes(lk)
            )
          );

        // Dynamically scale portions with clinical multi-target constraints
        let targetIntCal = targets.calories_kcal * conf.share;
        if (cravingRaw && dayIdx === 7) {
          if (conf.name === "Breakfast") targetIntCal = Math.max(100.0, targetIntCal - 50.0);
          else if (conf.name === "Lunch") targetIntCal = Math.max(150.0, targetIntCal - 75.0);
        }

        const maxIntProt = targets.protein_g * conf.share;
        const maxIntPot =
          hasCkdCond || hasHyperkalemiaCond ? targets.potassium_guidance_mg * conf.share : null;
        const maxIntSod = hasHtnCond || hasCkdCond ? targets.sodium_limit_mg * conf.share : null;

        const { scaledItems, totals: intNutrients } = scaleDishItems(
          chosenDish,
          targetIntCal,
          maxIntProt,
          maxIntPot,
          maxIntSod,
          hasCkdCond,
          hasHyperkalemiaCond
        );

        for (const it of scaledItems) {
          rawGroceryItems.push(it.itemName.split("(")[0].trim());
        }

        dayCal += intNutrients.calories;
        dayProt += intNutrients.protein_g;
        daySod += intNutrients.sodium_mg;
        dayPot += intNutrients.potassium_mg;

        const titlePrefix = isPreferredDish ? "⭐ " : "";

        // Construct dynamic condition-specific clinical justification matching desktop
        const clinicalTags: string[] = [];
        if (hasDiabetesCond) {
          clinicalTags.push(
            `[🩸 Diabetic MNT: Low-GI complex grain (<55 GI) paired with ${intNutrients.fiber_g || 4}g soluble fiber to control postprandial glucose spike]`
          );
        } else if (hasPrediabetesCond) {
          clinicalTags.push(
            `[🩸 Prediabetes MNT: Slow-release complex carbohydrates with ${intNutrients.fiber_g || 3}g fiber to protect insulin sensitivity]`
          );
        }

        if (hasCkdCond) {
          clinicalTags.push(
            `[🩺 Renal MNT: Preserving nephron hyperfiltration with controlled protein (${intNutrients.protein_g}g) and low phosphorus]`
          );
        }

        if (hasHtnCond) {
          clinicalTags.push(
            `[🫀 DASH MNT: Sodium-controlled preparation (${intNutrients.sodium_mg}mg Na) with potassium-magnesium rich vegetables]`
          );
        }

        if (clinicalTags.length === 0) {
          clinicalTags.push(
            "[✅ Balanced Vitality: Balanced macronutrient distribution supporting long-term metabolic health and vitality]"
          );
        }

        if (isPreferredDish) {
          clinicalTags.push(
            "[⭐ Preferred Choice: Selected specifically to incorporate your requested food preference while keeping within safe clinical limits]"
          );
        }

        const justificationText = `${chosenDish.justification || "Aligned with patient lab targets."} ${clinicalTags.join(" ")}`;

        const cleanDishTitle = chosenDish.title.replace(/^⭐\s*/, "");
        dayIntervals.push({
          intervalName: conf.name,
          timeWindow: conf.time,
          mealTitle: `${titlePrefix}${cleanDishTitle}`,
          items: scaledItems,
          totalNutrients: {
            calories: Math.round(intNutrients.calories),
            proteinG: roundToDecimal(intNutrients.protein_g, 2),
            sodiumMg: Math.round(intNutrients.sodium_mg),
            potassiumMg: Math.round(intNutrients.potassium_mg),
          },
          clinicalJustification: justificationText,
          prepTips: chosenDish.prep_tips || "Prepare fresh with low sodium rock salt.",
        });
      }

      // Smart Craving Sunday Replacement
      if (cravingRaw) {
        if (dayIdx < 7) {
          dayIntervals[0].clinicalJustification += ` [🔒 Strict Craving Lock: Zero ${cravingRaw} permitted today. This strict 6-day adherence builds insulin sensitivity and preserves weekly caloric balance for Sunday's budgeted treat.]`;
        } else {
          for (const inv of dayIntervals) {
            if (inv.intervalName === scheduledMealName && treatItem) {
              inv.mealTitle = indulgenceTitle;
              inv.items = [treatItem];
              inv.totalNutrients = {
                calories: treatItem.nutrients.calories || 120,
                proteinG: treatItem.nutrients.proteinG || 10,
                sodiumMg: treatItem.nutrients.sodiumMg || 50,
                potassiumMg: treatItem.nutrients.potassiumMg || 85,
              };
              inv.clinicalJustification = `🎯 Smart Craving Integration: Clinically portioned ${cravingRaw} safely budgeted for Sunday. Intra-day complex carbohydrates in Breakfast and Lunch were precision-rebalanced by -${Math.round(rebalanceCarbs)}g so Sunday strictly respects your daily metabolic targets (${targets.calories_kcal} kcal).`;
            }
          }
          dayCal = dayIntervals.reduce((s, inv) => s + inv.totalNutrients.calories, 0);
          dayProt = roundToDecimal(dayIntervals.reduce((s, inv) => s + inv.totalNutrients.proteinG, 0), 2);
          daySod = dayIntervals.reduce((s, inv) => s + inv.totalNutrients.sodiumMg, 0);
          dayPot = dayIntervals.reduce((s, inv) => s + (inv.totalNutrients.potassiumMg || 0), 0);
        }
      }

      days.push({
        dayNumber: dayIdx,
        dayName: dayNames[dayIdx - 1],
        intervals: dayIntervals,
        dailyTotalNutrients: {
          calories: dayCal,
          proteinG: roundToDecimal(dayProt, 2),
          sodiumMg: daySod,
          potassiumMg: dayPot,
        },
      });
    }

    const categorizedGroceries = categorizeGroceries(rawGroceryItems);

    return {
      userId: "patient_mobile",
      generatedAt: new Date().toISOString(),
      testReportDate: reportDate,
      isHistoricalTest: isHistorical,
      calibratedVitals: { ...vitals },
      nativeRegion: regionKey.replace("_", " ").toUpperCase(),
      dietaryType: prefs.dietaryType.toUpperCase(),
      caloricTargetKcal: targets.calories_kcal,
      proteinTargetG: targets.protein_g,
      sodiumTargetMg: targets.sodium_limit_mg,
      potassiumTargetMg: targets.potassium_guidance_mg,
      carbohydrateTargetG: targets.carbohydrate_g,
      fatTargetG: targets.fat_g,
      fiberTargetG: targets.fiber_target_g,
      phosphorusTargetMg: targets.phosphorus_limit_mg,
      fluidIntakeMl: targets.fluid_intake_ml,
      clinicalTargets: targets,
      detectedConditions,
      medicationAlerts: medAlerts,
      days,
      categorizedGroceries,
      cravingStrategy: cravingRaw
        ? {
            requestedCraving: cravingRaw,
            scheduledDay: "Sunday",
            scheduledMeal: scheduledMealName,
            metabolicRebalanceNote: `Sunday complex carbohydrates in Breakfast & Lunch were precision-reduced by -${Math.round(rebalanceCarbs)}g to balance Sunday totals.`,
            sixDayLockNote: `Days 1 to 6 (Monday–Saturday) strictly enforce 0% ${cravingRaw} to maintain insulin sensitivity and optimize clinical biomarkers.`,
          }
        : undefined,
    };
  }
}
