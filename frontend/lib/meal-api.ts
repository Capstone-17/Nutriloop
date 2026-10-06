import type { UserProfile } from "./auth-context"

export interface FoodItem {
  id: string
  name: string
  brand?: string
  servingSize: string
  servingUnit: string
  calories: number
  nutrients: {
    carbs: number // grams
    protein: number // grams
    fat: number // grams
    fiber: number // grams
    sodium: number // mg
    potassium: number // mg
    glucose?: number // mg (estimated)
  }
}

export interface MealEntry {
  id: string
  foodId: string
  foodName: string
  servings: number
  timestamp: string
  nutrients: {
    calories: number
    carbs: number
    protein: number
    fat: number
    fiber: number
    sodium: number
    potassium: number
    glucose: number
  }
}

export interface DailyNutrients {
  date: string
  calories: number
  carbs: number
  protein: number
  fat: number
  fiber: number
  sodium: number
  potassium: number
  glucose: number
  meals: MealEntry[]
}

export interface NutritionRecommendation {
  priority: "high" | "medium" | "low"
  message: string
  nutrient: string
  reason: string
}

// Mock food database - in production, this would call USDA FoodData Central or similar
const mockFoods: FoodItem[] = [
  {
    id: "1",
    name: "Apple, medium",
    servingSize: "182",
    servingUnit: "g",
    calories: 95,
    nutrients: {
      carbs: 25,
      protein: 0.5,
      fat: 0.3,
      fiber: 4.4,
      sodium: 2,
      potassium: 195,
      glucose: 12,
    },
  },
  {
    id: "2",
    name: "Banana, medium",
    servingSize: "118",
    servingUnit: "g",
    calories: 105,
    nutrients: {
      carbs: 27,
      protein: 1.3,
      fat: 0.3,
      fiber: 3.1,
      sodium: 1,
      potassium: 422,
      glucose: 18,
    },
  },
  {
    id: "3",
    name: "Chicken breast, cooked",
    servingSize: "100",
    servingUnit: "g",
    calories: 165,
    nutrients: {
      carbs: 0,
      protein: 31,
      fat: 3.6,
      fiber: 0,
      sodium: 74,
      potassium: 220,
      glucose: 0,
    },
  },
  {
    id: "4",
    name: "Brown rice, cooked",
    servingSize: "195",
    servingUnit: "g",
    calories: 215,
    nutrients: {
      carbs: 45,
      protein: 5,
      fat: 1.8,
      fiber: 3.5,
      sodium: 10,
      potassium: 84,
      glucose: 25,
    },
  },
  {
    id: "5",
    name: "Broccoli, steamed",
    servingSize: "156",
    servingUnit: "g",
    calories: 55,
    nutrients: {
      carbs: 11,
      protein: 3.7,
      fat: 0.6,
      fiber: 2.4,
      sodium: 64,
      potassium: 316,
      glucose: 3,
    },
  },
  {
    id: "6",
    name: "Salmon, cooked",
    servingSize: "100",
    servingUnit: "g",
    calories: 206,
    nutrients: {
      carbs: 0,
      protein: 25,
      fat: 11,
      fiber: 0,
      sodium: 75,
      potassium: 363,
      glucose: 0,
    },
  },
  {
    id: "7",
    name: "Oatmeal, cooked",
    servingSize: "150",
    servingUnit: "g",
    calories: 150,
    nutrients: {
      carbs: 27,
      protein: 5,
      fat: 3,
      fiber: 4,
      sodium: 2,
      potassium: 166,
      glucose: 8,
    },
  },
  {
    id: "8",
    name: "Sweet potato, baked",
    servingSize: "100",
    servingUnit: "g",
    calories: 86,
    nutrients: {
      carbs: 20,
      protein: 1.6,
      fat: 0.1,
      fiber: 3,
      sodium: 55,
      potassium: 337,
      glucose: 10,
    },
  },
  {
    id: "9",
    name: "Spinach, raw",
    servingSize: "30",
    servingUnit: "g",
    calories: 7,
    nutrients: {
      carbs: 1.1,
      protein: 0.9,
      fat: 0.1,
      fiber: 0.7,
      sodium: 24,
      potassium: 167,
      glucose: 0.2,
    },
  },
  {
    id: "10",
    name: "Whole wheat bread, 1 slice",
    servingSize: "28",
    servingUnit: "g",
    calories: 80,
    nutrients: {
      carbs: 14,
      protein: 4,
      fat: 1,
      fiber: 2,
      sodium: 140,
      potassium: 90,
      glucose: 4,
    },
  },
  {
    id: "11",
    name: "Egg, large boiled",
    servingSize: "50",
    servingUnit: "g",
    calories: 78,
    nutrients: {
      carbs: 0.6,
      protein: 6.3,
      fat: 5.3,
      fiber: 0,
      sodium: 62,
      potassium: 63,
      glucose: 0,
    },
  },
  {
    id: "12",
    name: "Olive oil, 1 tbsp",
    servingSize: "15",
    servingUnit: "ml",
    calories: 120,
    nutrients: {
      carbs: 0,
      protein: 0,
      fat: 14,
      fiber: 0,
      sodium: 0,
      potassium: 0,
      glucose: 0,
    },
  },
]

