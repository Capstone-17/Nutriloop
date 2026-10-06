"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertTriangle,
  Bell,
  Check,
  ChevronDown,
  Clock,
  Eye,
  FileText,
  Shield,
  ShieldCheck,
  User,
  Users,
  X,
} from "lucide-react"
import { DashboardLayout } from "@/components/dashboard/dashboard-layout"
import { BentoCard, BentoGrid } from "@/components/dashboard/bento-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

// Mock pending approvals
const pendingApprovals = [
  {
    id: 1,
    patientName: "Patient A",
    patientId: "PT-001",
    type: "meal_plan",
    title: "AI-Generated Dinner Plan",
    description: "Low-sodium meal plan generated after high sodium lunch deviation",
    meals: [
      { name: "Steamed Moong Dal with Jeera Rice", sodium: 180, calories: 320 },
      { name: "Cucumber Raita", sodium: 95, calories: 150 },
    ],
    timestamp: "2 hours ago",
    priority: "high",
    aiConfidence: 94,
  },
  {
    id: 2,
    patientName: "Patient B",
    patientId: "PT-002",
    type: "meal_plan",
    title: "Weekly Meal Adjustment",
    description: "Protein intake optimization for CKD Stage 3 management",
    meals: [
      { name: "Vegetable Upma", sodium: 120, calories: 180 },
      { name: "Mixed Vegetable Curry", sodium: 200, calories: 220 },
    ],
    timestamp: "5 hours ago",
    priority: "medium",
    aiConfidence: 88,
  },
]

// Mock alerts
const patientAlerts = [
  {
    id: 1,
    patientName: "Patient A",
    patientId: "PT-001",
    type: "sodium_exceeded",
    message: "Daily sodium limit exceeded by 280mg",
    timestamp: "1 hour ago",
    severity: "warning",
    acknowledged: false,
  },
  {
    id: 2,
    patientName: "Patient C",
    patientId: "PT-003",
    type: "glucose_spike",
    message: "Blood glucose reading: 186 mg/dL (above 180 threshold)",
    timestamp: "3 hours ago",
    severity: "critical",
    acknowledged: false,
  },
  {
    id: 3,
    patientName: "Patient B",
    patientId: "PT-002",
    type: "missed_meal",
    message: "Lunch not logged - reminder sent to patient",
    timestamp: "4 hours ago",
    severity: "info",
    acknowledged: true,
  },
]

// Mock patients
const patients = [
  {
    id: "PT-001",
    name: "Patient A",
    conditions: ["T2DM", "CKD Stage 2", "Hypertension"],
    compliance: 92,
    lastActive: "10 mins ago",
    status: "online",
  },
  {
    id: "PT-002",
    name: "Patient B",
    conditions: ["CKD Stage 3", "Hypertension"],
    compliance: 78,
    lastActive: "2 hours ago",
    status: "offline",
  },
  {
    id: "PT-003",
    name: "Patient C",
    conditions: ["T2DM", "Hypertension"],
    compliance: 85,
    lastActive: "30 mins ago",
    status: "online",
  },
]

