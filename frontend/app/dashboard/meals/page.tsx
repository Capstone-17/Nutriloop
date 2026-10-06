"use client"

import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  TrendingUp,
  Calendar,
  Loader2,
} from "lucide-react"
import { DashboardLayout } from "@/components/dashboard/dashboard-layout"
import { BentoCard } from "@/components/dashboard/bento-card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import * as mealApi from "@/lib/meal-api"

export default function MealLoggingPage() {
  const { user } = useAuth()
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<mealApi.FoodItem[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedFood, setSelectedFood] = useState<mealApi.FoodItem | null>(null)
  const [servings, setServings] = useState(1)
  const [todaysMeals, setTodaysMeals] = useState<mealApi.MealEntry[]>([])
  const [history, setHistory] = useState<Record<string, mealApi.DailyNutrients>>({})
  const [recommendations, setRecommendations] = useState<mealApi.NutritionRecommendation[]>([])

  const today = mealApi.getDateString()

  // Load from localStorage on mount
  useEffect(() => {
    const storedMeals = JSON.parse(
      localStorage.getItem(`nutriloop_meals_${user?.email}_${today}`) || "[]"
    )
    const storedHistory = JSON.parse(
      localStorage.getItem(`nutriloop_meal_history_${user?.email}`) || "{}"
    )
    setTodaysMeals(storedMeals)
    setHistory(storedHistory)
  }, [user?.email, today])

  // Update recommendations when meals change
  useEffect(() => {
    const dailyNutrients = mealApi.getDailyNutrients(todaysMeals)
    const newRecommendations = mealApi.generateRecommendations(
      { ...dailyNutrients, date: today, meals: todaysMeals },
      user?.profile
    )
    setRecommendations(newRecommendations)

    // Save to localStorage
    localStorage.setItem(
      `nutriloop_meals_${user?.email}_${today}`,
      JSON.stringify(todaysMeals)
    )
  }, [todaysMeals, user?.profile, today, user?.email])

  // Search foods
  useEffect(() => {
    const searchFoods = async () => {
      if (!searchQuery.trim()) {
        setSearchResults([])
        return
      }
      setSearching(true)
      try {
        const results = await mealApi.searchFoods(searchQuery)
        setSearchResults(results)
      } finally {
        setSearching(false)
      }
    }

    const timer = setTimeout(searchFoods, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const handleAddMeal = () => {
    if (!selectedFood || servings <= 0) return

    const nutrients = mealApi.calculateMealNutrients(selectedFood, servings)
    const newMeal: mealApi.MealEntry = {
      id: Date.now().toString(),
      foodId: selectedFood.id,
      foodName: selectedFood.name,
      servings,
      timestamp: new Date().toISOString(),
      nutrients,
    }

    setTodaysMeals([...todaysMeals, newMeal])
    setSelectedFood(null)
    setServings(1)
    setSearchQuery("")
  }

  const handleRemoveMeal = (mealId: string) => {
    setTodaysMeals(todaysMeals.filter(m => m.id !== mealId))
  }

  const handleSaveDay = () => {
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
    localStorage.setItem(
      `nutriloop_meal_history_${user?.email}`,
      JSON.stringify(newHistory)
    )
  }

  const dailyNutrients = mealApi.getDailyNutrients(todaysMeals)

  const nutrientGoals = {
    calories: { goal: 2000, unit: "kcal" },
    carbs: { goal: 300, unit: "g" },
    protein: { goal: 50, unit: "g" },
    fiber: { goal: 25, unit: "g" },
    sodium: { goal: 2300, unit: "mg" },
  }

  return (
    <DashboardLayout>
      <header className="mb-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-3xl font-bold tracking-tight">Meal Logging</h1>
          <p className="text-muted-foreground mt-1">
            Log your meals and track nutrients based on your health profile
          </p>
        </motion.div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Search & Add Meal Section */}
        <div className="lg:col-span-1 space-y-6">
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Search className="h-5 w-5 text-primary" />
              Add Meal
            </h2>

            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Search Foods</Label>
                <div className="relative mt-1">
                  <Input
                    placeholder="Search meals (e.g., chicken, apple)..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pr-10"
                  />
                  {searching && (
                    <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                </div>
              </div>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="border rounded-lg max-h-64 overflow-y-auto">
                  {searchResults.map(food => (
                    <button
                      key={food.id}
                      onClick={() => setSelectedFood(food)}
                      className={cn(
                        "w-full text-left p-3 border-b hover:bg-primary/5 transition-colors",
                        selectedFood?.id === food.id && "bg-primary/10 border-primary"
                      )}
                    >
                      <p className="font-medium text-sm">{food.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {food.calories} cal • {food.servingSize}{food.servingUnit}
                      </p>
                    </button>
                  ))}
                </div>
              )}

              {/* Selected Food Details */}
              {selectedFood && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 rounded-lg bg-primary/5 border border-primary/20"
                >
                  <p className="font-semibold text-sm mb-3">{selectedFood.name}</p>

                  <div className="space-y-3">
                    <div>
                      <Label className="text-xs font-medium">Servings</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <button
                          onClick={() => setServings(Math.max(0.5, servings - 0.5))}
                          className="px-2 py-1 rounded border hover:bg-secondary text-sm"
                        >
                          −
                        </button>
                        <Input
                          type="number"
                          min="0.5"
                          step="0.5"
                          value={servings}
                          onChange={(e) => setServings(Math.max(0.5, Number(e.target.value)))}
                          className="text-center"
                        />
                        <button
                          onClick={() => setServings(servings + 0.5)}
                          className="px-2 py-1 rounded border hover:bg-secondary text-sm"
                        >
                          +
                        </button>
                      </div>
                    </div>

                    <div className="text-xs text-muted-foreground space-y-1">
                      <p>
                        <span className="font-medium">Calories:</span>{" "}
                        {Math.round(selectedFood.calories * servings)}
                      </p>
                      <p>
                        <span className="font-medium">Protein:</span>{" "}
                        {(selectedFood.nutrients.protein * servings).toFixed(1)}g
                      </p>
                      <p>
                        <span className="font-medium">Carbs:</span>{" "}
                        {(selectedFood.nutrients.carbs * servings).toFixed(1)}g
                      </p>
                    </div>

                    <Button onClick={handleAddMeal} className="w-full gap-2">
                      <Plus className="h-4 w-4" />
                      Add to Meals
                    </Button>
                  </div>
                </motion.div>
              )}
            </div>
          </BentoCard>

          {/* Historical Stats */}
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Calendar className="h-5 w-5 text-accent" />
              History
            </h2>

            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Object.entries(history)
                .reverse()
                .slice(0, 7)
                .map(([date, data]) => (
                  <div
                    key={date}
                    className="p-3 rounded-lg bg-secondary/50 text-xs border border-secondary/50"
                  >
                    <p className="font-medium text-sm">{date}</p>
                    <div className="grid grid-cols-2 gap-2 mt-2 text-muted-foreground">
                      <p>{data.calories} cal</p>
                      <p>{data.meals.length} meals</p>
                    </div>
                  </div>
                ))}
            </div>
          </BentoCard>
        </div>

        {/* Nutrients Tracking & Recommendations */}
        <div className="lg:col-span-2 space-y-6">
          {/* Daily Nutrients Summary */}
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Daily Nutrients ({today})
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              {Object.entries(nutrientGoals).map(([key, { goal, unit }]) => {
                const actual = dailyNutrients[key as keyof typeof dailyNutrients] || 0
                const percentage = Math.min((actual / goal) * 100, 100)

                return (
                  <div key={key} className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label className="text-xs font-medium capitalize">{key}</Label>
                      <span className="text-xs text-muted-foreground">
                        {actual}{unit} / {goal}{unit}
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-secondary overflow-hidden">
                      <motion.div
                        className={cn(
                          "h-full transition-all",
                          percentage <= 75
                            ? "bg-green-500"
                            : percentage <= 100
                            ? "bg-yellow-500"
                            : "bg-red-500"
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Detailed Nutrients */}
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground">Protein</p>
                <p className="text-lg font-bold text-primary">{dailyNutrients.protein}g</p>
              </div>
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground">Fat</p>
                <p className="text-lg font-bold text-accent">{dailyNutrients.fat}g</p>
              </div>
              <div className="p-3 rounded-lg bg-secondary/30">
                <p className="text-xs text-muted-foreground">Fiber</p>
                <p className="text-lg font-bold text-chart-4">{dailyNutrients.fiber}g</p>
              </div>
            </div>
          </BentoCard>

          {/* AI Recommendations */}
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              AI Recommendations
            </h2>

            {recommendations.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                No recommendations yet. Start logging meals to get personalized advice.
              </div>
            ) : (
              <div className="space-y-3">
                {recommendations.map((rec, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={cn(
                      "p-4 rounded-lg border-l-4",
                      rec.priority === "high" && "bg-red-50/50 border-l-red-500",
                      rec.priority === "medium" && "bg-yellow-50/50 border-l-yellow-500",
                      rec.priority === "low" && "bg-green-50/50 border-l-green-500"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {rec.priority === "high" && (
                        <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                      )}
                      {rec.priority === "medium" && (
                        <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                      )}
                      {rec.priority === "low" && (
                        <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                      )}
                      <div>
                        <p className="font-medium text-sm">{rec.message}</p>
                        <p className="text-xs text-muted-foreground mt-1">{rec.reason}</p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </BentoCard>

          {/* Today's Meals */}
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4">Meals Added Today</h2>

            {todaysMeals.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                No meals logged yet. Use the search to add your first meal!
              </div>
            ) : (
              <div className="space-y-2">
                <AnimatePresence>
                  {todaysMeals.map(meal => (
                    <motion.div
                      key={meal.id}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: 100 }}
                      className="p-4 rounded-lg border border-secondary/50 bg-secondary/20 flex items-center justify-between"
                    >
                      <div className="flex-1">
                        <p className="font-medium text-sm">{meal.foodName}</p>
                        <p className="text-xs text-muted-foreground">
                          {meal.servings} serving{meal.servings !== 1 ? "s" : ""} •{" "}
                          {meal.nutrients.calories} cal
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveMeal(meal.id)}
                        className="text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}

            {todaysMeals.length > 0 && (
              <Button
                onClick={handleSaveDay}
                className="w-full mt-4 gap-2"
                variant="outline"
              >
                <CheckCircle2 className="h-4 w-4" />
                Save Day to History
              </Button>
            )}
          </BentoCard>
        </div>
      </div>
    </DashboardLayout>
  )
}
