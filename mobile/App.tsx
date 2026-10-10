import React, { useEffect, useState } from "react";
import { StyleSheet, View, Text, TouchableOpacity, SafeAreaView, Platform } from "react-native";
import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "./src/theme/colors";
import { Header, getRandomAlliterativeName } from "./src/components/Header";
import { AssessmentScreen } from "./src/screens/AssessmentScreen";
import { DietScreen } from "./src/screens/DietScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import {
  PatientVitals,
  MultiDiseaseAssessmentResult,
  WeeklyDietPlan,
  SavePatientTestResult,
} from "./src/types/clinical";
import { dbManager } from "./src/db/database";
import { ClinicalRulesEngine } from "./src/engine/clinical_rules";

export default function App() {
  const [activeTab, setActiveTab] = useState<"assessment" | "diet" | "history">("assessment");
  const [patientName, setPatientName] = useState<string>("Clever Cheetah");
  const [reportDate, setReportDate] = useState<string | null>(null);
  const [isHistoricalTest, setIsHistoricalTest] = useState<boolean>(false);

  // Clinical Vitals Baseline
  const [vitals, setVitals] = useState<PatientVitals>({
    ageYears: 48,
    sex: "male",
    bodyMassIndex: 25.4,
    systolicBpMmhg: 130,
    diastolicBpMmhg: 82,
    fastingGlucoseMgDl: 110,
    hba1cPct: 5.8,
    serumCreatinineMgDl: 1.0,
    egfrMlMin: 85,
    serumPotassiumMeqL: 4.3,
    serumSodiumMeqL: 140,
  });

  const [assessmentResult, setAssessmentResult] = useState<MultiDiseaseAssessmentResult | null>(null);
  const [activePlan, setActivePlan] = useState<WeeklyDietPlan | null>(null);

  // Initialize SQLite and load saved plan/test/name
  useEffect(() => {
    async function initOfflineData() {
      try {
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
          const res = ClinicalRulesEngine.assessPatient(latest.vitals);
          setAssessmentResult(res);
        } else {
          // Compute baseline assessment
          const res = ClinicalRulesEngine.assessPatient(vitals);
          setAssessmentResult(res);
        }
      } catch (err) {
        console.warn("Error initializing offline database:", err);
      }
    }
    initOfflineData();
  }, []);

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

        {activeTab === "history" && (
          <HistoryScreen
            onLoadTest={(loadedVitals, createdAt, isHistorical) => {
              setVitals(loadedVitals);
              setReportDate(createdAt || null);
              setIsHistoricalTest(isHistorical ?? false);
              const res = ClinicalRulesEngine.assessPatient(loadedVitals);
              setAssessmentResult(res);
              setActiveTab("assessment");
            }}
          />
        )}
      </View>

      {/* Bottom Navigation Bar */}
      <View style={styles.bottomNav}>
        <TouchableOpacity
          style={[styles.navItem, activeTab === "assessment" && styles.navItemActive]}
          onPress={() => setActiveTab("assessment")}
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
          style={[styles.navItem, activeTab === "history" && styles.navItemActive]}
          onPress={() => setActiveTab("history")}
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
    paddingVertical: 10,
    paddingBottom: Platform.OS === "ios" ? 22 : 10,
  },
  navItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
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