export default function SupervisorPage() {
  const [supervisorMode, setSupervisorMode] = useState(true)
  const [expandedApproval, setExpandedApproval] = useState<number | null>(null)
  const [approvalDialog, setApprovalDialog] = useState<{ open: boolean; approval?: typeof pendingApprovals[0]; action?: "approve" | "reject" }>({ open: false })
  const [rejectionNote, setRejectionNote] = useState("")
  const [alerts, setAlerts] = useState(patientAlerts)
  const [approvals, setApprovals] = useState(pendingApprovals)

  const acknowledgeAlert = (alertId: number) => {
    setAlerts(prev => prev.map(alert => 
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ))
  }

  const handleApprovalAction = (action: "approve" | "reject") => {
    if (!approvalDialog.approval) return
    
    setApprovals(prev => prev.filter(a => a.id !== approvalDialog.approval!.id))
    setApprovalDialog({ open: false })
    setRejectionNote("")
  }

  const unacknowledgedAlerts = alerts.filter(a => !a.acknowledged)

  return (
    <DashboardLayout>
      <header className="mb-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                <span className="text-accent">Supervisor</span> Dashboard
              </h1>
              <p className="text-muted-foreground mt-1">
                Review and approve AI-generated meal plans for your patients
              </p>
            </div>
            <div className="flex items-center gap-3 glass px-4 py-2 rounded-lg">
              <Shield className={cn(
                "h-5 w-5 transition-colors",
                supervisorMode ? "text-accent" : "text-muted-foreground"
              )} />
              <Label htmlFor="supervisor-mode" className="cursor-pointer">
                Supervisor Mode
              </Label>
              <Switch
                id="supervisor-mode"
                checked={supervisorMode}
                onCheckedChange={setSupervisorMode}
              />
            </div>
          </div>
        </motion.div>
      </header>

      <BentoGrid>
        {/* Quick Stats */}
        <BentoCard>
          <div className="flex items-center gap-2 mb-4">
            <Users className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">Active Patients</h2>
          </div>
          <div className="text-4xl font-bold text-primary mb-2">
            {patients.filter(p => p.status === "online").length}
            <span className="text-lg font-normal text-muted-foreground">/{patients.length}</span>
          </div>
          <p className="text-sm text-muted-foreground">Currently being monitored</p>
        </BentoCard>

        <BentoCard>
          <div className="flex items-center gap-2 mb-4">
            <FileText className="h-5 w-5 text-chart-3" />
            <h2 className="font-semibold">Pending Approvals</h2>
          </div>
          <div className="text-4xl font-bold text-chart-3 mb-2">{approvals.length}</div>
          <p className="text-sm text-muted-foreground">AI plans awaiting review</p>
        </BentoCard>

        <BentoCard>
          <div className="flex items-center gap-2 mb-4">
            <Bell className="h-5 w-5 text-destructive" />
            <h2 className="font-semibold">Active Alerts</h2>
          </div>
          <div className="text-4xl font-bold text-destructive mb-2">{unacknowledgedAlerts.length}</div>
          <p className="text-sm text-muted-foreground">Require attention</p>
        </BentoCard>

        {/* Patient Overview */}
        <BentoCard colSpan={2}>
          <div className="flex items-center gap-2 mb-4">
            <Users className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-lg">Patient Overview</h2>
          </div>

          <div className="space-y-3">
            {patients.map((patient) => (
              <div
                key={patient.id}
                className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 hover:bg-secondary/80 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                      <User className="h-5 w-5 text-primary" />
                    </div>
                    <span className={cn(
                      "absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-background",
                      patient.status === "online" ? "bg-accent" : "bg-muted-foreground"
                    )} />
                  </div>
                  <div>
                    <p className="font-medium">{patient.name}</p>
                    <p className="text-xs text-muted-foreground">{patient.id} | {patient.lastActive}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-sm font-medium">Compliance</p>
                    <p className={cn(
                      "text-lg font-bold",
                      patient.compliance >= 90 ? "text-accent" :
                      patient.compliance >= 70 ? "text-chart-3" : "text-destructive"
                    )}>
                      {patient.compliance}%
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1 max-w-[200px]">
                    {patient.conditions.map((condition) => (
                      <Badge key={condition} variant="secondary" className="text-xs">
                        {condition}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </BentoCard>

        {/* Alerts */}
        <BentoCard rowSpan={2}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <h2 className="font-semibold text-lg">Patient Alerts</h2>
            </div>
            {unacknowledgedAlerts.length > 0 && (
              <Badge variant="destructive">
                {unacknowledgedAlerts.length} New
              </Badge>
            )}
          </div>

          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
            {alerts.map((alert) => (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className={cn(
                  "p-3 rounded-lg border transition-all",
                  alert.acknowledged 
                    ? "border-border bg-secondary/30 opacity-60"
                    : alert.severity === "critical"
                    ? "border-destructive/50 bg-destructive/10"
                    : alert.severity === "warning"
                    ? "border-chart-3/50 bg-chart-3/10"
                    : "border-primary/50 bg-primary/10"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className={cn(
                      "h-4 w-4 mt-0.5 shrink-0",
                      alert.severity === "critical" ? "text-destructive" :
                      alert.severity === "warning" ? "text-chart-3" : "text-primary"
                    )} />
                    <div>
                      <p className="font-medium text-sm">{alert.patientName}</p>
                      <p className="text-xs text-muted-foreground mb-1">{alert.message}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {alert.timestamp}
                      </p>
                    </div>
                  </div>
                  {!alert.acknowledged && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0 h-7 px-2"
                      onClick={() => acknowledgeAlert(alert.id)}
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </BentoCard>

        {/* Pending Approvals */}
        <BentoCard colSpan={2}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-accent" />
              <h2 className="font-semibold text-lg">Pending Approvals</h2>
            </div>
            <Badge variant="outline">
              {approvals.length} Pending
            </Badge>
          </div>

          {approvals.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <ShieldCheck className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>All meal plans have been reviewed</p>
            </div>
          ) : (
            <div className="space-y-3">
              {approvals.map((approval) => (
                <Collapsible
                  key={approval.id}
                  open={expandedApproval === approval.id}
                  onOpenChange={(open) => setExpandedApproval(open ? approval.id : null)}
                >
                  <div className={cn(
                    "rounded-lg border transition-all",
                    approval.priority === "high" ? "border-chart-3/50" : "border-border"
                  )}>
                    <CollapsibleTrigger asChild>
                      <button className="w-full p-4 flex items-center justify-between hover:bg-secondary/50 transition-colors rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                            <User className="h-5 w-5 text-primary" />
                          </div>
                          <div className="text-left">
                            <div className="flex items-center gap-2">
                              <p className="font-medium">{approval.title}</p>
                              {approval.priority === "high" && (
                                <Badge variant="outline" className="border-chart-3/50 text-chart-3 text-xs">
                                  High Priority
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {approval.patientName} | {approval.timestamp}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className="bg-primary/20 text-primary">
                            AI: {approval.aiConfidence}%
                          </Badge>
                          <ChevronDown className={cn(
                            "h-5 w-5 text-muted-foreground transition-transform",
                            expandedApproval === approval.id && "rotate-180"
                          )} />
                        </div>
                      </button>
                    </CollapsibleTrigger>

                    <CollapsibleContent>
                      <div className="px-4 pb-4 border-t border-border pt-4">
                        <p className="text-sm text-muted-foreground mb-4">
                          {approval.description}
                        </p>

                        <div className="space-y-2 mb-4">
                          <p className="text-sm font-medium">Suggested Meals:</p>
                          {approval.meals.map((meal, index) => (
                            <div
                              key={index}
                              className="flex items-center justify-between p-2 rounded bg-secondary/50 text-sm"
                            >
                              <span>{meal.name}</span>
                              <span className="text-muted-foreground">
                                Na: {meal.sodium}mg | {meal.calories} kcal
                              </span>
                            </div>
                          ))}
                        </div>

                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            className="flex-1 border-destructive/30 text-destructive hover:bg-destructive/10"
                            onClick={() => setApprovalDialog({ open: true, approval, action: "reject" })}
                          >
                            <X className="mr-2 h-4 w-4" />
                            Reject
                          </Button>
                          <Button
                            className="flex-1 bg-accent hover:bg-accent/90"
                            onClick={() => setApprovalDialog({ open: true, approval, action: "approve" })}
                          >
                            <Check className="mr-2 h-4 w-4" />
                            Approve
                          </Button>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </div>
          )}
        </BentoCard>

        {/* Supervisor Guidelines */}
        <BentoCard colSpan={3}>
          <div className="flex items-center gap-2 mb-4">
            <Eye className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-lg">Supervisor Guidelines</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
              <h3 className="font-medium mb-2 text-primary">Review AI Confidence</h3>
              <p className="text-sm text-muted-foreground">
                AI confidence scores above 85% indicate strong alignment with clinical protocols. 
                Lower scores may require additional review.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
              <h3 className="font-medium mb-2 text-accent">Validate Nutrient Limits</h3>
              <p className="text-sm text-muted-foreground">
                Ensure suggested meals comply with IFCT 2017 guidelines and individual 
                patient thresholds for sodium, potassium, and protein.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-chart-3/10 border border-chart-3/20">
              <h3 className="font-medium mb-2 text-chart-3">Monitor High-Priority Alerts</h3>
              <p className="text-sm text-muted-foreground">
                Critical alerts require immediate attention. Glucose spikes and significant 
                deviations should be addressed within 2 hours.
              </p>
            </div>
          </div>
        </BentoCard>
      </BentoGrid>

      {/* Approval/Rejection Dialog */}
      <Dialog open={approvalDialog.open} onOpenChange={(open) => setApprovalDialog({ open })}>
        <DialogContent className="glass">
          <DialogHeader>
            <DialogTitle className={cn(
              "flex items-center gap-2",
              approvalDialog.action === "approve" ? "text-accent" : "text-destructive"
            )}>
              {approvalDialog.action === "approve" ? (
                <><ShieldCheck className="h-5 w-5" /> Approve Meal Plan</>
              ) : (
                <><X className="h-5 w-5" /> Reject Meal Plan</>
              )}
            </DialogTitle>
            <DialogDescription>
              {approvalDialog.action === "approve" 
                ? "This meal plan will be sent to the patient for implementation."
                : "Please provide a reason for rejection. The AI will use this feedback to improve future recommendations."
              }
            </DialogDescription>
          </DialogHeader>

          {approvalDialog.approval && (
            <div className="space-y-4">
              <div className="p-3 rounded-lg bg-secondary/50">
                <p className="font-medium">{approvalDialog.approval.title}</p>
                <p className="text-sm text-muted-foreground">{approvalDialog.approval.patientName}</p>
              </div>

              {approvalDialog.action === "reject" && (
                <div className="space-y-2">
                  <Label htmlFor="rejection-note">Rejection Notes</Label>
                  <Textarea
                    id="rejection-note"
                    value={rejectionNote}
                    onChange={(e) => setRejectionNote(e.target.value)}
                    placeholder="Explain why this plan doesn't meet clinical requirements..."
                    className="bg-secondary/50"
                  />
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setApprovalDialog({ open: false })}>
              Cancel
            </Button>
            <Button
              className={approvalDialog.action === "approve" ? "bg-accent hover:bg-accent/90" : "bg-destructive hover:bg-destructive/90"}
              onClick={() => handleApprovalAction(approvalDialog.action!)}
              disabled={approvalDialog.action === "reject" && !rejectionNote.trim()}
            >
              {approvalDialog.action === "approve" ? "Confirm Approval" : "Submit Rejection"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  )
}
