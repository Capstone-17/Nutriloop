import { Platform } from "react-native";

export interface AppConfig {
  apiUrl: string;
  isProduction: boolean;
  timeouts: {
    assessmentMs: number;
    dietPlanMs: number;
    chatMs: number;
    defaultMs: number;
  };
  retries: {
    maxAttempts: number;
    baseDelayMs: number;
  };
}

const isProd = process.env.NODE_ENV === "production";

// Resolve default development URL per platform
const getDevApiUrl = (): string => {
  if (Platform.OS === "android") {
    // 10.0.2.2 is the Android emulator's alias to host loopback
    return "http://10.0.2.2:8000";
  }
  return "http://localhost:8000";
};

// EXPO_PUBLIC_API_URL takes precedence when set in .env or EAS build
const resolvedApiUrl = (
  process.env.EXPO_PUBLIC_API_URL ||
  (isProd ? "https://api.nutriloop.com" : getDevApiUrl())
).replace(/\/+$/, "");

export const ENV: AppConfig = {
  apiUrl: resolvedApiUrl,
  isProduction: isProd,
  timeouts: {
    assessmentMs: 15000, // 15 seconds for ML risk assessment
    dietPlanMs: 35000,   // 35 seconds for full 7-day 35-meal generation
    chatMs: 60000,       // 60 seconds for server-side clinical LLM reasoning
    defaultMs: 20000,    // 20 seconds for standard queries
  },
  retries: {
    maxAttempts: 2,
    baseDelayMs: 1000,
  },
};
