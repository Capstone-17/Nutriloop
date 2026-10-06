"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Sidebar } from "./sidebar"
import { NutriBot } from "./nutribot"
import { cn } from "@/lib/utils"

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [isChatOpen, setIsChatOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background gradient-mesh">
      <Sidebar onChatOpen={() => setIsChatOpen(true)} />
      
      <main className="pl-[72px] md:pl-[240px] transition-all duration-200">
        <div className="container mx-auto p-6 max-w-7xl">
          {children}
        </div>
      </main>

      {/* NutriBot Chat */}
      <AnimatePresence>
        {isChatOpen && (
          <NutriBot onClose={() => setIsChatOpen(false)} />
        )}
      </AnimatePresence>

      {/* Floating Chat Button for Mobile */}
      <button
        onClick={() => setIsChatOpen(true)}
        className={cn(
          "fixed bottom-6 right-6 z-50 md:hidden",
          "flex h-14 w-14 items-center justify-center rounded-full",
          "bg-gradient-to-br from-primary to-accent text-primary-foreground",
          "shadow-lg glow-cyan transition-transform hover:scale-105",
          isChatOpen && "hidden"
        )}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </button>
    </div>
  )
}
