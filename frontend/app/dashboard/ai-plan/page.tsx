"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  Check,
  ChefHat,
  Clock,
  Info,
  Lightbulb,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Utensils,
  Zap,
} from "lucide-react"
import { DashboardLayout } from "@/components/dashboard/dashboard-layout"
import { BentoCard, BentoGrid } from "@/components/dashboard/bento-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

// Mock deviation data
const deviationData = {
  detected: true,
  type: "sodium",
  value: 890,
  limit: 600,
  meal: "Butter Chicken (Lunch)",
  impact: "High sodium intake detected. Risk of elevated blood pressure and kidney stress."
}

// Mock AI-generated meal suggestions
const aiMealSuggestions = [
  {
    id: 1,
    name: "Steamed Moong Dal with Jeera Rice",
    time: "Dinner (7:00 PM)",
    calories: 320,
    sodium: 180,
    potassium: 420,
    protein: 14,
    explanation: "This meal was chosen because it offsets your high sodium intake from lunch and aligns with CKD Stage 2 protocols. Moong dal is kidney-friendly with low phosphorus content.",
    confidence: 94,
    tags: ["Low Sodium", "CKD Friendly", "Diabetic Safe"]
  },
  {
    id: 2,
    name: "Cucumber Raita with Phulka",
    time: "Snack (5:00 PM)",
    calories: 150,
    sodium: 95,
    potassium: 280,
    protein: 6,
    explanation: "Light snack to maintain blood sugar levels. The probiotics in curd support gut health while the cucumber provides hydration without excess potassium.",
    confidence: 89,
    tags: ["Light", "Probiotic", "Hydrating"]
  },
  {
    id: 3,
    name: "Vegetable Upma (Low Salt)",
    time: "Tomorrow Breakfast",
    calories: 180,
    sodium: 120,
    potassium: 220,
    protein: 5,
    explanation: "Starting tomorrow with low-sodium breakfast to compensate for today's excess. Semolina provides sustained energy for diabetic management.",
    confidence: 91,
    tags: ["Next Day", "Low Sodium", "Energy"]
  }
]

// Mock daily plan
const dailyPlan = {
  consumed: {
    calories: 865,
    sodium: 1580,
    potassium: 1420,
    protein: 38
  },
  limits: {
    calories: 1800,
    sodium: 2000,
    potassium: 3000,
    protein: 60
  },
  remaining: {
    calories: 935,
    sodium: 420,
    potassium: 1580,
    protein: 22
  }
}

