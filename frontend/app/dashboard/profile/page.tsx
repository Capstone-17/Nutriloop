"use client"

import { useState, useEffect, useCallback } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { motion } from "framer-motion"
import {
  Activity,
  CheckCircle2,
  Droplets,
  Heart,
  Save,
  Zap,
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
import * as api from "@/lib/api"

const diseases = [
  { id: "diabetes", label: "Type 2 Diabetes (T2DM)", color: "bg-chart-4/20 text-chart-4 border-chart-4/30" },
  { id: "ckd", label: "Chronic Kidney Disease (CKD)", color: "bg-primary/20 text-primary border-primary/30" },
  { id: "hypertension", label: "Hypertension", color: "bg-destructive/20 text-destructive border-destructive/30" },
]

const activityLevels = [
  { id: "sedentary", label: "Sedentary (little exercise)" },
  { id: "light", label: "Light (1-3 days/week)" },
  { id: "moderate", label: "Moderate (3-5 days/week)" },
  { id: "active", label: "Active (6-7 days/week)" },
  { id: "veryactive", label: "Very Active (2x per day)" },
]

export default function ProfilePage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user, updateProfile } = useAuth()
  const isOnboarding = searchParams.get("onboarding") === "1"

  const [formData, setFormData] = useState({
    age: user?.profile?.age || 45,
    sex: (user?.profile?.sex || "male") as "male" | "female",
    weight: user?.profile?.weight || 75,
    height: user?.profile?.height || 170,
    activityLevel: user?.profile?.activityLevel || "light",
    selectedDiseases: user?.profile?.selectedDiseases || ["diabetes"],
  })

  const [healthMetrics, setHealthMetrics] = useState({
    glucose: user?.profile?.healthMetrics?.glucose || 120,
    systolic: user?.profile?.healthMetrics?.systolic || 120,
    diastolic: user?.profile?.healthMetrics?.diastolic || 80,
    creatinine: user?.profile?.healthMetrics?.creatinine || 1.0,
    urea: user?.profile?.healthMetrics?.urea || 40,
  })

  const [predictions, setPredictions] = useState<Record<string, any>>({})
  const [loadingPredictions, setLoadingPredictions] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const bmi = Number((formData.weight / Math.pow(formData.height / 100, 2)).toFixed(1))

  const fetchPredictions = useCallback(async () => {
    if (formData.selectedDiseases.length === 0) {
      setPredictions({})
      return
    }

    setLoadingPredictions(true)
    try {
      const results: Record<string, any> = {}
      
      for (const disease of formData.selectedDiseases) {
        const rawInputs: Record<string, unknown> = {
          age_years: formData.age,
          sex: formData.sex,
          body_mass_index: bmi,
          current_smoker: false,
          diagnosed_diabetes: formData.selectedDiseases.includes("diabetes"),
          diagnosed_hypertension: formData.selectedDiseases.includes("hypertension"),
          systolic_bp_mmhg: healthMetrics.systolic,
          diastolic_bp_mmhg: healthMetrics.diastolic,
          fasting_glucose_mg_dl: healthMetrics.glucose,
        }

        if (disease === "hypertension") {
          rawInputs.education_level = 5
          rawInputs.cigarettes_per_day = 0
          rawInputs.prior_stroke = false
        }

        try {
          const result = await api.predictRiskRaw({
            disease: disease as api.DiseaseType,
            raw_inputs: rawInputs,
            user_id: user?.id,
          })
          results[disease] = result
        } catch (err) {
          console.error(`Failed to predict ${disease}:`, err)
          results[disease] = { error: true, message: String(err) }
        }
      }
      
      setPredictions(results)
    } finally {
      setLoadingPredictions(false)
    }
  }, [formData.age, formData.sex, bmi, healthMetrics, formData.selectedDiseases, user?.id])

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPredictions()
    }, 500)
    return () => clearTimeout(timer)
  }, [fetchPredictions])

  const toggleDisease = (diseaseId: string) => {
    setFormData(prev => ({
      ...prev,
      selectedDiseases: prev.selectedDiseases.includes(diseaseId)
        ? prev.selectedDiseases.filter(d => d !== diseaseId)
        : [...prev.selectedDiseases, diseaseId]
    }))
  }

  const handleSaveProfile = async () => {
    if (formData.selectedDiseases.length === 0) return
    setIsSaving(true)
    try {
      await updateProfile({
        ...formData,
        healthMetrics,
      })
      setSaveSuccess(true)
      setTimeout(() => {
        setSaveSuccess(false)
        if (isOnboarding) {
          router.push("/dashboard")
        }
      }, 1500)
    } finally {
      setIsSaving(false)
    }
  }

  const getRiskColor = (riskLevel?: string) => {
    if (!riskLevel) return "text-muted-foreground"
    if (riskLevel === "low") return "text-green-600"
    if (riskLevel === "moderate") return "text-yellow-600"
    return "text-red-600"
  }

  return (
    <DashboardLayout>
      <header className="mb-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-3xl font-bold tracking-tight">
            {isOnboarding ? "Complete Your Health Profile" : "Edit My Profile"}
          </h1>
          <p className="text-muted-foreground mt-1">
            {isOnboarding
              ? "Help us understand your health to provide personalized recommendations"
              : "Update your health parameters for personalized AI recommendations"}
          </p>
        </motion.div>
      </header>

      {saveSuccess && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4 flex items-center gap-3"
        >
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <p className="text-green-800 font-medium">
            {isOnboarding ? "Profile created! Redirecting to dashboard..." : "Profile saved successfully!"}
          </p>
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              Personal Info
            </h2>

            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Age (years)</Label>
                <Input
                  type="number"
                  min="18"
                  max="100"
                  value={formData.age}
                  onChange={(e) => setFormData(p => ({ ...p, age: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>

              <div>
                <Label className="text-sm font-medium">Sex</Label>
                <select
                  value={formData.sex}
                  onChange={(e) => setFormData(p => ({ ...p, sex: e.target.value as "male" | "female" }))}
                  className="w-full mt-1 rounded-lg border border-primary/20 bg-background/60 px-3 py-2 text-foreground"
                >
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm font-medium">Weight (kg)</Label>
                  <Input
                    type="number"
                    min="30"
                    max="300"
                    step="0.1"
                    value={formData.weight}
                    onChange={(e) => setFormData(p => ({ ...p, weight: Number(e.target.value) }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-sm font-medium">Height (cm)</Label>
                  <Input
                    type="number"
                    min="100"
                    max="250"
                    value={formData.height}
                    onChange={(e) => setFormData(p => ({ ...p, height: Number(e.target.value) }))}
                    className="mt-1"
                  />
                </div>
              </div>

              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <div className="text-sm text-muted-foreground">BMI</div>
                <div className="text-2xl font-bold text-primary">{bmi}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {bmi < 18.5 ? "Underweight" : bmi < 25 ? "Normal" : bmi < 30 ? "Overweight" : "Obese"}
                </div>
              </div>
            </div>
          </BentoCard>

          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Zap className="h-5 w-5 text-accent" />
              Activity Level
            </h2>

            <div className="space-y-2">
              {activityLevels.map((level) => (
                <button
                  key={level.id}
                  onClick={() => setFormData(p => ({ ...p, activityLevel: level.id }))}
                  className={cn(
                    "w-full text-left p-3 rounded-lg border-2 transition-all",
                    formData.activityLevel === level.id
                      ? "border-accent bg-accent/10"
                      : "border-secondary/50 hover:border-accent/50"
                  )}
                >
                  <div className="flex items-center gap-2">
                    {formData.activityLevel === level.id && (
                      <CheckCircle2 className="h-4 w-4 text-accent" />
                    )}
                    <span className="text-sm font-medium">{level.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </BentoCard>

          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4">Conditions</h2>
            <div className="space-y-2">
              {diseases.map((disease) => (
                <button
                  key={disease.id}
                  onClick={() => toggleDisease(disease.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg border-2 transition-all",
                    formData.selectedDiseases.includes(disease.id)
                      ? `${disease.color} border-current`
                      : "border-secondary/50 hover:border-secondary"
                  )}
                >
                  <div className="flex items-center gap-2">
                    {formData.selectedDiseases.includes(disease.id) && (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    <span className="text-sm font-medium">{disease.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </BentoCard>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <BentoCard className="p-6">
            <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Droplets className="h-5 w-5 text-primary" />
              Health Metrics
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <Label className="text-sm font-medium">Blood Glucose (mg/dL)</Label>
                <Input
                  type="number"
                  min="40"
                  max="450"
                  value={healthMetrics.glucose}
                  onChange={(e) => setHealthMetrics(p => ({ ...p, glucose: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>

              <div>
                <Label className="text-sm font-medium">Systolic BP (mmHg)</Label>
                <Input
                  type="number"
                  min="70"
                  max="260"
                  value={healthMetrics.systolic}
                  onChange={(e) => setHealthMetrics(p => ({ ...p, systolic: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>

              <div>
                <Label className="text-sm font-medium">Diastolic BP (mmHg)</Label>
                <Input
                  type="number"
                  min="40"
                  max="160"
                  value={healthMetrics.diastolic}
                  onChange={(e) => setHealthMetrics(p => ({ ...p, diastolic: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>

              <div>
                <Label className="text-sm font-medium">Creatinine (mg/dL)</Label>
                <Input
                  type="number"
                  min="0.5"
                  max="5.0"
                  step="0.1"
                  value={healthMetrics.creatinine}
                  onChange={(e) => setHealthMetrics(p => ({ ...p, creatinine: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>

              <div>
                <Label className="text-sm font-medium">Blood Urea (mg/dL)</Label>
                <Input
                  type="number"
                  min="5"
                  max="200"
                  value={healthMetrics.urea}
                  onChange={(e) => setHealthMetrics(p => ({ ...p, urea: Number(e.target.value) }))}
                  className="mt-1"
                />
              </div>
            </div>
          </BentoCard>

          <BentoCard className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <Heart className="h-5 w-5 text-destructive" />
                Risk Predictions
              </h2>
              {loadingPredictions && (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              )}
            </div>

            {formData.selectedDiseases.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                Select at least one condition to see risk predictions
              </div>
            ) : (
              <div className="space-y-3">
                {formData.selectedDiseases.map((disease) => {
                  const prediction = predictions[disease]
                  return (
                    <motion.div
                      key={disease}
                      initial={{ opacity: 0, y: -5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-4 rounded-lg border border-secondary/50 bg-secondary/30"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="font-semibold capitalize">{disease}</p>
                          {prediction?.model_name && (
                            <p className="text-xs text-muted-foreground">{prediction.model_name}</p>
                          )}
                        </div>
                        {prediction?.risk_level && (
                          <Badge className={cn(
                            "capitalize",
                            prediction.risk_level === "low" && "bg-green-500/20 text-green-700 border-green-500/30",
                            prediction.risk_level === "moderate" && "bg-yellow-500/20 text-yellow-700 border-yellow-500/30",
                            prediction.risk_level === "high" && "bg-red-500/20 text-red-700 border-red-500/30",
                          )}>
                            {prediction.risk_level}
                          </Badge>
                        )}
                      </div>

                      {prediction?.error ? (
                        <div className="text-sm text-red-600">Failed to load prediction</div>
                      ) : prediction?.risk_score !== undefined ? (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">Risk Score:</span>
                            <span className={cn("text-lg font-bold", getRiskColor(prediction.risk_level))}>
                              {(prediction.risk_score * 100).toFixed(1)}%
                            </span>
                          </div>
                          {prediction.thresholds && (
                            <div className="text-xs text-muted-foreground">
                              Moderate: {(prediction.thresholds.moderate * 100).toFixed(1)}% | High: {(prediction.thresholds.high * 100).toFixed(1)}%
                            </div>
                          )}
                          {prediction.top_factors && prediction.top_factors.length > 0 && (
                            <div className="text-xs mt-2">
                              <p className="font-medium text-foreground mb-1">Top Factors:</p>
                              <div className="flex flex-wrap gap-1">
                                {prediction.top_factors.slice(0, 3).map((factor: any, i: number) => (
                                  <Badge key={i} variant="outline" className="text-xs capitalize">
                                    {factor.feature}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-sm text-muted-foreground">Loading prediction...</div>
                      )}
                    </motion.div>
                  )
                })}
              </div>
            )}
          </BentoCard>

          <div className="flex gap-3">
            {isOnboarding && (
              <Button
                variant="outline"
                onClick={() => router.push("/dashboard")}
                disabled={isSaving}
                className="flex-1"
              >
                Skip for Now
              </Button>
            )}
            <Button
              onClick={handleSaveProfile}
              disabled={isSaving || formData.selectedDiseases.length === 0}
              className="flex-1 gap-2"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  {isOnboarding ? "Complete Setup & Continue" : "Save Profile"}
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
