"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface BentoCardProps {
  children: React.ReactNode
  className?: string
  colSpan?: 1 | 2 | 3
  rowSpan?: 1 | 2
  gradient?: boolean
}

export function BentoCard({
  children,
  className,
  colSpan = 1,
  rowSpan = 1,
  gradient = false,
}: BentoCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn(
        "glass rounded-xl p-5 transition-all duration-300",
        "hover:border-primary/30",
        gradient && "gradient-mesh",
        colSpan === 2 && "md:col-span-2",
        colSpan === 3 && "md:col-span-3",
        rowSpan === 2 && "md:row-span-2",
        className
      )}
    >
      {children}
    </motion.div>
  )
}

interface BentoGridProps {
  children: React.ReactNode
  className?: string
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid gap-4 md:grid-cols-2 lg:grid-cols-3",
        className
      )}
    >
      {children}
    </div>
  )
}
