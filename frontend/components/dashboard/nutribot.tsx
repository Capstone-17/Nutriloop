"use client"

import { useState, useRef, useEffect } from "react"
import { motion } from "framer-motion"
import { Brain, Send, X, Sparkles, AlertTriangle, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  type?: "normal" | "warning" | "safe"
}

interface NutriBotProps {
  onClose: () => void
}

// Simulated Clinical Rule Engine responses
const clinicalResponses: Record<string, { response: string; type: "normal" | "warning" | "safe" }> = {
  "hypertension": {
    response: "Based on your hypertension profile, I recommend limiting sodium intake to under 1500mg daily. Avoid processed foods, canned soups, and excessive salt. Consider DASH diet principles with emphasis on potassium-rich foods like bananas and leafy greens.",
    type: "safe"
  },
  "sodium": {
    response: "High sodium foods can elevate blood pressure. For your CKD Stage 2 condition, keep daily sodium below 2000mg. I've flagged this meal in your log as it contains 890mg sodium - that's 44% of your daily limit in one meal.",
    type: "warning"
  },
  "safe": {
    response: "This food choice aligns well with your chronic condition management protocols. It's low in sodium (120mg), moderate in potassium (280mg), and provides excellent fiber content. Approved for your meal plan!",
    type: "safe"
  },
  "ckd": {
    response: "For CKD Stage 2 management, monitor protein intake (0.8g/kg body weight), limit phosphorus-rich foods, and keep potassium within 2000-3000mg daily. Avoid high-potassium fruits like oranges and bananas in excess.",
    type: "warning"
  },
  "diabetes": {
    response: "Managing T2DM requires consistent carbohydrate monitoring. Your target is 45-60g carbs per meal. Focus on low-glycemic foods, increase fiber intake, and time your meals consistently. I'll alert you if any logged food exceeds these parameters.",
    type: "safe"
  },
}

function getAIResponse(message: string): { response: string; type: "normal" | "warning" | "safe" } {
  const lowerMessage = message.toLowerCase()
  
  if (lowerMessage.includes("hypertension") || lowerMessage.includes("blood pressure")) {
    return clinicalResponses["hypertension"]
  }
  if (lowerMessage.includes("sodium") || lowerMessage.includes("salt")) {
    return clinicalResponses["sodium"]
  }
  if (lowerMessage.includes("safe") || lowerMessage.includes("can i eat") || lowerMessage.includes("is this ok")) {
    return clinicalResponses["safe"]
  }
  if (lowerMessage.includes("kidney") || lowerMessage.includes("ckd") || lowerMessage.includes("creatinine")) {
    return clinicalResponses["ckd"]
  }
  if (lowerMessage.includes("diabetes") || lowerMessage.includes("sugar") || lowerMessage.includes("glucose") || lowerMessage.includes("t2dm")) {
    return clinicalResponses["diabetes"]
  }
  
  return {
    response: "I'm NutriBot, your AI dietary assistant. I can help you understand how foods interact with your chronic conditions (T2DM, CKD, Hypertension). Try asking me 'Is this safe for my hypertension?' or 'What should I know about sodium with CKD?'",
    type: "normal"
  }
}

export function NutriBot({ onClose }: NutriBotProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I'm NutriBot, your AI-powered dietary assistant. I can help you understand how foods interact with your chronic conditions. What would you like to know?",
      type: "normal"
    }
  ])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async () => {
    if (!input.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsTyping(true)

    // Simulate AI thinking
    await new Promise((resolve) => setTimeout(resolve, 1000 + Math.random() * 1000))

    const { response, type } = getAIResponse(input)
    
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: response,
      type,
    }

    setIsTyping(false)
    setMessages((prev) => [...prev, assistantMessage])
  }

  const getMessageIcon = (type?: string) => {
    switch (type) {
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-chart-3" />
      case "safe":
        return <ShieldCheck className="h-4 w-4 text-accent" />
      default:
        return <Sparkles className="h-4 w-4 text-primary" />
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 100, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.95 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="fixed right-6 bottom-6 top-6 z-50 w-full max-w-md"
    >
      <div className="flex h-full flex-col glass rounded-2xl overflow-hidden shadow-2xl border border-primary/20">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/50 bg-gradient-to-r from-primary/10 to-accent/10 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/20 glow-cyan">
              <Brain className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold">NutriBot</h3>
              <p className="text-xs text-muted-foreground">AI Dietary Assistant</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn(
                  "flex gap-3",
                  message.role === "user" && "flex-row-reverse"
                )}
              >
                {message.role === "assistant" && (
                  <div className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                    message.type === "warning" ? "bg-chart-3/20" : 
                    message.type === "safe" ? "bg-accent/20" : "bg-primary/20"
                  )}>
                    {getMessageIcon(message.type)}
                  </div>
                )}
                <div
                  className={cn(
                    "rounded-2xl px-4 py-3 max-w-[85%]",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : message.type === "warning"
                      ? "bg-chart-3/10 border border-chart-3/30"
                      : message.type === "safe"
                      ? "bg-accent/10 border border-accent/30"
                      : "bg-secondary"
                  )}
                >
                  <p className="text-sm leading-relaxed">{message.content}</p>
                </div>
              </motion.div>
            ))}
            
            {isTyping && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-3"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20">
                  <Brain className="h-4 w-4 text-primary animate-pulse" />
                </div>
                <div className="bg-secondary rounded-2xl px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="border-t border-border/50 p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
            }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your diet..."
              className="flex-1 bg-secondary/50 border-border/50"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || isTyping}
              className="bg-primary hover:bg-primary/90 glow-cyan"
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted-foreground text-center">
            Powered by Clinical Rule Engine
          </p>
        </div>
      </div>
    </motion.div>
  )
}
