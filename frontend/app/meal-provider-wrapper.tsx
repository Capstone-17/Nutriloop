'use client'

import { useAuth } from '@/lib/auth-context'
import { MealProvider } from '@/lib/meal-context'

export function MealProviderWrapper({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return <MealProvider userEmail={user?.email || null}>{children}</MealProvider>
}
