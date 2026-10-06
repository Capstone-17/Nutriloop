"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  Activity,
  Brain,
  ChefHat,
  ChevronLeft,
  ChevronRight,
  Home,
  LogOut,
  MessageSquare,
  Settings,
  ShieldCheck,
  Soup,
  User,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useAuth } from "@/lib/auth-context"

const navItems = [
  { href: "/dashboard", icon: Home, label: "Dashboard", color: "text-primary" },
  { href: "/dashboard/profile", icon: User, label: "Risk Profile", color: "text-primary" },
  { href: "/dashboard/meals", icon: Soup, label: "Meal Log", color: "text-accent" },
  { href: "/dashboard/ai-plan", icon: Brain, label: "AI Recalculation", color: "text-primary" },
  { href: "/dashboard/supervisor", icon: ShieldCheck, label: "Supervisor", color: "text-accent" },
]

const bottomNavItems = [
  { href: "/dashboard/settings", icon: Settings, label: "Settings" },
]

interface SidebarProps {
  onChatOpen?: () => void
}

export function Sidebar({ onChatOpen }: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuth()

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  return (
    <TooltipProvider delayDuration={0}>
      <motion.aside
        initial={false}
        animate={{ width: isCollapsed ? 72 : 240 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="fixed left-0 top-0 z-40 flex h-screen flex-col glass-sidebar"
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-sidebar-border/50">
          <AnimatePresence mode="wait">
            {!isCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 glow-cyan">
                  <Zap className="h-5 w-5 text-primary" />
                </div>
                <span className="font-semibold text-lg tracking-tight">NutriLoop</span>
              </motion.div>
            )}
          </AnimatePresence>
          {isCollapsed && (
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 mx-auto">
              <Zap className="h-5 w-5 text-primary" />
            </div>
          )}
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 space-y-1 p-3">
          <div className="mb-4">
            {!isCollapsed && (
              <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Main
              </p>
            )}
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                        isActive
                          ? "bg-primary/10 text-primary glow-cyan"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                      )}
                    >
                      <item.icon
                        className={cn(
                          "h-5 w-5 shrink-0",
                          isActive ? item.color : ""
                        )}
                      />
                      <AnimatePresence mode="wait">
                        {!isCollapsed && (
                          <motion.span
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: "auto" }}
                            exit={{ opacity: 0, width: 0 }}
                            className="truncate"
                          >
                            {item.label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </Link>
                  </TooltipTrigger>
                  {isCollapsed && (
                    <TooltipContent side="right" className="glass">
                      {item.label}
                    </TooltipContent>
                  )}
                </Tooltip>
              )
            })}
          </div>

          {/* AI Assistant Button */}
          <div className="border-t border-sidebar-border/50 pt-4">
            {!isCollapsed && (
              <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                AI Assistant
              </p>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  onClick={onChatOpen}
                  className={cn(
                    "w-full justify-start gap-3 px-3 py-2.5 h-auto",
                    "bg-gradient-to-r from-primary/10 to-accent/10 hover:from-primary/20 hover:to-accent/20",
                    "border border-primary/20 text-foreground"
                  )}
                >
                  <MessageSquare className="h-5 w-5 shrink-0 text-primary" />
                  {!isCollapsed && <span>NutriBot</span>}
                </Button>
              </TooltipTrigger>
              {isCollapsed && (
                <TooltipContent side="right" className="glass">
                  NutriBot Assistant
                </TooltipContent>
              )}
            </Tooltip>
          </div>
        </nav>

        {/* Bottom Navigation */}
        <div className="border-t border-sidebar-border/50 p-3 space-y-2">
          {bottomNavItems.map((item) => {
            const isActive = pathname === item.href
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                    {!isCollapsed && <span>{item.label}</span>}
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right" className="glass">
                    {item.label}
                  </TooltipContent>
                )}
              </Tooltip>
            )
          })}

          {/* Logout Button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleLogout}
                variant="ghost"
                className="w-full justify-start gap-3 px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-all duration-200"
              >
                <LogOut className="h-5 w-5 shrink-0" />
                {!isCollapsed && <span>Logout</span>}
              </Button>
            </TooltipTrigger>
            {isCollapsed && (
              <TooltipContent side="right" className="glass">
                Logout
              </TooltipContent>
            )}
          </Tooltip>

          {/* Collapse Button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full mt-2 justify-center text-muted-foreground hover:text-foreground"
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
        </div>
      </motion.aside>
    </TooltipProvider>
  )
}
