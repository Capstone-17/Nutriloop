"use client"

import { User, Activity, Scale, Dumbbell } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface PatientData {
  age: number
  bmi: number
  activityLevel: "Sedentary" | "Light" | "Moderate" | "Active"
  diseases: string[]
}

interface MedicalSnapshotProps {
  data: PatientData
}

const activityColors = {
  Sedentary: "bg-destructive/20 text-destructive",
  Light: "bg-chart-3/20 text-chart-3",
  Moderate: "bg-primary/20 text-primary",
  Active: "bg-accent/20 text-accent",
}

const diseaseColors: Record<string, string> = {
  "T2DM": "bg-chart-4/20 text-chart-4 border-chart-4/30",
  "CKD": "bg-primary/20 text-primary border-primary/30",
  "Hypertension": "bg-destructive/20 text-destructive border-destructive/30",
}

export function MedicalSnapshot({ data }: MedicalSnapshotProps) {
  const getBMIStatus = (bmi: number) => {
    if (bmi < 18.5) return { label: "Underweight", color: "text-chart-3" }
    if (bmi < 25) return { label: "Normal", color: "text-accent" }
    if (bmi < 30) return { label: "Overweight", color: "text-chart-3" }
    return { label: "Obese", color: "text-destructive" }
  }

  const bmiStatus = getBMIStatus(data.bmi)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <User className="h-5 w-5 text-primary" />
        <h3 className="font-semibold text-lg">Medical Snapshot</h3>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Age */}
        <div className="glass rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Age</span>
          </div>
          <p className="text-2xl font-bold">{data.age}</p>
          <p className="text-xs text-muted-foreground">years</p>
        </div>

        {/* BMI */}
        <div className="glass rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Scale className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">BMI</span>
          </div>
          <p className="text-2xl font-bold">{data.bmi.toFixed(1)}</p>
          <p className={cn("text-xs font-medium", bmiStatus.color)}>
            {bmiStatus.label}
          </p>
        </div>
      </div>

      {/* Activity Level */}
      <div className="glass rounded-lg p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dumbbell className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Activity Level</span>
          </div>
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              activityColors[data.activityLevel]
            )}
          >
            {data.activityLevel}
          </span>
        </div>
      </div>

      {/* Diseases */}
      <div className="glass rounded-lg p-3">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Chronic Conditions</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {data.diseases.map((disease) => (
            <Badge
              key={disease}
              variant="outline"
              className={cn(
                "font-medium",
                diseaseColors[disease] || "bg-muted/20 text-muted-foreground"
              )}
            >
              {disease}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  )
}
