"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface HealthGaugeProps {
  label: string
  value: number
  maxValue: number
  unit: string
  status: "normal" | "warning" | "danger"
  icon: React.ReactNode
}

const statusConfig = {
  normal: {
    color: "text-accent",
    bgColor: "bg-accent/20",
    strokeColor: "stroke-accent",
    glowClass: "glow-emerald",
  },
  warning: {
    color: "text-chart-3",
    bgColor: "bg-chart-3/20",
    strokeColor: "stroke-chart-3",
    glowClass: "",
  },
  danger: {
    color: "text-destructive",
    bgColor: "bg-destructive/20",
    strokeColor: "stroke-destructive",
    glowClass: "",
  },
}

export function HealthGauge({
  label,
  value,
  maxValue,
  unit,
  status,
  icon,
}: HealthGaugeProps) {
  const config = statusConfig[status]
  const percentage = Math.min((value / maxValue) * 100, 100)
  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="flex flex-col items-center p-4">
      <div className="relative h-32 w-32">
        {/* Background circle */}
        <svg className="absolute inset-0 h-full w-full -rotate-90">
          <circle
            cx="64"
            cy="64"
            r="45"
            fill="none"
            strokeWidth="8"
            className="stroke-muted/30"
          />
          <motion.circle
            cx="64"
            cy="64"
            r="45"
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            className={cn(config.strokeColor)}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: "easeOut" }}
            style={{
              strokeDasharray: circumference,
            }}
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className={cn("mb-1", config.color)}>{icon}</div>
          <motion.span
            className={cn("text-2xl font-bold", config.color)}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            {value}
          </motion.span>
          <span className="text-xs text-muted-foreground">{unit}</span>
        </div>
      </div>

      <div className="mt-3 text-center">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium mt-1",
            config.bgColor,
            config.color
          )}
        >
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      </div>
    </div>
  )
}
