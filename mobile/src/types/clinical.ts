export interface PatientVitals {
  ageYears: number;
  sex: "male" | "female";
  bodyMassIndex: number;
  systolicBpMmhg: number;
  diastolicBpMmhg: number;
  fastingGlucoseMgDl: number;
  hba1cPct: number;
  serumCreatinineMgDl: number;
  egfrMlMin: number;
  serumPotassiumMeqL: number;
  serumSodiumMeqL: number;
}

export interface DiseaseAssessment {
  disease: "ckd" | "hypertension" | "diabetes";
  diseaseName: string;
  riskScore: number;
  riskLevel: "low" | "moderate" | "high";
  riskPercentage: number;
  primaryDrivers: string[];
  protectiveFactors: string[];
  clinicalSummary: string;
}

export interface MultiDiseaseAssessmentResult {
  timestamp: string;
  detectedConditions: string[];
  assessments: {
    ckd: DiseaseAssessment;
    hypertension: DiseaseAssessment;
    diabetes: DiseaseAssessment;
  };
  vitals: PatientVitals;
}

export interface MealItem {
  itemName: string;
  portion: string;
  nutrients: {
    calories?: number;
    proteinG?: number;
    sodiumMg?: number;
    potassiumMg?: number;
    carbsG?: number;
  };
}

export interface SingleMealInterval {
  intervalName: string; // "Breakfast", "Mid-Morning Snack", "Lunch", "Evening Snack", "Dinner"
  timeWindow: string;
  mealTitle: string;
  items: MealItem[];
  totalNutrients: {
    calories: number;
    proteinG: number;
    sodiumMg: number;
    potassiumMg?: number;
    carbsG?: number;
  };
  clinicalJustification: string;
  prepTips: string;
}

export interface DayDietPlan {
  dayNumber: number;
  dayName: string;
  intervals: SingleMealInterval[];
  dailyTotalNutrients: {
    calories: number;
    proteinG: number;
    sodiumMg: number;
    potassiumMg?: number;
  };
}

export interface PatientPreferences {
  nativeRegion: "south_indian" | "north_indian" | "western_indian" | "eastern_indian" | "continental";
  dietaryType: "vegetarian" | "non_vegetarian" | "vegan" | "eggetarian" | "jain";
  cookingSkill?: "intermediate" | "beginner" | "advanced";
  maxPrepTimeMins?: number;
  allergies?: string[];
  dislikes?: string[];
  interestsAndLikes: string[];
  activeMedications: string[];
  calorieOverride?: number;
  cravingOrTreat?: string;
}

export interface ClinicalTargets {
  calories_kcal: number;
  protein_g: number;
  carbohydrate_g: number;
  fat_g: number;
  fiber_target_g: number;
  sodium_limit_mg: number;
  potassium_guidance_mg: number;
  phosphorus_limit_mg: number;
  fluid_intake_ml: number;
  free_sugar_limit_g?: number;
}

export interface WeeklyDietPlan {
  userId: string;
  generatedAt: string;
  nativeRegion: string;
  dietaryType: string;
  caloricTargetKcal: number;
  proteinTargetG: number;
  sodiumTargetMg: number;
  potassiumTargetMg: number;
  carbohydrateTargetG?: number;
  fatTargetG?: number;
  fiberTargetG?: number;
  phosphorusTargetMg?: number;
  fluidIntakeMl?: number;
  clinicalTargets?: ClinicalTargets;
  testReportDate?: string;
  isHistoricalTest?: boolean;
  calibratedVitals?: PatientVitals;
  detectedConditions: string[];
  medicationAlerts: string[];
  days: DayDietPlan[];
  categorizedGroceries: Record<string, string[]>;
  cravingStrategy?: {
    requestedCraving: string;
    scheduledDay: string;
    scheduledMeal: string;
    metabolicRebalanceNote: string;
    sixDayLockNote: string;
  };
}

export interface PatientTestHistoryRecord {
  id: number;
  userId: string;
  createdAt: string;
  vitals: PatientVitals;
  detectedConditions: string[];
  assessments: MultiDiseaseAssessmentResult["assessments"];
}

export interface SavePatientTestResult {
  id: number;
  isDuplicate: boolean;
}