export async function searchFoods(query: string): Promise<FoodItem[]> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 300))

  if (!query.trim()) return []

  const lowerQuery = query.toLowerCase()
  return mockFoods.filter(
    food =>
      food.name.toLowerCase().includes(lowerQuery) ||
      (food.brand?.toLowerCase().includes(lowerQuery))
  )
}

export function calculateMealNutrients(food: FoodItem, servings: number): MealEntry["nutrients"] {
  return {
    calories: Math.round(food.calories * servings),
    carbs: Math.round(food.nutrients.carbs * servings * 10) / 10,
    protein: Math.round(food.nutrients.protein * servings * 10) / 10,
    fat: Math.round(food.nutrients.fat * servings * 10) / 10,
    fiber: Math.round(food.nutrients.fiber * servings * 10) / 10,
    sodium: Math.round(food.nutrients.sodium * servings),
    potassium: Math.round(food.nutrients.potassium * servings),
    glucose: Math.round(food.nutrients.glucose * servings * 10) / 10,
  }
}

export function generateRecommendations(
  dailyNutrients: DailyNutrients,
  profile?: UserProfile
): NutritionRecommendation[] {
  const recommendations: NutritionRecommendation[] = []

  // Sodium limits (higher for non-hypertension patients)
  const sodiumLimit = profile?.selectedDiseases.includes("hypertension") ? 2000 : 2500
  if (dailyNutrients.sodium > sodiumLimit) {
    recommendations.push({
      priority: "high",
      message: `High sodium intake (${dailyNutrients.sodium}mg). Recommended: ${sodiumLimit}mg/day`,
      nutrient: "Sodium",
      reason: profile?.selectedDiseases.includes("hypertension")
        ? "Hypertension patients need strict sodium control"
        : "General health recommendation",
    })
  }

  // Carbs/Glucose tracking for diabetes
  if (profile?.selectedDiseases.includes("diabetes")) {
    if (dailyNutrients.glucose > 180) {
      recommendations.push({
        priority: "high",
        message: `High glucose impact (${dailyNutrients.glucose}g). Focus on low-GI foods`,
        nutrient: "Glucose",
        reason: "Diabetes patients need low glycemic load",
      })
    }
    if (dailyNutrients.carbs > 250) {
      recommendations.push({
        priority: "medium",
        message: `High carbohydrates (${dailyNutrients.carbs}g). Consider reducing refined carbs`,
        nutrient: "Carbohydrates",
        reason: "Helps maintain stable blood sugar",
      })
    }
  }

  // Fiber recommendations (good for CKD & Diabetes)
  if (dailyNutrients.fiber < 25) {
    recommendations.push({
      priority: "medium",
      message: `Low fiber intake (${dailyNutrients.fiber}g). Target: 25-30g/day`,
      nutrient: "Fiber",
      reason: "Improves digestion and blood sugar control",
    })
  }

  // Protein for CKD patients (need lower intake)
  if (profile?.selectedDiseases.includes("ckd") && dailyNutrients.protein > 50) {
    recommendations.push({
      priority: "high",
      message: `High protein intake (${dailyNutrients.protein}g). CKD patients should limit to ~50g/day`,
      nutrient: "Protein",
      reason: "Excess protein worsens kidney function in CKD",
    })
  }

  // Potassium for CKD patients (need lower intake if advanced CKD)
  if (profile?.selectedDiseases.includes("ckd") && dailyNutrients.potassium > 2000) {
    recommendations.push({
      priority: "medium",
      message: `Moderate potassium intake (${dailyNutrients.potassium}mg). Limit processed foods`,
      nutrient: "Potassium",
      reason: "Advanced CKD may require potassium restriction",
    })
  }

  // Positive recommendations
  if (dailyNutrients.calories >= 1800 && dailyNutrients.calories <= 2200) {
    recommendations.push({
      priority: "low",
      message: "✓ Calorie intake looks good",
      nutrient: "Calories",
      reason: "Well-balanced energy intake",
    })
  }

  return recommendations.sort((a, b) => {
    const priorityMap = { high: 0, medium: 1, low: 2 }
    return priorityMap[a.priority] - priorityMap[b.priority]
  })
}

export function getDailyNutrients(meals: MealEntry[]): Omit<DailyNutrients, "date"> {
  const totals: any = {
    calories: 0,
    carbs: 0,
    protein: 0,
    fat: 0,
    fiber: 0,
    sodium: 0,
    potassium: 0,
    glucose: 0,
    meals,
  }

  meals.forEach(meal => {
    totals.calories += meal.nutrients.calories
    totals.carbs += meal.nutrients.carbs
    totals.protein += meal.nutrients.protein
    totals.fat += meal.nutrients.fat
    totals.fiber += meal.nutrients.fiber
    totals.sodium += meal.nutrients.sodium
    totals.potassium += meal.nutrients.potassium
    totals.glucose += meal.nutrients.glucose
  })

  // Round all to 1 decimal place
  Object.keys(totals).forEach(key => {
    if (key !== "meals") {
      totals[key] = Math.round(totals[key] * 10) / 10
    }
  })

  return totals
}

export function getDateString(date = new Date()): string {
  return date.toISOString().split("T")[0]
}
