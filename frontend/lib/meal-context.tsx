'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import * as mealApi from './meal-api'

export interface MealContextType {
  todaysMeals: mealApi.MealEntry[]
  history: Record<string, mealApi.DailyNutrients>
  dailyNutrients: ReturnType<typeof mealApi.getDailyNutrients>
  recommendations: mealApi.NutritionRecommendation[]
  addMeal: (food: mealApi.FoodItem, servings: number) => void
  removeMeal: (mealId: string) => void
  saveDayToHistory: () => void
  userEmail: string | null
}

const MealContext = createContext<MealContextType | undefined>(undefined)

export function MealProvider({ children, userEmail }: { children: React.ReactNode; userEmail: string | null }) {
  const [todaysMeals, setTodaysMeals] = useState<mealApi.MealEntry[]>([])
  const [history, setHistory] = useState<Record<string, mealApi.DailyNutrients>>({})
  const [recommendations, setRecommendations] = useState<mealApi.NutritionRecommendation[]>([])
  const today = mealApi.getDateString()

  // Load from localStorage on mount and when userEmail changes
  useEffect(() => {
    if (!userEmail) return

    const storedMeals = JSON.parse(
      localStorage.getItem(`nutriloop_meals_${userEmail}_${today}`) || '[]'
    )
    const storedHistory = JSON.parse(
      localStorage.getItem(`nutriloop_meal_history_${userEmail}`) || '{}'
    )
    setTodaysMeals(storedMeals)
    setHistory(storedHistory)
  }, [userEmail, today])

  // Update recommendations when meals change
  useEffect(() => {
    const dailyNutrients = mealApi.getDailyNutrients(todaysMeals)
    // Note: We'll pass userProfile through context or prop later
    const newRecommendations = mealApi.generateRecommendations(
      { ...dailyNutrients, date: today, meals: todaysMeals },
      undefined // Profile will be passed when integrated with Auth
    )
    setRecommendations(newRecommendations)

    // Persist to localStorage
    if (userEmail) {
      localStorage.setItem(
        `nutriloop_meals_${userEmail}_${today}`,
        JSON.stringify(todaysMeals)
      )
    }
  }, [todaysMeals, userEmail, today])

  const addMeal = (food: mealApi.FoodItem, servings: number) => {
    const nutrients = mealApi.calculateMealNutrients(food, servings)
    const newMeal: mealApi.MealEntry = {
      id: Date.now().toString(),
      foodId: food.id,
      foodName: food.name,
      servings,
      timestamp: new Date().toISOString(),
      nutrients,
    }
    setTodaysMeals([...todaysMeals, newMeal])
  }

  const removeMeal = (mealId: string) => {
    setTodaysMeals(todaysMeals.filter(m => m.id !== mealId))
  }

  const saveDayToHistory = () => {
    const dailyData = {
      date: today,
      ...mealApi.getDailyNutrients(todaysMeals),
      meals: todaysMeals,
    }

    const newHistory = {
      ...history,
      [today]: dailyData,
    }
    setHistory(newHistory)
    if (userEmail) {
      localStorage.setItem(
        `nutriloop_meal_history_${userEmail}`,
        JSON.stringify(newHistory)
      )
    }
  }

  const dailyNutrients = mealApi.getDailyNutrients(todaysMeals)

  return (
    <MealContext.Provider
      value={{
        todaysMeals,
        history,
        dailyNutrients,
        recommendations,
        addMeal,
        removeMeal,
        saveDayToHistory,
        userEmail,
      }}
    >
      {children}
    </MealContext.Provider>
  )
}

export function useMeals() {
  const context = useContext(MealContext)
  if (context === undefined) {
    throw new Error('useMeals must be used within MealProvider')
  }
  return context
}
