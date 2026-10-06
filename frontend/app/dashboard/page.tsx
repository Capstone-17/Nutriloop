"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  Droplets,
  Heart,
  ShieldCheck,
  Soup,
  TrendingUp,
  Zap,
} from "lucide-react"
import { DashboardLayout } from "@/components/dashboard/dashboard-layout"
import { BentoCard, BentoGrid } from "@/components/dashboard/bento-card"
import { HealthGauge } from "@/components/dashboard/health-gauge"
import { MedicalSnapshot } from "@/components/dashboard/medical-snapshot"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import Link from "next/link"
import { fetchDashboardRiskSummary } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

const defaultPatientData = {
  age: 58,
  bmi: 30.1,
  activityLevel: "Light" as const,
  diseases: ["Diabetes", "Hypertension"],
}

const defaultMetrics = {
  glucose: { value: 168, max: 180, unit: "mg/dL", status: "warning" as const },
  bloodPressure: { systolic: 146, diastolic: 90, status: "warning" as const },
  creatinine: { value: 1.1, max: 1.5, unit: "mg/dL", status: "normal" as const },
  urea: { value: 38, max: 50, unit: "mg/dL", status: "normal" as const },
}

const defaultMeals = [
  { name: "Breakfast - Oats with Almonds", time: "8:30 AM", calories: 320, status: "safe" },
  { name: "Lunch - Dal Chawal", time: "1:00 PM", calories: 450, status: "warning" },
  { name: "Snack - Apple", time: "4:30 PM", calories: 95, status: "safe" },
]