export default function AIPlanPage() {
  const [isRecalculating, setIsRecalculating] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  const [approvedMeals, setApprovedMeals] = useState<number[]>([])

  const handleRecalculate = async () => {
    setIsRecalculating(true)
    // Simulate AI processing
    await new Promise(resolve => setTimeout(resolve, 2500))
    setIsRecalculating(false)
    setShowPlan(true)
  }

  const toggleMealApproval = (mealId: number) => {
    setApprovedMeals(prev => 
      prev.includes(mealId) 
        ? prev.filter(id => id !== mealId)
        : [...prev, mealId]
    )
  }

  return (
    <DashboardLayout>
      <TooltipProvider>
        <header className="mb-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="text-primary">Generative AI</span> Meal Planner
            </h1>
            <p className="text-muted-foreground mt-1">
              AI-powered meal recalculation engine based on your health metrics and deviations
            </p>
          </motion.div>
        </header>

        <BentoGrid>
          {/* Deviation Alert */}
          {deviationData.detected && (
            <BentoCard colSpan={3} className="border-chart-3/30 bg-chart-3/5">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-chart-3/20">
                  <AlertTriangle className="h-6 w-6 text-chart-3" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h2 className="font-semibold text-lg text-chart-3">Deviation Detected</h2>
                    <Badge variant="outline" className="border-chart-3/30 text-chart-3">
                      {deviationData.type.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mb-3">
                    <strong>{deviationData.meal}</strong> contained {deviationData.value}mg sodium 
                    (exceeds single-meal limit of {deviationData.limit}mg)
                  </p>
                  <p className="text-sm text-chart-3">
                    {deviationData.impact}
                  </p>
                </div>
                <Button 
                  onClick={handleRecalculate}
                  disabled={isRecalculating}
                  className="bg-gradient-to-r from-primary to-accent hover:opacity-90 glow-cyan"
                >
                  {isRecalculating ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Recalculating...
                    </>
                  ) : (
                    <>
                      <Brain className="mr-2 h-4 w-4" />
                      Recalculate Plan
                    </>
                  )}
                </Button>
              </div>
            </BentoCard>
          )}

          {/* Current Day Status */}
          <BentoCard colSpan={2}>
            <div className="flex items-center gap-2 mb-4">
              <Zap className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-lg">Today&apos;s Status</h2>
            </div>

            <div className="space-y-4">
              {Object.entries(dailyPlan.consumed).map(([key, value]) => {
                const limit = dailyPlan.limits[key as keyof typeof dailyPlan.limits]
                const percentage = (value / limit) * 100
                const isWarning = percentage > 70
                const isDanger = percentage > 90

                return (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="capitalize font-medium">{key}</span>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          isDanger ? "text-destructive" : isWarning ? "text-chart-3" : "text-muted-foreground"
                        )}>
                          {value} / {limit} {key === "calories" ? "kcal" : key === "protein" ? "g" : "mg"}
                        </span>
                        {isDanger && <AlertTriangle className="h-3 w-3 text-destructive" />}
                      </div>
                    </div>
                    <Progress 
                      value={Math.min(percentage, 100)} 
                      className={cn(
                        "h-2",
                        isDanger ? "[&>div]:bg-destructive" : 
                        isWarning ? "[&>div]:bg-chart-3" : 
                        "[&>div]:bg-accent"
                      )}
                    />
                  </div>
                )
              })}
            </div>

            <div className="mt-6 p-4 rounded-lg bg-primary/10 border border-primary/20">
              <div className="flex items-center gap-2 mb-2">
                <Lightbulb className="h-4 w-4 text-primary" />
                <span className="font-medium text-sm">Remaining Allowance</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>Calories: <span className="text-accent font-medium">{dailyPlan.remaining.calories} kcal</span></div>
                <div>Sodium: <span className={cn(
                  "font-medium",
                  dailyPlan.remaining.sodium < 300 ? "text-chart-3" : "text-accent"
                )}>{dailyPlan.remaining.sodium} mg</span></div>
                <div>Potassium: <span className="text-accent font-medium">{dailyPlan.remaining.potassium} mg</span></div>
                <div>Protein: <span className="text-accent font-medium">{dailyPlan.remaining.protein} g</span></div>
              </div>
            </div>
          </BentoCard>

          {/* AI Processing Animation */}
          <BentoCard gradient>
            <div className="flex flex-col items-center justify-center h-full py-8">
              <motion.div
                animate={isRecalculating ? {
                  scale: [1, 1.1, 1],
                  rotate: [0, 180, 360]
                } : {}}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                className={cn(
                  "h-20 w-20 rounded-full flex items-center justify-center mb-4",
                  isRecalculating 
                    ? "bg-gradient-to-br from-primary to-accent glow-cyan"
                    : "bg-primary/20"
                )}
              >
                <Brain className={cn(
                  "h-10 w-10",
                  isRecalculating ? "text-primary-foreground" : "text-primary"
                )} />
              </motion.div>
              
              <h3 className="font-semibold text-lg mb-2">
                {isRecalculating ? "AI Processing..." : "AI Engine Ready"}
              </h3>
              <p className="text-sm text-muted-foreground text-center max-w-xs">
                {isRecalculating 
                  ? "Analyzing your health metrics and generating personalized meal recommendations"
                  : "Click 'Recalculate Plan' to generate AI-optimized meal suggestions based on your deviations"
                }
              </p>

              {isRecalculating && (
                <div className="mt-4 flex items-center gap-2 text-primary">
                  <Sparkles className="h-4 w-4 animate-pulse" />
                  <span className="text-sm">Consulting Clinical Rule Engine...</span>
                </div>
              )}
            </div>
          </BentoCard>

          {/* AI Generated Meal Plan */}
          <AnimatePresence>
            {showPlan && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="col-span-full"
              >
                <BentoCard colSpan={3}>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                      <ChefHat className="h-5 w-5 text-accent" />
                      <h2 className="font-semibold text-lg">AI-Generated Meal Plan</h2>
                    </div>
                    <Badge className="bg-accent/20 text-accent border-accent/30">
                      <Sparkles className="mr-1 h-3 w-3" />
                      Generated by NutriLoop AI
                    </Badge>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    {aiMealSuggestions.map((meal, index) => (
                      <motion.div
                        key={meal.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.15 }}
                        className={cn(
                          "relative p-4 rounded-xl border transition-all",
                          approvedMeals.includes(meal.id)
                            ? "border-accent bg-accent/10"
                            : "border-border hover:border-primary/30"
                        )}
                      >
                        {/* Confidence Badge */}
                        <div className="absolute top-3 right-3">
                          <Badge variant="outline" className="text-xs">
                            {meal.confidence}% Match
                          </Badge>
                        </div>

                        {/* Meal Info */}
                        <div className="flex items-center gap-2 mb-3">
                          <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                            <Utensils className="h-5 w-5 text-primary" />
                          </div>
                          <div>
                            <p className="font-medium text-sm">{meal.name}</p>
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {meal.time}
                            </p>
                          </div>
                        </div>

                        {/* Nutritional Info */}
                        <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                          <div className="p-2 rounded bg-secondary/50">
                            <span className="text-muted-foreground">Calories:</span>
                            <span className="ml-1 font-medium">{meal.calories}</span>
                          </div>
                          <div className="p-2 rounded bg-accent/10">
                            <span className="text-muted-foreground">Sodium:</span>
                            <span className="ml-1 font-medium text-accent">{meal.sodium}mg</span>
                          </div>
                          <div className="p-2 rounded bg-secondary/50">
                            <span className="text-muted-foreground">K:</span>
                            <span className="ml-1 font-medium">{meal.potassium}mg</span>
                          </div>
                          <div className="p-2 rounded bg-secondary/50">
                            <span className="text-muted-foreground">Protein:</span>
                            <span className="ml-1 font-medium">{meal.protein}g</span>
                          </div>
                        </div>

                        {/* Tags */}
                        <div className="flex flex-wrap gap-1 mb-3">
                          {meal.tags.map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>

                        {/* Explainability Tooltip */}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-1 text-xs text-primary cursor-help mb-3">
                              <Info className="h-3 w-3" />
                              <span>Why this meal?</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs glass">
                            <p className="text-sm">{meal.explanation}</p>
                          </TooltipContent>
                        </Tooltip>

                        {/* Approval Button */}
                        <Button
                          variant={approvedMeals.includes(meal.id) ? "default" : "outline"}
                          size="sm"
                          className={cn(
                            "w-full",
                            approvedMeals.includes(meal.id) && "bg-accent hover:bg-accent/90"
                          )}
                          onClick={() => toggleMealApproval(meal.id)}
                        >
                          {approvedMeals.includes(meal.id) ? (
                            <>
                              <Check className="mr-2 h-4 w-4" />
                              Approved
                            </>
                          ) : (
                            <>
                              <ArrowRight className="mr-2 h-4 w-4" />
                              Add to Plan
                            </>
                          )}
                        </Button>
                      </motion.div>
                    ))}
                  </div>

                  {/* Submit Plan */}
                  {approvedMeals.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="mt-6 flex items-center justify-between p-4 rounded-lg bg-accent/10 border border-accent/30"
                    >
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-accent" />
                        <span className="font-medium">
                          {approvedMeals.length} meal{approvedMeals.length > 1 ? "s" : ""} selected
                        </span>
                      </div>
                      <Button className="bg-accent hover:bg-accent/90 glow-emerald">
                        Submit for Supervisor Approval
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </motion.div>
                  )}
                </BentoCard>
              </motion.div>
            )}
          </AnimatePresence>

          {/* How It Works */}
          <BentoCard colSpan={3}>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-lg">How the AI Engine Works</h2>
            </div>

            <div className="grid md:grid-cols-4 gap-4">
              {[
                { icon: AlertTriangle, title: "Deviation Detection", desc: "Monitors nutrient intake against IFCT 2017 limits" },
                { icon: Brain, title: "AI Analysis", desc: "Generative AI processes your health profile and deviations" },
                { icon: ChefHat, title: "Meal Generation", desc: "Creates personalized suggestions from 6000+ Indian dishes" },
                { icon: ShieldCheck, title: "Safety Validation", desc: "Clinical Rule Engine validates all recommendations" },
              ].map((step, index) => (
                <div key={step.title} className="flex flex-col items-center text-center p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/20 mb-3">
                    <step.icon className="h-6 w-6 text-primary" />
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-muted-foreground">Step {index + 1}</span>
                  </div>
                  <h3 className="font-medium text-sm mb-1">{step.title}</h3>
                  <p className="text-xs text-muted-foreground">{step.desc}</p>
                </div>
              ))}
            </div>
          </BentoCard>
        </BentoGrid>
      </TooltipProvider>
    </DashboardLayout>
  )
}
