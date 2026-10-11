import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Modal,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Svg, { Circle } from "react-native-svg";
import { Colors } from "../theme/colors";
import { VitalSliderCard } from "../components/VitalSliderCard";
import {
  PatientVitals,
  DEFAULT_PATIENT_VITALS,
  MultiDiseaseAssessmentResult,
  SavePatientTestResult,
} from "../types/clinical";
import { ApiService } from "../services/api";
import { parseLabReportText, calculateCkdEpiEgfr } from "../utils/labParser";
import { formatDecimal, roundToDecimal } from "../utils/formatters";

interface AssessmentScreenProps {
  vitals: PatientVitals;
  onVitalsChange: (vitals: PatientVitals) => void;
  assessmentResult: MultiDiseaseAssessmentResult | null;
  onAssessCompleted: (result: MultiDiseaseAssessmentResult) => Promise<SavePatientTestResult | void> | void;
  onProceedToDiet?: () => void;
}

const CircularScoreGauge: React.FC<{ scorePercentage: number; strokeColor: string }> = ({
  scorePercentage,
  strokeColor,
}) => {
  const size = 80;
  const strokeWidth = 5.5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(100, Math.max(3, scorePercentage));
  const strokeDashoffset = circumference - (circumference * progress) / 100;

  return (
    <View style={styles.gaugeContainer}>
      <Svg width={size} height={size}>
        {/* Background track circle */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress circular stroke */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          fill="none"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <View style={styles.gaugeInnerContent}>
        <Text style={styles.gaugeScoreText}>{formatDecimal(scorePercentage, 2)}%</Text>
        <Text style={styles.gaugeScoreLabel}>SCORE</Text>
      </View>
    </View>
  );
};

export const AssessmentScreen: React.FC<AssessmentScreenProps> = ({
  vitals,
  onVitalsChange,
  assessmentResult,
  onAssessCompleted,
  onProceedToDiet,
}) => {
  const [labTextModalVisible, setLabTextModalVisible] = useState(false);
  const [duplicateNoticeVisible, setDuplicateNoticeVisible] = useState(false);
  const [labTextInput, setLabTextInput] = useState("");
  const [isAssessing, setIsAssessing] = useState(false);
  const [selectedExplainDisease, setSelectedExplainDisease] = useState<"ckd" | "hypertension" | "diabetes">("ckd");

  const updateVital = <K extends keyof PatientVitals>(key: K, val: PatientVitals[K]) => {
    const updated = { ...vitals, [key]: val };
    // Auto-recalculate eGFR if creatinine, age, or sex changes
    if (key === "serumCreatinineMgDl" || key === "ageYears" || key === "sex") {
      updated.egfrMlMin = calculateCkdEpiEgfr(
        updated.serumCreatinineMgDl,
        updated.ageYears,
        updated.sex
      );
    }
    onVitalsChange(updated);
  };

  const handleRunAssessment = async () => {
    try {
      setIsAssessing(true);
      const result = await ApiService.assessPatient(vitals);
      const saveRes = await onAssessCompleted(result);
      if (saveRes && saveRes.isDuplicate) {
        setDuplicateNoticeVisible(true);
      }
    } catch (err: any) {
      console.warn("Assessment API error:", err);
      Alert.alert(
        "Assessment Notice",
        `Could not reach common backend API (${err?.message || "Check connection"}). Please ensure Nutriloop backend is running.`
      );
    } finally {
      setIsAssessing(false);
    }
  };

  const handleApplyLabText = () => {
    if (!labTextInput.trim()) {
      setLabTextModalVisible(false);
      return;
    }
    const extracted = parseLabReportText(labTextInput);
    const count = Object.keys(extracted).length;
    if (count === 0) {
      Alert.alert("No Biomarkers Found", "Could not detect blood pressure, glucose, creatinine, or lab values in the pasted text.");
      return;
    }

    const merged = { ...vitals, ...extracted };
    if (extracted.serumCreatinineMgDl && !extracted.egfrMlMin) {
      merged.egfrMlMin = calculateCkdEpiEgfr(
        merged.serumCreatinineMgDl,
        merged.ageYears,
        merged.sex
      );
    }
    onVitalsChange(merged);
    setLabTextModalVisible(false);
    setLabTextInput("");
    Alert.alert("Lab Values Extracted", `Successfully updated ${count} clinical biomarker(s) from report text!`);
  };

  // Helper for explainability content based on selected disease
  const renderExplainabilityContent = () => {
    if (!assessmentResult) return null;
    const item = assessmentResult.assessments[selectedExplainDisease];
    const level = item.riskLevel;
    const isHigh = level === "high";
    const isMod = level === "moderate";

    const whyTitle = isHigh
      ? "Why Is It High? (Primary Clinical Causes)"
      : isMod
      ? "Why Is It Moderate? (Key Contributing Factors)"
      : "What Is Working Well (Positive Health Signals)";

    const actionTitle = isHigh
      ? "What To Do (Urgent Clinical & Dietary Actions)"
      : isMod
      ? "How To Reduce It (Targeted Corrective Steps)"
      : "Steps To Preserve It (Daily Habits to Maintain Health)";

    const whyIcon = isHigh || isMod ? "🔍" : "⭐";
    const actionIcon = isHigh ? "🚨" : isMod ? "📉" : "🌿";

    // Why reasons
    const whyReasons =
      !isHigh && !isMod && item.protectiveFactors && item.protectiveFactors.length > 0
        ? item.protectiveFactors
        : item.primaryDrivers;

    // Action plan tailored to disease
    let actionSteps: string[] = [];
    if (selectedExplainDisease === "ckd") {
      actionSteps = isHigh || isMod
        ? [
            "Strictly restrict daily sodium intake to < 2000 mg/day (KDIGO guidelines).",
            "Moderate dietary protein to 0.6-0.8 g/kg/day to minimize renal hyperfiltration.",
            "Avoid unmonitored NSAID pain relievers and maintain routine nephrology follow-up."
          ]
        : [
            "Maintain optimal daily hydration (2.0 to 2.5 L/day) and low-sodium culinary habits.",
            "Avoid routine unmonitored NSAID painkillers to safeguard renal nephron filtration.",
            "Schedule an annual metabolic renal panel (eGFR & serum creatinine) with your primary physician."
          ];
    } else if (selectedExplainDisease === "hypertension") {
      actionSteps = isHigh || isMod
        ? [
            "Follow AHA DASH guidelines: reduce daily sodium to < 1500 mg/day.",
            "Increase potassium-rich vegetables (unless contraindicated by comorbid CKD) to lower vascular tone.",
            "Engage in 150 minutes of moderate aerobic cardiovascular pacing weekly."
          ]
        : [
            "Continue balanced dietary seasoning with mineral salts and cold-pressed cooking oils.",
            "Perform regular home blood pressure monitoring to maintain normotensive stability.",
            "Engage in consistent daily physical movement to maintain elastic vascular compliance."
          ];
    } else {
      // diabetes
      actionSteps = isHigh || isMod
        ? [
            "Prioritize complex whole grains with high fiber (millets, ragi, barley) to blunt glycemic spikes.",
            "Completely eliminate refined sugars, high-fructose beverages, and ultra-processed bakery products.",
            "Coordinate quarterly HbA1c testing and self-monitoring of fasting and postprandial blood glucose."
          ]
        : [
            "Maintain dietary fiber intake at >= 25g daily through whole pulses, millets, and greens.",
            "Keep added free sugars under 5% of total caloric intake per WHO standards.",
            "Maintain daily active movement to preserve high peripheral insulin sensitivity."
          ];
    }

    return (
      <View style={styles.explainContentCard}>
        {/* Meta Bar */}
        <View style={styles.explainMetaBar}>
          <Text style={styles.explainDiseaseTitle}>{item.diseaseName}</Text>
          <View
            style={[
              styles.explainRiskBadge,
              level === "high"
                ? styles.badgeHigh
                : level === "moderate"
                ? styles.badgeMod
                : styles.badgeLow,
            ]}
          >
            <Text
              style={[
                styles.explainRiskBadgeText,
                level === "high"
                  ? styles.badgeHighText
                  : level === "moderate"
                  ? styles.badgeModText
                  : styles.badgeLowText,
              ]}
            >
              {level === "high" ? "🔴" : level === "moderate" ? "🟡" : "🟢"} {level.toUpperCase()} RISK ({item.riskPercentage}%)
            </Text>
          </View>
        </View>

        {/* Section 1: Why */}
        <View style={styles.explainSection}>
          <View style={styles.explainSectionHeader}>
            <Text style={styles.explainSectionTitle}>
              {whyIcon} {whyTitle}
            </Text>
          </View>
          {whyReasons.map((r, rIdx) => (
            <View key={rIdx} style={styles.explainListItem}>
              <Text style={styles.explainBullet}>•</Text>
              <Text style={styles.explainListText}>{r}</Text>
            </View>
          ))}
        </View>

        {/* Section 2: What to do */}
        <View style={styles.explainSection}>
          <View style={styles.explainSectionHeader}>
            <Text style={styles.explainSectionTitle}>
              {actionIcon} {actionTitle}
            </Text>
          </View>
          {actionSteps.map((s, sIdx) => (
            <View key={sIdx} style={styles.explainListItem}>
              <Text style={styles.explainBullet}>•</Text>
              <Text style={styles.explainListText}>{s}</Text>
            </View>
          ))}
        </View>
      </View>
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* ──────────────────────────────────────────────────────────────────
          STEP 1: Values Entered First (Paste Lab Notes + 2-Column Sliders)
          ────────────────────────────────────────────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarTextWrap}>
          <Text style={styles.sectionHeading}>📋 Clinical Biomarkers & Vitals</Text>
          <Text style={styles.sectionSubheading}>Input latest lab tests or adjust sliders below</Text>
        </View>

        <View style={styles.topBarActions}>
          <TouchableOpacity
            style={styles.btnSecondary}
            activeOpacity={0.8}
            onPress={() => onVitalsChange({ ...DEFAULT_PATIENT_VITALS })}
          >
            <Ionicons name="refresh-outline" size={14} color={Colors.secondary} />
            <Text style={styles.btnSecondaryText}>Ideal Baseline</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.btnSecondary}
            activeOpacity={0.8}
            onPress={() => setLabTextModalVisible(true)}
          >
            <Ionicons name="document-text-outline" size={14} color={Colors.secondary} />
            <Text style={styles.btnSecondaryText}>Paste Notes</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Sex Toggle */}
      <View style={styles.sexToggleContainer}>
        <Text style={styles.sexLabel}>Biological Sex</Text>
        <View style={styles.sexButtonsRow}>
          <TouchableOpacity
            style={[styles.sexBtn, vitals.sex === "male" && styles.sexBtnActive]}
            onPress={() => updateVital("sex", "male")}
          >
            <Text style={[styles.sexBtnText, vitals.sex === "male" && styles.sexBtnTextActive]}>
              ♂ Male
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.sexBtn, vitals.sex === "female" && styles.sexBtnActive]}
            onPress={() => updateVital("sex", "female")}
          >
            <Text style={[styles.sexBtnText, vitals.sex === "female" && styles.sexBtnTextActive]}>
              ♀ Female
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 2 Sliders Per Row Grid */}
      {/* Row 1: Age & BMI */}
      <View style={styles.gridRow}>
        <VitalSliderCard
          title="Patient Age"
          value={vitals.ageYears}
          min={18}
          max={95}
          unit="yrs"
          onValueChange={(v) => updateVital("ageYears", Math.round(v))}
        />
        <VitalSliderCard
          title="BMI"
          value={vitals.bodyMassIndex}
          min={14}
          max={48}
          step={0.1}
          unit="kg/m²"
          statusType={vitals.bodyMassIndex >= 30 ? "danger" : vitals.bodyMassIndex >= 25 ? "warning" : "normal"}
          statusText={vitals.bodyMassIndex >= 30 ? "Obese" : vitals.bodyMassIndex >= 25 ? "Overweight" : "Normal"}
          onValueChange={(v) => updateVital("bodyMassIndex", roundToDecimal(v, 2))}
        />
      </View>

      {/* Row 2: Systolic BP & Diastolic BP */}
      <View style={styles.gridRow}>
        <VitalSliderCard
          title="Systolic BP"
          value={vitals.systolicBpMmhg}
          min={70}
          max={220}
          unit="mmHg"
          statusType={vitals.systolicBpMmhg >= 140 ? "danger" : vitals.systolicBpMmhg >= 130 ? "warning" : "normal"}
          statusText={vitals.systolicBpMmhg >= 140 ? "Stage 2 HTN" : vitals.systolicBpMmhg >= 130 ? "Stage 1 HTN" : "Optimal"}
          onValueChange={(v) => updateVital("systolicBpMmhg", Math.round(v))}
        />
        <VitalSliderCard
          title="Diastolic BP"
          value={vitals.diastolicBpMmhg}
          min={40}
          max={130}
          unit="mmHg"
          statusType={vitals.diastolicBpMmhg >= 90 ? "danger" : vitals.diastolicBpMmhg >= 80 ? "warning" : "normal"}
          statusText={vitals.diastolicBpMmhg >= 90 ? "High" : vitals.diastolicBpMmhg >= 80 ? "Elevated" : "Optimal"}
          onValueChange={(v) => updateVital("diastolicBpMmhg", Math.round(v))}
        />
      </View>

      {/* Row 3: Fasting Glucose & HbA1c */}
      <View style={styles.gridRow}>
        <VitalSliderCard
          title="Fasting Glucose"
          value={vitals.fastingGlucoseMgDl}
          min={50}
          max={350}
          unit="mg/dL"
          statusType={vitals.fastingGlucoseMgDl >= 126 ? "danger" : vitals.fastingGlucoseMgDl >= 100 ? "warning" : "normal"}
          statusText={vitals.fastingGlucoseMgDl >= 126 ? "Diabetic" : vitals.fastingGlucoseMgDl >= 100 ? "Prediabetic" : "Optimal"}
          onValueChange={(v) => updateVital("fastingGlucoseMgDl", Math.round(v))}
        />
        <VitalSliderCard
          title="HbA1c"
          value={vitals.hba1cPct}
          min={4.0}
          max={15.0}
          step={0.1}
          unit="%"
          statusType={vitals.hba1cPct >= 6.5 ? "danger" : vitals.hba1cPct >= 5.7 ? "warning" : "normal"}
          statusText={vitals.hba1cPct >= 6.5 ? "Diabetic" : vitals.hba1cPct >= 5.7 ? "Impaired" : "Optimal"}
          onValueChange={(v) => updateVital("hba1cPct", roundToDecimal(v, 2))}
        />
      </View>

      {/* Row 4: Serum Creatinine & Estimated GFR */}
      <View style={styles.gridRow}>
        <VitalSliderCard
          title="Serum Creatinine"
          value={vitals.serumCreatinineMgDl}
          min={0.2}
          max={8.0}
          step={0.05}
          unit="mg/dL"
          statusType={vitals.serumCreatinineMgDl > (vitals.sex === "female" ? 1.0 : 1.2) ? "danger" : "normal"}
          statusText={vitals.serumCreatinineMgDl > (vitals.sex === "female" ? 1.0 : 1.2) ? "Elevated" : "Normal"}
          onValueChange={(v) => updateVital("serumCreatinineMgDl", roundToDecimal(v, 2))}
        />
        <VitalSliderCard
          title="Estimated GFR"
          value={vitals.egfrMlMin}
          min={10}
          max={130}
          step={0.5}
          unit="mL/min"
          statusType={vitals.egfrMlMin < 60 ? "danger" : vitals.egfrMlMin < 90 ? "warning" : "normal"}
          statusText={vitals.egfrMlMin < 60 ? "Reduced GFR" : vitals.egfrMlMin < 90 ? "Mild Drop" : "Normal"}
          onValueChange={(v) => updateVital("egfrMlMin", roundToDecimal(v, 2))}
        />
      </View>

      {/* Row 5: Serum Potassium & Serum Sodium */}
      <View style={styles.gridRow}>
        <VitalSliderCard
          title="Potassium (K+)"
          value={vitals.serumPotassiumMeqL}
          min={2.0}
          max={7.5}
          step={0.05}
          unit="mEq/L"
          statusType={vitals.serumPotassiumMeqL > 5.0 || vitals.serumPotassiumMeqL < 3.5 ? "danger" : "normal"}
          statusText={vitals.serumPotassiumMeqL > 5.0 ? "High K+" : vitals.serumPotassiumMeqL < 3.5 ? "Low K+" : "Optimal"}
          onValueChange={(v) => updateVital("serumPotassiumMeqL", roundToDecimal(v, 2))}
        />
        <VitalSliderCard
          title="Sodium (Na+)"
          value={vitals.serumSodiumMeqL}
          min={115}
          max={165}
          unit="mEq/L"
          statusType={vitals.serumSodiumMeqL > 145 || vitals.serumSodiumMeqL < 135 ? "warning" : "normal"}
          statusText={vitals.serumSodiumMeqL > 145 ? "High Na+" : vitals.serumSodiumMeqL < 135 ? "Low Na+" : "Normal"}
          onValueChange={(v) => updateVital("serumSodiumMeqL", Math.round(v))}
        />
      </View>

      {/* ──────────────────────────────────────────────────────────────────
          STEP 2: Prominent Button to Run Assessment
          ────────────────────────────────────────────────────────────────── */}
      <TouchableOpacity
        style={[styles.btnRunAssessment, isAssessing && { opacity: 0.7 }]}
        activeOpacity={0.85}
        disabled={isAssessing}
        onPress={handleRunAssessment}
      >
        <Ionicons name={isAssessing ? "hourglass-outline" : "flash"} size={18} color="#FFF" />
        <Text style={styles.btnRunAssessmentText}>
          {isAssessing ? "Evaluating with Clinical Models..." : "Run Clinical Risk Assessment"}
        </Text>
      </TouchableOpacity>

      {/* ──────────────────────────────────────────────────────────────────
          STEP 3: Multi-Disease Risk Assessment Results (Matches Desktop UI)
          ────────────────────────────────────────────────────────────────── */}
      {assessmentResult ? (
        <View style={styles.resultsMainCard}>
          {/* Section Header with Proceed to Diet Planning Button */}
          <View style={styles.resultsCardHeader}>
            <Text style={styles.resultsCardTitle}>📊 Multi-Disease Risk Assessment Results</Text>
            {onProceedToDiet ? (
              <TouchableOpacity
                style={styles.btnProceedDiet}
                activeOpacity={0.8}
                onPress={onProceedToDiet}
              >
                <Text style={styles.btnProceedDietText}>🥗 Proceed to Diet Planning ➡️</Text>
              </TouchableOpacity>
            ) : null}
          </View>

          {/* Risk Dashboard Grid Trio (CKD, Hypertension, Diabetes) */}
          <View style={styles.riskTrioContainer}>
            {(["ckd", "hypertension", "diabetes"] as const).map((disKey) => {
              const item = assessmentResult.assessments[disKey];
              const isSelected = selectedExplainDisease === disKey;
              const barColor =
                item.riskLevel === "high"
                  ? Colors.dangerRose
                  : item.riskLevel === "moderate"
                  ? Colors.warningAmber
                  : Colors.safeGreen;

              return (
                <TouchableOpacity
                  key={disKey}
                  style={[
                    styles.riskMeterCard,
                    isSelected && styles.riskMeterCardActive,
                  ]}
                  activeOpacity={0.85}
                  onPress={() => setSelectedExplainDisease(disKey)}
                >
                  <Text style={styles.riskMeterTitle} numberOfLines={1}>
                    {item.diseaseName}
                  </Text>

                  {/* Circular Score Gauge */}
                  <CircularScoreGauge
                    scorePercentage={item.riskPercentage}
                    strokeColor={barColor}
                  />

                  {/* Risk Badge */}
                  <View
                    style={[
                      styles.riskBadge,
                      item.riskLevel === "high"
                        ? styles.badgeHigh
                        : item.riskLevel === "moderate"
                        ? styles.badgeMod
                        : styles.badgeLow,
                    ]}
                  >
                    <Text
                      style={[
                        styles.riskBadgeText,
                        item.riskLevel === "high"
                          ? styles.badgeHighText
                          : item.riskLevel === "moderate"
                          ? styles.badgeModText
                          : styles.badgeLowText,
                      ]}
                    >
                      {item.riskLevel.toUpperCase()}
                    </Text>
                  </View>

                  {/* Cutoff Legend */}
                  <Text style={styles.cutoffsText}>
                    Low: &lt;50% | Mod: 50-75% | High: &gt;75%
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Detected Chronic Conditions */}
          <View style={styles.detectedConditionsBox}>
            <Text style={styles.detectedConditionsLabel}>Detected Chronic Conditions:</Text>
            <View style={styles.conditionsRow}>
              {assessmentResult.detectedConditions.length > 0 ? (
                assessmentResult.detectedConditions.map((cond, i) => (
                  <View key={i} style={styles.conditionPill}>
                    <Text style={styles.conditionPillText}>• {cond}</Text>
                  </View>
                ))
              ) : (
                <View style={styles.conditionPillSafe}>
                  <Text style={styles.conditionPillSafeText}>✅ No High Clinical Comorbidities Detected</Text>
                </View>
              )}
            </View>
          </View>

          {/* ──────────────────────────────────────────────────────────────────
              STEP 4: Explainable AI Clinical Insights & Action Plan
              ────────────────────────────────────────────────────────────────── */}
          <View style={styles.explainabilityContainer}>
            <View style={styles.explainHeaderRow}>
              <Text style={styles.explainHeaderTitle}>
                💡 Explainable AI Clinical Insights &amp; Action Plan
              </Text>
              {/* Disease Switcher Tabs */}
              <View style={styles.explainTabs}>
                {(["ckd", "hypertension", "diabetes"] as const).map((disKey) => {
                  const isActive = selectedExplainDisease === disKey;
                  const label = disKey === "ckd" ? "CKD" : disKey === "hypertension" ? "HTN" : "Diabetes";
                  return (
                    <TouchableOpacity
                      key={disKey}
                      style={[styles.explainTabBtn, isActive && styles.explainTabBtnActive]}
                      onPress={() => setSelectedExplainDisease(disKey)}
                    >
                      <Text style={[styles.explainTabBtnText, isActive && styles.explainTabBtnTextActive]}>
                        {label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            {/* Explainability Card Content */}
            {renderExplainabilityContent()}
          </View>
        </View>
      ) : (
        <View style={styles.pendingCard}>
          <Text style={styles.pendingText}>
            💡 Adjust biomarkers above and tap "Run Clinical Risk Assessment" to view multi-disease risk analysis and Explainable AI clinical insights.
          </Text>
        </View>
      )}

      {/* Lab Text Parser Modal */}
      <Modal
        visible={labTextModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setLabTextModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Paste Clinical Notes / Doctor Report</Text>
              <TouchableOpacity onPress={() => setLabTextModalVisible(false)}>
                <Ionicons name="close" size={20} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Our NLP engine extracts BP (e.g. "140/90"), glucose, HbA1c, creatinine, and electrolytes automatically:
            </Text>

            <TextInput
              style={styles.modalTextInput}
              multiline
              numberOfLines={6}
              placeholder="e.g. Patient presents with BP 142/88 mmHg. Labs: Fasting blood sugar 128 mg/dL, HbA1c 6.8%, Serum Creatinine 1.3 mg/dL, eGFR 58, Potassium 4.8 mEq/L..."
              placeholderTextColor={Colors.textSubtle}
              value={labTextInput}
              onChangeText={setLabTextInput}
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setLabTextModalVisible(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.modalApplyBtn} onPress={handleApplyLabText}>
                <Text style={styles.modalApplyText}>Extract &amp; Populate Vitals</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Duplicate Test Report Notice Modal (Matches Desktop App UI Notice) */}
      <Modal
        visible={duplicateNoticeVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setDuplicateNoticeVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.noticeModalCard}>
            <View style={styles.noticeModalHeader}>
              <View style={styles.noticeIconBadge}>
                <Ionicons name="information-circle-outline" size={20} color={Colors.secondary} />
              </View>
              <Text style={styles.noticeModalTitle}>Risk Assessment Updated</Text>
            </View>

            <View style={styles.noticeModalBody}>
              <Text style={styles.noticeModalLead}>
                Risk assessment diagnostics updated.
              </Text>
              <Text style={styles.noticeModalSub}>
                Notice: Your biomarker values match your latest saved report, so no duplicate test record was added to history.
              </Text>
            </View>

            <TouchableOpacity
              style={styles.noticeModalBtn}
              activeOpacity={0.85}
              onPress={() => setDuplicateNoticeVisible(false)}
            >
              <Text style={styles.noticeModalBtnText}>Understood</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgMain,
  },
  content: {
    padding: 14,
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  topBarTextWrap: {
    flex: 1,
    marginRight: 8,
  },
  topBarActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  sectionHeading: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "700",
  },
  sectionSubheading: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  btnSecondary: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
    paddingVertical: 7,
    paddingHorizontal: 11,
    borderRadius: 8,
  },
  btnSecondaryText: {
    color: Colors.secondary,
    fontSize: 11.5,
    fontWeight: "600",
  },
  sexToggleContainer: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1,
    borderColor: Colors.borderCard,
  },
  sexLabel: {
    color: Colors.textMain,
    fontSize: 13,
    fontWeight: "600",
  },
  sexButtonsRow: {
    flexDirection: "row",
    gap: 8,
  },
  sexBtn: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  sexBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryLight,
  },
  sexBtnText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  sexBtnTextActive: {
    color: "#FFF",
    fontWeight: "700",
  },
  gridRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 2,
  },
  btnRunAssessment: {
    backgroundColor: Colors.primary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.primaryLight,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35,
    shadowRadius: 6,
    elevation: 4,
  },
  btnRunAssessmentText: {
    color: "#FFF",
    fontSize: 14.5,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  resultsMainCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 14,
    marginTop: 4,
  },
  resultsCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 14,
  },
  resultsCardTitle: {
    color: "#FFF",
    fontSize: 14.5,
    fontWeight: "700",
  },
  btnProceedDiet: {
    backgroundColor: Colors.secondaryGold,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  btnProceedDietText: {
    color: "#000",
    fontSize: 11,
    fontWeight: "700",
  },
  riskTrioContainer: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 14,
  },
  riskMeterCard: {
    flex: 1,
    backgroundColor: "rgba(18, 9, 14, 0.95)",
    borderWidth: 1,
    borderColor: "rgba(16, 185, 129, 0.4)",
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 6,
    alignItems: "center",
    justifyContent: "space-between",
  },
  riskMeterCardActive: {
    borderColor: Colors.secondaryGold,
    backgroundColor: "rgba(35, 18, 28, 0.98)",
    shadowColor: Colors.secondaryGold,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 5,
    elevation: 4,
  },
  riskMeterTitle: {
    color: "#FFF",
    fontSize: 11.5,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 6,
  },
  gaugeContainer: {
    width: 80,
    height: 80,
    justifyContent: "center",
    alignItems: "center",
    marginVertical: 4,
  },
  gaugeInnerContent: {
    position: "absolute",
    justifyContent: "center",
    alignItems: "center",
  },
  gaugeScoreText: {
    color: "#FFF",
    fontSize: 14.5,
    fontWeight: "800",
  },
  gaugeScoreLabel: {
    color: Colors.textMuted,
    fontSize: 8,
    fontWeight: "600",
    letterSpacing: 0.5,
    marginTop: -2,
  },
  riskBadge: {
    paddingVertical: 3,
    paddingHorizontal: 10,
    borderRadius: 12,
    marginTop: 6,
  },
  riskBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  badgeLow: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    borderWidth: 1,
    borderColor: Colors.safeGreen,
  },
  badgeLowText: {
    color: Colors.safeGreen,
  },
  badgeMod: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1,
    borderColor: Colors.warningAmber,
  },
  badgeModText: {
    color: Colors.warningAmber,
  },
  badgeHigh: {
    backgroundColor: "rgba(244, 63, 94, 0.15)",
    borderWidth: 1,
    borderColor: Colors.dangerRose,
  },
  badgeHighText: {
    color: Colors.dangerRose,
  },
  cutoffsText: {
    color: Colors.textSubtle,
    fontSize: 7.5,
    fontWeight: "500",
    marginTop: 6,
    textAlign: "center",
  },
  detectedConditionsBox: {
    marginBottom: 14,
    paddingTop: 4,
  },
  detectedConditionsLabel: {
    color: Colors.secondaryGold,
    fontSize: 12,
    fontWeight: "700",
    marginBottom: 6,
  },
  conditionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  conditionPill: {
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
    paddingVertical: 4,
    paddingHorizontal: 9,
    borderRadius: 6,
  },
  conditionPillText: {
    color: Colors.secondaryLight,
    fontSize: 11,
    fontWeight: "600",
  },
  conditionPillSafe: {
    backgroundColor: "rgba(16, 185, 129, 0.12)",
    borderWidth: 1,
    borderColor: Colors.safeGreen,
    paddingVertical: 4,
    paddingHorizontal: 9,
    borderRadius: 6,
  },
  conditionPillSafeText: {
    color: Colors.safeGreen,
    fontSize: 11,
    fontWeight: "600",
  },
  explainabilityContainer: {
    backgroundColor: "rgba(18, 9, 14, 0.7)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    padding: 12,
  },
  explainHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 10,
  },
  explainHeaderTitle: {
    color: "#FFF",
    fontSize: 13,
    fontWeight: "700",
  },
  explainTabs: {
    flexDirection: "row",
    gap: 4,
  },
  explainTabBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  explainTabBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryLight,
  },
  explainTabBtnText: {
    color: Colors.textMuted,
    fontSize: 10.5,
    fontWeight: "600",
  },
  explainTabBtnTextActive: {
    color: "#FFF",
    fontWeight: "700",
  },
  explainContentCard: {
    marginTop: 4,
  },
  explainMetaBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: 8,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.08)",
  },
  explainDiseaseTitle: {
    color: "#FFF",
    fontSize: 13.5,
    fontWeight: "700",
  },
  explainRiskBadge: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  explainRiskBadgeText: {
    fontSize: 10,
    fontWeight: "700",
  },
  explainSection: {
    marginVertical: 6,
  },
  explainSectionHeader: {
    marginBottom: 4,
  },
  explainSectionTitle: {
    color: Colors.secondaryLight,
    fontSize: 12,
    fontWeight: "700",
  },
  explainListItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginVertical: 2,
    paddingLeft: 4,
  },
  explainBullet: {
    color: Colors.secondaryGold,
    fontSize: 12,
    marginRight: 6,
    lineHeight: 16,
  },
  explainListText: {
    flex: 1,
    color: Colors.textMain,
    fontSize: 11.5,
    lineHeight: 16,
  },
  pendingCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    alignItems: "center",
  },
  pendingText: {
    color: Colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    lineHeight: 18,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "center",
    padding: 16,
  },
  modalCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 18,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  modalTitle: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "700",
  },
  modalSubtitle: {
    color: Colors.textMuted,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 12,
  },
  modalTextInput: {
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 10,
    color: "#FFF",
    fontSize: 13,
    padding: 12,
    textAlignVertical: "top",
    minHeight: 110,
  },
  modalFooter: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 14,
  },
  modalCancelBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  modalCancelText: {
    color: Colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
  },
  modalApplyBtn: {
    backgroundColor: Colors.primary,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  modalApplyText: {
    color: "#FFF",
    fontSize: 13,
    fontWeight: "700",
  },

  /* Duplicate Notice Modal Styles */
  noticeModalCard: {
    backgroundColor: "#200914",
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: "rgba(245, 158, 11, 0.4)",
    padding: 18,
    width: "100%",
    maxWidth: 400,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.45,
    shadowRadius: 12,
    elevation: 8,
  },
  noticeModalHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.08)",
  },
  noticeIconBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    justifyContent: "center",
    alignItems: "center",
  },
  noticeModalTitle: {
    color: Colors.secondaryLight,
    fontSize: 14.5,
    fontWeight: "700",
  },
  noticeModalBody: {
    paddingVertical: 14,
  },
  noticeModalLead: {
    color: Colors.textMain,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  noticeModalSub: {
    color: Colors.textMuted,
    fontSize: 12,
    lineHeight: 17,
  },
  noticeModalBtn: {
    backgroundColor: Colors.secondary,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 4,
  },
  noticeModalBtnText: {
    color: "#000",
    fontSize: 13,
    fontWeight: "700",
  },
});
