"use client"

import { motion } from "framer-motion"
import {
  Bell,
  Globe,
  Moon,
  Palette,
  Shield,
  Smartphone,
  User,
} from "lucide-react"
import { DashboardLayout } from "@/components/dashboard/dashboard-layout"
import { BentoCard, BentoGrid } from "@/components/dashboard/bento-card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <header className="mb-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground mt-1">
            Manage your account and application preferences
          </p>
        </motion.div>
      </header>

      <BentoGrid>
        {/* Profile Settings */}
        <BentoCard colSpan={2}>
          <div className="flex items-center gap-2 mb-6">
            <User className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-lg">Profile Settings</h2>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input id="name" defaultValue="Patient User" className="bg-secondary/50" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" defaultValue="patient@example.com" className="bg-secondary/50" />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input id="phone" defaultValue="+91 98765 43210" className="bg-secondary/50" />
            </div>
            <Button className="bg-primary">Save Changes</Button>
          </div>
        </BentoCard>

        {/* Appearance */}
        <BentoCard>
          <div className="flex items-center gap-2 mb-6">
            <Palette className="h-5 w-5 text-accent" />
            <h2 className="font-semibold text-lg">Appearance</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Moon className="h-4 w-4 text-muted-foreground" />
                <Label>Dark Mode</Label>
              </div>
              <Switch defaultChecked />
            </div>

            <Separator />

            <div className="space-y-2">
              <Label>Language</Label>
              <Select defaultValue="en">
                <SelectTrigger className="bg-secondary/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="hi">Hindi</SelectItem>
                  <SelectItem value="ta">Tamil</SelectItem>
                  <SelectItem value="te">Telugu</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </BentoCard>

        {/* Notifications */}
        <BentoCard colSpan={2}>
          <div className="flex items-center gap-2 mb-6">
            <Bell className="h-5 w-5 text-chart-3" />
            <h2 className="font-semibold text-lg">Notifications</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
              <div>
                <p className="font-medium">Meal Reminders</p>
                <p className="text-sm text-muted-foreground">Get notified to log your meals</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
              <div>
                <p className="font-medium">Health Alerts</p>
                <p className="text-sm text-muted-foreground">Notifications when limits are exceeded</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
              <div>
                <p className="font-medium">AI Recommendations</p>
                <p className="text-sm text-muted-foreground">New meal plan suggestions</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
              <div>
                <p className="font-medium">Supervisor Updates</p>
                <p className="text-sm text-muted-foreground">When plans are approved/rejected</p>
              </div>
              <Switch defaultChecked />
            </div>
          </div>
        </BentoCard>

        {/* Privacy & Security */}
        <BentoCard>
          <div className="flex items-center gap-2 mb-6">
            <Shield className="h-5 w-5 text-accent" />
            <h2 className="font-semibold text-lg">Privacy</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">Share with Supervisor</p>
                <p className="text-xs text-muted-foreground">Allow clinician access</p>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">Family Access</p>
                <p className="text-xs text-muted-foreground">Allow family view</p>
              </div>
              <Switch defaultChecked />
            </div>

            <Separator />

            <Button variant="outline" className="w-full">
              Download My Data
            </Button>
          </div>
        </BentoCard>

        {/* Connected Devices */}
        <BentoCard colSpan={2}>
          <div className="flex items-center gap-2 mb-6">
            <Smartphone className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-lg">Connected Devices</h2>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg border border-accent/30 bg-accent/5">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-accent/20 flex items-center justify-center">
                  <Globe className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="font-medium">Web Browser</p>
                  <p className="text-xs text-muted-foreground">Chrome on Windows - Current Session</p>
                </div>
              </div>
              <span className="text-xs text-accent">Active</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/30">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center">
                  <Smartphone className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="font-medium">Mobile App</p>
                  <p className="text-xs text-muted-foreground">iPhone 14 - Last active 2 hours ago</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" className="text-destructive">
                Revoke
              </Button>
            </div>
          </div>
        </BentoCard>

        {/* Data Sources */}
        <BentoCard>
          <div className="flex items-center gap-2 mb-6">
            <Globe className="h-5 w-5 text-chart-3" />
            <h2 className="font-semibold text-lg">Data Sources</h2>
          </div>

          <div className="space-y-3 text-sm">
            <div className="p-3 rounded-lg bg-secondary/50">
              <p className="font-medium">IFCT 2017</p>
              <p className="text-xs text-muted-foreground">Indian Food Composition Tables</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/50">
              <p className="font-medium">Open Food Facts</p>
              <p className="text-xs text-muted-foreground">Packaged food database (India)</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/50">
              <p className="font-medium">Mendeley Indian Recipes</p>
              <p className="text-xs text-muted-foreground">6000+ traditional dishes</p>
            </div>
          </div>
        </BentoCard>
      </BentoGrid>
    </DashboardLayout>
  )
}