const defaultNutrientLimits = {
  sodium: { current: 1420, limit: 2000, unit: "mg" },
  potassium: { current: 2100, limit: 3000, unit: "mg" },
  protein: { current: 45, limit: 60, unit: "g" },
  carbs: { current: 180, limit: 250, unit: "g" },
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [riskSummary, setRiskSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    async function loadRiskSummary() {
      try {
        const profile = user?.profile
        const diseases = profile?.selectedDiseases?.length ? profile.selectedDiseases : ["diabetes"]
        const reports = await Promise.all(
          diseases.map((disease) => fetchDashboardRiskSummary(profile, disease as "ckd" | "hypertension" | "diabetes", user?.id))
        )
        const data = reports[0]
        if (isMounted) {
          setRiskSummary({ ...data, reports })
          setLoading(false)
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Unknown backend error")
          setLoading(false)
        }
      }
    }

    loadRiskSummary()

    return () => {
      isMounted = false
    }
  }, [user?.id, user?.profile])

  const profile = user?.profile
  const bmi = profile ? profile.weight / Math.pow(profile.height / 100, 2) : 30.1
  const patientData = profile
    ? { age: profile.age, bmi: Number(bmi.toFixed(1)), activityLevel: (profile.activityLevel[0].toUpperCase() + profile.activityLevel.slice(1)) as "Light" | "Sedentary" | "Moderate" | "Active", diseases: profile.selectedDiseases.map((disease) => disease[0].toUpperCase() + disease.slice(1)) }
    : defaultPatientData
  const healthMetrics = riskSummary
    ? {
        glucose: { value: profile?.healthMetrics.glucose ?? Math.round((riskSummary.risk_score ?? 0.72) * 180), max: 180, unit: "mg/dL", status: "warning" as const },
        bloodPressure: { systolic: profile?.healthMetrics.systolic ?? 146, diastolic: profile?.healthMetrics.diastolic ?? 90, status: "warning" as const },
        creatinine: { value: profile?.healthMetrics.creatinine ?? 1.1, max: 1.5, unit: "mg/dL", status: "normal" as const },
        urea: { value: profile?.healthMetrics.urea ?? 38, max: 50, unit: "mg/dL", status: "normal" as const },
      }
    : defaultMetrics
  const nutrientLimits = defaultNutrientLimits
  const recentMeals = defaultMeals

  return (
    <DashboardLayout>
      {/* Header */}
      <header className="mb-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome back, <span className="text-primary">{user?.name || "Patient"}</span>
          </h1>
          <p className="text-muted-foreground mt-1">
            Your personalized health dashboard for chronic disease management
          </p>
        </motion.div>
      </header>

      <BentoGrid className="gap-4">
        {/* Health Gauges - Real-time Monitoring */}
        <BentoCard colSpan={2} className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-lg">Real-time Health Monitor</h2>
            </div>
            <Badge variant="outline" className="text-primary border-primary/30">
              <span className="mr-1 h-2 w-2 rounded-full bg-primary animate-pulse inline-block" />
              Live
            </Badge>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <HealthGauge
              label="Blood Glucose"
              value={healthMetrics.glucose.value}
              maxValue={healthMetrics.glucose.max}
              unit={healthMetrics.glucose.unit}
              status={healthMetrics.glucose.status}
              icon={<Droplets className="h-5 w-5" />}
            />
            <HealthGauge
              label="Blood Pressure"
              value={healthMetrics.bloodPressure.systolic}
              maxValue={180}
              unit={`${healthMetrics.bloodPressure.systolic}/${healthMetrics.bloodPressure.diastolic}`}
              status={healthMetrics.bloodPressure.status}
              icon={<Heart className="h-5 w-5" />}
            />
            <HealthGauge
              label="Creatinine"
              value={healthMetrics.creatinine.value}
              maxValue={healthMetrics.creatinine.max}
              unit={healthMetrics.creatinine.unit}
              status={healthMetrics.creatinine.status}
              icon={<Activity className="h-5 w-5" />}
            />
            <HealthGauge
              label="Blood Urea"
              value={healthMetrics.urea.value}
              maxValue={healthMetrics.urea.max}
              unit={healthMetrics.urea.unit}
              status={healthMetrics.urea.status}
              icon={<Zap className="h-5 w-5" />}
            />
          </div>
        </BentoCard>

        {/* Medical Snapshot */}
        <BentoCard rowSpan={2}>
          <MedicalSnapshot data={patientData} />
        </BentoCard>

        {/* Nutrient Tracking */}
        <BentoCard colSpan={2}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-accent" />
              <h2 className="font-semibold text-lg">Daily Nutrient Limits</h2>
            </div>
            <span className="text-xs text-muted-foreground">Based on IFCT 2017</span>
          </div>

          <div className="space-y-4">
            {Object.entries(nutrientLimits).map(([key, data]) => {
              const percentage = (data.current / data.limit) * 100
              const isWarning = percentage > 70
              const isDanger = percentage > 90
              
              return (
                <div key={key} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize font-medium">{key}</span>
                    <span className={`${isDanger ? "text-destructive" : isWarning ? "text-chart-3" : "text-muted-foreground"}`}>
                      {data.current} / {data.limit} {data.unit}
                    </span>
                  </div>
                  <Progress 
                    value={percentage} 
                    className={`h-2 ${isDanger ? "[&>div]:bg-destructive" : isWarning ? "[&>div]:bg-chart-3" : "[&>div]:bg-accent"}`}
                  />
                </div>
              )
            })}
          </div>
        </BentoCard>

        {/* Recent Meals */}
        <BentoCard colSpan={2}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Soup className="h-5 w-5 text-accent" />
              <h2 className="font-semibold text-lg">Recent Meals</h2>
            </div>
            <Link href="/meals">
              <Button variant="ghost" size="sm" className="text-primary">
                View All <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </Link>
          </div>

          <div className="space-y-3">
            {riskSummary?.reports?.slice(1).map((report: any) => (
              <div key={report.disease} className="rounded-lg border border-primary/15 bg-primary/5 p-3 text-sm">
                <span className="font-medium capitalize">{report.disease}</span>: <span className="capitalize">{report.risk_level}</span> risk ({(report.risk_score * 100).toFixed(1)}%)
              </div>
            ))}
            {recentMeals.map((meal, index) => (
              <motion.div
                key={meal.name}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 hover:bg-secondary/80 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`h-2 w-2 rounded-full ${meal.status === "safe" ? "bg-accent" : "bg-chart-3"}`} />
                  <div>
                    <p className="font-medium text-sm">{meal.name}</p>
                    <p className="text-xs text-muted-foreground">{meal.time}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">{meal.calories} kcal</span>
                  {meal.status === "warning" && (
                    <AlertTriangle className="h-4 w-4 text-chart-3" />
                  )}
                  {meal.status === "safe" && (
                    <ShieldCheck className="h-4 w-4 text-accent" />
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </BentoCard>

        {/* AI Recommendations */}
        <BentoCard gradient>
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-lg">AI Insight</h2>
          </div>
          
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-chart-3/10 border border-chart-3/30">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-chart-3 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-chart-3">Sodium Alert</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Your lunch contained high sodium. Consider low-sodium options for dinner.
                  </p>
                </div>
              </div>
            </div>
            
            <Link href="/ai-plan">
              <Button className="w-full bg-gradient-to-r from-primary to-accent hover:opacity-90 glow-cyan">
                <Brain className="mr-2 h-4 w-4" />
                Recalculate Meal Plan
              </Button>
            </Link>
          </div>
        </BentoCard>

        {/* Quick Stats */}
        <BentoCard>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Today&apos;s Progress</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Calories</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold">865 / 1800</span>
                <TrendingUp className="h-4 w-4 text-accent" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Water</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold">6 / 8 glasses</span>
                <TrendingUp className="h-4 w-4 text-primary" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Compliance</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-accent">92%</span>
                <ShieldCheck className="h-4 w-4 text-accent" />
              </div>
            </div>
          </div>
        </BentoCard>

        {/* Supervisor Alert */}
        <BentoCard>
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <h3 className="font-medium">Supervisor Mode</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            Enable clinician oversight for AI-generated meal plans
          </p>
          <Link href="/supervisor">
            <Button variant="outline" className="w-full border-accent/30 text-accent hover:bg-accent/10">
              Open Supervisor Dashboard
            </Button>
          </Link>
        </BentoCard>
      </BentoGrid>
    </DashboardLayout>
  )
}
