import React, { useEffect, useState } from "react";
import { StyleSheet, View, Text, TouchableOpacity, SafeAreaView, Platform } from "react-native";
import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "./src/theme/colors";
import { Header, getRandomAlliterativeName } from "./src/components/Header";
import { AssessmentScreen } from "./src/screens/AssessmentScreen";
import { DietScreen } from "./src/screens/DietScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import { ChatScreen } from "./src/screens/ChatScreen";
import { MedicalDisclaimerModal } from "./src/components/MedicalDisclaimerModal";
import {
  PatientVitals,
  DEFAULT_PATIENT_VITALS,
  MultiDiseaseAssessmentResult,
  WeeklyDietPlan,
  SavePatientTestResult,
} from "./src/types/clinical";
import { dbManager } from "./src/db/database";
import { ApiService } from "./src/services/api";
import { SecureStorageService } from "./src/services/storage";

export default function App() {
  const [activeTab, setActiveTab] = useState<"assessment" | "diet" | "chat" | "history">("assessment");
  const [patientName, setPatientName] = useState<string>("Clever Cheetah");
  const [reportDate, setReportDate] = useState<string | null>(null);
  const [isHistoricalTest, setIsHistoricalTest] = useState<boolean>(false);
  const [showDisclaimer, setShowDisclaimer] = useState<boolean>(false);

  // Clinical Vitals Baseline (Ideal Reference Standard: Normotensive & Euglycemic)
  const [vitals, setVitals] = useState<PatientVitals>(DEFAULT_PATIENT_VITALS);

  const [assessmentResult, setAssessmentResult] = useState<MultiDiseaseAssessmentResult | null>(null);
  const [activePlan, setActivePlan] = useState<WeeklyDietPlan | null>(null);

  // Initialize SQLite, secure disclaimer status, and load saved plan/test/name
  useEffect(() => {
    async function initAppData() {
      try {
        // Check mandatory clinical disclaimer status
        const accepted = await SecureStorageService.isDisclaimerAccepted();
        if (!accepted) {
          setShowDisclaimer(true);
        }

        await dbManager.getDb();

        const savedName = await dbManager.getSetting("patient_name");
        if (savedName) {
          setPatientName(savedName);
        } else {
          const newName = getRandomAlliterativeName();
          setPatientName(newName);
          await dbManager.saveSetting("patient_name", newName);
        }

        const savedPlan = await dbManager.getActivePlan("patient_local");
        if (savedPlan) {
          setActivePlan(savedPlan);
        }

        const tests = await dbManager.getPatientTestHistory("patient_local");
        if (tests.length > 0) {
          const latest = tests[0];
          setVitals(latest.vitals);
          setReportDate(latest.createdAt);
          setIsHistoricalTest(false);
          try {
            const res = await ApiService.assessPatient(latest.vitals);
            setAssessmentResult(res);
          } catch {
            if (latest.assessments) {
              setAssessmentResult({
                timestamp: latest.createdAt,
                detectedConditions: latest.detectedConditions || [],
                assessments: latest.assessments as any,
                vitals: latest.vitals,
              });
            }
          }
        } else {
          // No saved test reports yet: apply ideal clinical baseline report
          setVitals(DEFAULT_PATIENT_VITALS);
          setReportDate(null);
          setIsHistoricalTest(false);
          try {
            const res = await ApiService.assessPatient(DEFAULT_PATIENT_VITALS);
            setAssessmentResult(res);
          } catch (e) {
            console.warn("Initial backend assessment notice:", e);
          }
        }
      } catch (err) {
        console.warn("Error initializing app data:", err);
      }
    }
    initAppData();
  }, []);

  const handleAcceptDisclaimer = async () => {
    await SecureStorageService.setDisclaimerAccepted(true);
    setShowDisclaimer(false);
  };

  const handlePatientNameChange = async (newName: string) => {
    setPatientName(newName);
    try {
      await dbManager.saveSetting("patient_name", newName);
    } catch (e) {
      console.warn("Failed to save patient name:", e);
    }
  };

  const handleAssessCompleted = async (
    result: MultiDiseaseAssessmentResult
  ): Promise<SavePatientTestResult> => {
    setAssessmentResult(result);
    try {
      const saveRes = await dbManager.savePatientTest("patient_local", vitals, result);
      if (!saveRes.isDuplicate) {
        setReportDate(new Date().toISOString());
        setIsHistoricalTest(false);
      }
      return saveRes;
    } catch (e) {
      console.warn("Failed to auto-save test to SQLite:", e);
      return { id: 0, isDuplicate: false };
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <Header patientName={patientName} onPatientNameChange={handlePatientNameChange} />

      {/* Main Screen Viewport */}
      <View style={styles.contentContainer}>
        {activeTab === "assessment" && (
          <AssessmentScreen
            vitals={vitals}
            onVitalsChange={setVitals}
            assessmentResult={assessmentResult}
            onAssessCompleted={handleAssessCompleted}
            onProceedToDiet={() => setActiveTab("diet")}
          />
        )}

        {activeTab === "diet" && (
          <DietScreen
            vitals={vitals}
            detectedConditions={assessmentResult?.detectedConditions || []}
            activePlan={activePlan}
            onPlanGenerated={setActivePlan}
            reportDate={reportDate}
            isHistoricalTest={isHistoricalTest}
          />
        )}

        {activeTab === "chat" && <ChatScreen vitals={vitals} />}

        {activeTab === "history" && (
          <HistoryScreen
            onLoadTest={async (loadedVitals, createdAt, isHistorical) => {
              setVitals(loadedVitals);
              setReportDate(createdAt || null);
              setIsHistoricalTest(isHistorical ?? false);
              try {
                const res = await ApiService.assessPatient(loadedVitals);
                setAssessmentResult(res);
              } catch (e) {
                console.warn("Historical test assessment notice:", e);
              }
              setActiveTab("assessment");
            }}
          />
        )}
      </View>

      {/* Bottom Navigation Bar with >= 48px touch targets */}
      <View style={styles.bottomNav}>
        <TouchableOpacity
          style={[styles.navItem, activeTab === "assessment" && styles.navItemActive]}
          onPress={() => setActiveTab("assessment")}
          activeOpacity={0.7}
        >
          <Ionicons
            name={activeTab === "assessment" ? "pulse" : "pulse-outline"}
            size={22}
            color={activeTab === "assessment" ? Colors.secondary : Colors.textMuted}
          />
          <Text style={[styles.navText, activeTab === "assessment" && styles.navTextActive]}>
            Assessment
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === "diet" && styles.navItemActive]}
          onPress={() => setActiveTab("diet")}
          activeOpacity={0.7}
        >
          <Ionicons
            name={activeTab === "diet" ? "restaurant" : "restaurant-outline"}
            size={22}
            color={activeTab === "diet" ? Colors.secondary : Colors.textMuted}
          />
          <Text style={[styles.navText, activeTab === "diet" && styles.navTextActive]}>
            7-Day Diet
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === "chat" && styles.navItemActive]}
          onPress={() => setActiveTab("chat")}
          activeOpacity={0.7}
        >
          <Ionicons
            name={activeTab === "chat" ? "chatbubble-ellipses" : "chatbubble-ellipses-outline"}
            size={22}
            color={activeTab === "chat" ? Colors.secondary : Colors.textMuted}
          />
          <Text style={[styles.navText, activeTab === "chat" && styles.navTextActive]}>
            AI Chat
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === "history" && styles.navItemActive]}
          onPress={() => setActiveTab("history")}
          activeOpacity={0.7}
        >
          <Ionicons
            name={activeTab === "history" ? "time" : "time-outline"}
            size={22}
            color={activeTab === "history" ? Colors.secondary : Colors.textMuted}
          />
          <Text style={[styles.navText, activeTab === "history" && styles.navTextActive]}>
            Records
          </Text>
        </TouchableOpacity>
      </View>

      {/* Mandatory First-Launch Clinical Disclaimer Modal */}
      <MedicalDisclaimerModal
        visible={showDisclaimer}
        onAccept={handleAcceptDisclaimer}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.bgMain,
  },
  contentContainer: {
    flex: 1,
  },
  bottomNav: {
    flexDirection: "row",
    backgroundColor: Colors.bgSurface,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    paddingVertical: 8,
    paddingBottom: Platform.OS === "ios" ? 24 : 10,
  },
  navItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
    paddingVertical: 4,
  },
  navItemActive: {},
  navText: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    marginTop: 3,
  },
  navTextActive: {
    color: Colors.secondary,
    fontWeight: "700",
  },
});
