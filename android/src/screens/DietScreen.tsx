import React, { useState, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";
import { PatientVitals, PatientPreferences, WeeklyDietPlan } from "../types/clinical";
import { ApiService } from "../services/api";
import { dbManager } from "../db/database";
import { formatDecimal } from "../utils/formatters";

interface DietScreenProps {
  vitals: PatientVitals;
  detectedConditions: string[];
  activePlan: WeeklyDietPlan | null;
  onPlanGenerated: (plan: WeeklyDietPlan) => void;
  reportDate?: string | null;
  isHistoricalTest?: boolean;
}

export const DietScreen: React.FC<DietScreenProps> = ({
  vitals,
  detectedConditions,
  activePlan,
  onPlanGenerated,
  reportDate,
  isHistoricalTest,
}) => {
  const scrollViewRef = useRef<ScrollView>(null);

  // Generation loading & tracking state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationCount, setGenerationCount] = useState(0);
  const [lastGeneratedAt, setLastGeneratedAt] = useState<string | null>(null);

  // 1. Regional Cuisine (Native Place)
  const [region, setRegion] = useState<PatientPreferences["nativeRegion"]>("south_indian");

  // 2. Dietary Pattern
  const [dietaryType, setDietaryType] = useState<PatientPreferences["dietaryType"]>("vegetarian");

  // 3. Cooking Skill
  const [cookingSkill, setCookingSkill] = useState<"intermediate" | "beginner" | "advanced">("intermediate");

  // 4. Max Prep Time (mins)
  const [prepTimeInput, setPrepTimeInput] = useState("30");

  // 5. Preferred Foods & Interests (Likes)
  const [likesInput, setLikesInput] = useState("millet, dalia, spinach");

  // 6. Food Allergens & Dislikes (Excluded)
  const [dislikesInput, setDislikesInput] = useState("");

  // 7. Active Medications (Drug-Nutrient Check)
  const [medicationsInput, setMedicationsInput] = useState("Lisinopril, Amlodipine");

  // 8. Smart Craving Sunday Treat (Optional)
  const [cravingInput, setCravingInput] = useState("");

  // Selected Day Index for Day Column Buttons (0 = Monday, 6 = Sunday)
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);

  // Toggle between Active Day Schedule and Grocery Checklist
  const [activeViewTab, setActiveViewTab] = useState<"meals" | "groceries">("meals");

  const regions: { key: PatientPreferences["nativeRegion"]; label: string; sub: string }[] = [
    { key: "south_indian", label: "South Indian", sub: "(Dosa, Idli, Rasam, Sambar)" },
    { key: "north_indian", label: "North Indian", sub: "(Roti, Dal, Paneer, Sabzi)" },
    { key: "western_indian", label: "Western Indian", sub: "(Gujarati/Maharashtrian)" },
    { key: "eastern_indian", label: "Eastern Indian", sub: "(Bengali/Odia)" },
    { key: "continental", label: "Continental", sub: "(Western / Balanced)" },
  ];

  const dietPatterns: { key: PatientPreferences["dietaryType"]; label: string }[] = [
    { key: "vegetarian", label: "Vegetarian" },
    { key: "non_vegetarian", label: "Non-Vegetarian" },
    { key: "vegan", label: "Vegan" },
    { key: "eggetarian", label: "Eggetarian" },
    { key: "jain", label: "Jain (No Onion/Garlic)" },
  ];

  const cookingSkills: Array<"beginner" | "intermediate" | "advanced"> = [
    "beginner",
    "intermediate",
    "advanced",
  ];

  const handleGeneratePlan = async () => {
    if (isGenerating) return;
    setIsGenerating(true);

    // Yield to let UI render the active loading state on button immediately
    setTimeout(async () => {
      try {
        // Multi-token delimiter splitting strictly matching desktop app gui/app.js:945-947
        const parseDelimited = (str: string) =>
          str
            .split(/[,;/+&]|\band\b/i)
            .map((s) => s.trim())
            .filter(Boolean);

        const meds = parseDelimited(medicationsInput);
        const likes = parseDelimited(likesInput);
        const dislikes = parseDelimited(dislikesInput);
        const prepMins = parseInt(prepTimeInput, 10) || 30;

        const prefs: PatientPreferences = {
          nativeRegion: region,
          dietaryType,
          cookingSkill,
          maxPrepTimeMins: prepMins,
          interestsAndLikes: likes,
          dislikes: dislikes,
          allergies: dislikes,
          activeMedications: meds,
          cravingOrTreat: cravingInput.trim() || undefined,
        };

        const plan = await ApiService.generateWeeklyDiet(
          vitals,
          prefs,
          reportDate || undefined,
          isHistoricalTest
        );

        onPlanGenerated(plan);
        await dbManager.saveActivePlan("patient_local", plan);

        setGenerationCount((c) => c + 1);
        const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        setLastGeneratedAt(timeStr);

        // Smoothly auto-scroll down to the generated plan
        setTimeout(() => {
          scrollViewRef.current?.scrollTo({ y: 550, animated: true });
        }, 120);
      } catch (err: any) {
        console.error("Failed to generate weekly diet plan:", err);
        const hostUrl = await ApiService.getBaseUrl();
        Alert.alert(
          "Server Connection Notice",
          `Could not generate 7-day diet plan via Nutriloop server at:\n${hostUrl}\n\n` +
          `Tips to connect:\n` +
          `1. Start backend: uvicorn backend.app:app --host 0.0.0.0 --port 8000\n` +
          `2. Tap the Server icon at the top of the screen to configure your computer's Wi-Fi IP (e.g. http://192.168.1.50:8000).`
        );
      } finally {
        setIsGenerating(false);
      }
    }, 100);
  };

  const selectedDay = activePlan?.days?.[selectedDayIdx];

  return (
    <ScrollView ref={scrollViewRef} style={styles.container} contentContainerStyle={styles.content}>
      {/* ──────────────────────────────────────────────────────────────────
          Historical Test Selected Warning Banner (Matches Desktop App UI)
          ────────────────────────────────────────────────────────────────── */}
      {isHistoricalTest && reportDate && (
        <View style={styles.historicalWarningBanner}>
          <Text style={styles.warningIcon}>⚠️</Text>
          <View style={styles.warningTextWrap}>
            <Text style={styles.warningTitle}>Historical Test Selected:</Text>
            <Text style={styles.warningSub}>
              Meal plan is being calibrated against report from{" "}
              <Text style={styles.warningDate}>
                {reportDate.substring(0, 16).replace("T", " ")}
              </Text>
              , not your latest test result.
            </Text>
          </View>
        </View>
      )}

      {/* ──────────────────────────────────────────────────────────────────
          Active Clinical Biomarker Calibration Summary Box
          ────────────────────────────────────────────────────────────────── */}
      <View style={styles.calibrationStatusBox}>
        <View style={styles.calibrationHeaderRow}>
          <View style={styles.calibIconBadge}>
            <Ionicons name="medical" size={13} color={Colors.secondary} />
          </View>
          <Text style={styles.calibrationStatusTitle}>
            🩺 Grounded in Lab Report ({reportDate ? reportDate.substring(0, 10) : "Active Outpatient Assessment"})
          </Text>
        </View>

        {/* 6 Core Biomarkers Driving Clinical Targets */}
        <View style={styles.biomarkerGrid}>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>Blood Pressure</Text>
            <Text style={styles.biomarkerChipVal}>
              {Math.round(vitals.systolicBpMmhg)}/{Math.round(vitals.diastolicBpMmhg)} mmHg
            </Text>
          </View>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>Fasting Glucose</Text>
            <Text style={styles.biomarkerChipVal}>{formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL</Text>
          </View>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>HbA1c</Text>
            <Text style={styles.biomarkerChipVal}>{formatDecimal(vitals.hba1cPct, 2)}%</Text>
          </View>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>Serum Creatinine</Text>
            <Text style={styles.biomarkerChipVal}>{formatDecimal(vitals.serumCreatinineMgDl, 2)} mg/dL</Text>
          </View>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>eGFR</Text>
            <Text style={styles.biomarkerChipVal}>{formatDecimal(vitals.egfrMlMin, 2)} mL/min</Text>
          </View>
          <View style={styles.biomarkerChip}>
            <Text style={styles.biomarkerChipLabel}>Serum Potassium</Text>
            <Text style={styles.biomarkerChipVal}>{formatDecimal(vitals.serumPotassiumMeqL, 2)} mEq/L</Text>
          </View>
        </View>

        {detectedConditions && detectedConditions.length > 0 && (
          <View style={styles.detectedConditionsRow}>
            {detectedConditions.map((cond, idx) => (
              <View key={idx} style={styles.calibConditionChip}>
                <Text style={styles.calibConditionText}>⚠️ {cond}</Text>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* ──────────────────────────────────────────────────────────────────
          1. Patient Cultural & Culinary Profile (Matches Desktop App UI)
          ────────────────────────────────────────────────────────────────── */}
      <View style={styles.profileCard}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardHeaderTitle}>🍲 Patient Cultural &amp; Culinary Profile</Text>
          <View style={styles.badgePill}>
            <Text style={styles.badgePillText}>PRECISION REBALANCING ENGINE</Text>
          </View>
        </View>

        {/* 1. Regional Cuisine (Native Place) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Regional Cuisine (Native Place)</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsScroll}>
            {regions.map((r) => (
              <TouchableOpacity
                key={r.key}
                style={[styles.chip, region === r.key && styles.chipActive]}
                onPress={() => setRegion(r.key)}
              >
                <Text style={[styles.chipText, region === r.key && styles.chipTextActive]}>
                  {r.label}
                </Text>
                <Text style={[styles.chipSubText, region === r.key && styles.chipSubTextActive]}>
                  {r.sub}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* 2. Dietary Pattern (Full Width Line) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Dietary Pattern</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsScroll}>
            {dietPatterns.map((dp) => (
              <TouchableOpacity
                key={dp.key}
                style={[styles.chip, dietaryType === dp.key && styles.chipActive]}
                onPress={() => setDietaryType(dp.key)}
              >
                <Text style={[styles.chipText, dietaryType === dp.key && styles.chipTextActive]}>
                  {dp.label}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* 3. Cooking Skill & Prep (Full Width Line on Next Line) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Cooking Skill &amp; Prep</Text>
          <View style={styles.skillFullRow}>
            {cookingSkills.map((sk) => (
              <TouchableOpacity
                key={sk}
                style={[styles.skillFullChip, cookingSkill === sk && styles.skillFullChipActive]}
                onPress={() => setCookingSkill(sk)}
              >
                <Text style={[styles.skillFullChipText, cookingSkill === sk && styles.skillFullChipTextActive]}>
                  {sk.charAt(0).toUpperCase() + sk.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Max Prep Time Input */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Max Prep Time (mins)</Text>
          <TextInput
            style={styles.formInput}
            value={prepTimeInput}
            onChangeText={setPrepTimeInput}
            keyboardType="number-pad"
            placeholder="30"
            placeholderTextColor={Colors.textSubtle}
          />
        </View>

        {/* 3. Preferred Foods & Interests (Likes) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Preferred Foods &amp; Interests (Likes)</Text>
          <TextInput
            style={styles.formInput}
            value={likesInput}
            onChangeText={setLikesInput}
            placeholder="e.g. oats, paneer, ragi, khichdi"
            placeholderTextColor={Colors.textSubtle}
          />
          <Text style={styles.inputHint}>Separated by commas. Prioritized with ⭐ badge.</Text>
        </View>

        {/* 4. Food Allergens & Dislikes (Excluded) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Food Allergens &amp; Dislikes (Excluded)</Text>
          <TextInput
            style={styles.formInput}
            value={dislikesInput}
            onChangeText={setDislikesInput}
            placeholder="e.g. None, peanuts, mushrooms"
            placeholderTextColor={Colors.textSubtle}
          />
          <Text style={styles.inputHint}>Zero-tolerance clinical exclusion scrubber.</Text>
        </View>

        {/* 5. Active Medications (Drug-Nutrient Check) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>Active Medications (Drug-Nutrient Check)</Text>
          <TextInput
            style={styles.formInput}
            value={medicationsInput}
            onChangeText={setMedicationsInput}
            placeholder="e.g. None, or metformin, lisinopril"
            placeholderTextColor={Colors.textSubtle}
          />
          <Text style={styles.inputHint}>Cross-referenced against clinical pharmacopeia.</Text>
        </View>

        {/* 6. Smart Craving Sunday Treat (Optional) */}
        <View style={styles.formGroup}>
          <Text style={styles.formLabel}>🍧 Smart Craving Sunday Treat (Optional)</Text>
          <TextInput
            style={styles.formInput}
            value={cravingInput}
            onChangeText={setCravingInput}
            placeholder="e.g. Pizza, Gulab Jamun, Biryani"
            placeholderTextColor={Colors.textSubtle}
          />
          <Text style={styles.inputHint}>Strictly budgeted for Sunday (Day 7) metabolic lock.</Text>
        </View>

        {/* Generate Diet Plan Button */}
        <TouchableOpacity
          style={[styles.btnGenerate, isGenerating && styles.btnGenerateDisabled]}
          activeOpacity={0.85}
          onPress={handleGeneratePlan}
          disabled={isGenerating}
        >
          {isGenerating ? (
            <>
              <ActivityIndicator size="small" color="#FFF" />
              <Text style={styles.btnGenerateText}>⏳ Assembling Personalized 7-Day Plan...</Text>
            </>
          ) : (
            <>
              <Text style={styles.btnGenerateIcon}>🥗</Text>
              <Text style={styles.btnGenerateText}>Generate Personalized 7-Day Regional Diet</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* ──────────────────────────────────────────────────────────────────
          2. 7-Day Clinically Rebalanced Diet Schedule Results
          ────────────────────────────────────────────────────────────────── */}
      {activePlan ? (
        <View style={styles.resultsCard}>
          <View style={styles.resultsHeaderRow}>
            <View style={styles.resultsTitleCol}>
              <Text style={styles.resultsHeading}>📅 7-Day Clinically Rebalanced Schedule</Text>
              {lastGeneratedAt && (
                <Text style={styles.generationNoticeSub}>
                  ✨ Assembled iteration #{generationCount} • {lastGeneratedAt}
                </Text>
              )}
            </View>
            <View style={styles.resultsActionsRow}>
              <TouchableOpacity
                style={[styles.btnQuickRegenerate, isGenerating && styles.btnQuickRegenerateDisabled]}
                onPress={handleGeneratePlan}
                disabled={isGenerating}
                activeOpacity={0.8}
              >
                {isGenerating ? (
                  <ActivityIndicator size="small" color="#FBBF24" />
                ) : (
                  <>
                    <Ionicons name="shuffle" size={12} color="#FBBF24" />
                    <Text style={styles.btnQuickRegenerateText}>Rotate Variety</Text>
                  </>
                )}
              </TouchableOpacity>
              <Text style={styles.regionTag}>{activePlan.nativeRegion}</Text>
            </View>
          </View>

          {/* Caloric & Macronutrient Targets Summary Grid (Matches Desktop App UI) */}
          <View style={styles.targetsGrid}>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🔥 Caloric Target</Text>
              <Text style={styles.targetValue}>{formatDecimal(activePlan.caloricTargetKcal, 2)} kcal</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🥩 Daily Protein</Text>
              <Text style={styles.targetValue}>{formatDecimal(activePlan.proteinTargetG, 2)}g</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🌾 Carb Floor</Text>
              <Text style={styles.targetValue}>
                {formatDecimal(activePlan.carbohydrateTargetG || Math.round((activePlan.caloricTargetKcal * 0.45) / 4), 2)}g
              </Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🥑 Healthy Fats</Text>
              <Text style={styles.targetValue}>{formatDecimal(activePlan.fatTargetG || 50, 2)}g</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🥦 Dietary Fiber</Text>
              <Text style={styles.targetValue}>&ge; {formatDecimal(activePlan.fiberTargetG || 28, 2)}g</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🧂 Sodium Limit</Text>
              <Text style={styles.targetValue}>&le; {formatDecimal(activePlan.sodiumTargetMg, 2)}mg</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>⚡ Potassium Cap</Text>
              <Text style={styles.targetValue}>&le; {formatDecimal(activePlan.potassiumTargetMg, 2)}mg</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>💧 Fluid Intake</Text>
              <Text style={styles.targetValue}>{formatDecimal(activePlan.fluidIntakeMl || 2000, 2)}ml</Text>
            </View>
            <View style={styles.targetCol}>
              <Text style={styles.targetLabel}>🏛️ Cuisine Tradition</Text>
              <Text style={styles.targetValue}>{activePlan.nativeRegion}</Text>
            </View>
          </View>

          {/* Active Medication Pharmacopeia Warnings */}
          {activePlan.medicationAlerts.length > 0 && (
            <View style={styles.medAlertsBox}>
              <View style={styles.medAlertHeader}>
                <Ionicons name="warning" size={16} color={Colors.warningAmber} />
                <Text style={styles.medAlertTitle}>Clinical Pharmacopeia Guardrails Active</Text>
              </View>
              {activePlan.medicationAlerts.map((alert, idx) => (
                <Text key={idx} style={styles.medAlertText}>
                  • {alert}
                </Text>
              ))}
            </View>
          )}

          {/* Sunday Craving Rebalancing Strategy Banner */}
          {activePlan.cravingStrategy && (
            <View style={styles.cravingBox}>
              <Text style={styles.cravingTitle}>
                🎯 Sunday Indulgence Scheduled: {activePlan.cravingStrategy.requestedCraving}
              </Text>
              <Text style={styles.cravingText}>
                ⚖️ {activePlan.cravingStrategy.metabolicRebalanceNote}
              </Text>
              <Text style={styles.cravingLock}>
                🔒 {activePlan.cravingStrategy.sixDayLockNote}
              </Text>
            </View>
          )}

          {/* Toggle between Day Schedule and Grocery List */}
          <View style={styles.viewToggleRow}>
            <TouchableOpacity
              style={[styles.viewToggleBtn, activeViewTab === "meals" && styles.viewToggleBtnActive]}
              onPress={() => setActiveViewTab("meals")}
            >
              <Ionicons name="calendar-outline" size={15} color={activeViewTab === "meals" ? "#FFF" : Colors.textMuted} />
              <Text style={[styles.viewToggleText, activeViewTab === "meals" && styles.viewToggleTextActive]}>
                Day-by-Day Schedule
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.viewToggleBtn, activeViewTab === "groceries" && styles.viewToggleBtnActive]}
              onPress={() => setActiveViewTab("groceries")}
            >
              <Ionicons name="cart-outline" size={15} color={activeViewTab === "groceries" ? "#FFF" : Colors.textMuted} />
              <Text style={[styles.viewToggleText, activeViewTab === "groceries" && styles.viewToggleTextActive]}>
                Grocery Checklist
              </Text>
            </TouchableOpacity>
          </View>

          {activeViewTab === "meals" ? (
            <View style={styles.dayNavigatorContainer}>
              {/* ────────────────────────────────────────────────────────
                  7-Day Column Button Navigator (Matches Desktop App UI)
                  ──────────────────────────────────────────────────────── */}
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                style={styles.dayButtonsScroll}
                contentContainerStyle={styles.dayButtonsContainer}
              >
                {activePlan.days.map((day, idx) => {
                  const isActive = idx === selectedDayIdx;
                  return (
                    <TouchableOpacity
                      key={day.dayNumber}
                      style={[styles.dayColBtn, isActive && styles.dayColBtnActive]}
                      onPress={() => setSelectedDayIdx(idx)}
                      activeOpacity={0.8}
                    >
                      <Text style={[styles.dayColBtnNumber, isActive && styles.dayColBtnNumberActive]}>
                        Day {day.dayNumber}
                      </Text>
                      <Text style={[styles.dayColBtnName, isActive && styles.dayColBtnNameActive]}>
                        {day.dayName.slice(0, 3)}
                      </Text>
                      <Text style={[styles.dayColBtnCal, isActive && styles.dayColBtnCalActive]}>
                        {formatDecimal(day.dailyTotalNutrients.calories, 2)} kcal
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              {/* Active Day Detailed View */}
              {selectedDay && (
                <View style={styles.activeDayView}>
                  <View style={styles.activeDayBanner}>
                    <View style={styles.activeDayTitleWrap}>
                      <View style={styles.dayBadge}>
                        <Text style={styles.dayBadgeText}>Day {selectedDay.dayNumber}</Text>
                      </View>
                      <Text style={styles.activeDayTitle}>
                        {selectedDay.dayName} Clinically Rebalanced Regimen
                      </Text>
                    </View>

                    {/* Day Metrics Strip */}
                    <View style={styles.dayMetricsStrip}>
                      <View style={styles.metricPill}>
                        <Text style={styles.metricIcon}>🔥</Text>
                        <Text style={styles.metricText}>
                          <Text style={styles.metricBold}>{formatDecimal(selectedDay.dailyTotalNutrients.calories, 2)}</Text> kcal
                        </Text>
                      </View>
                      <View style={styles.metricPill}>
                        <Text style={styles.metricIcon}>🥩</Text>
                        <Text style={styles.metricText}>
                          P: <Text style={styles.metricBold}>{formatDecimal(selectedDay.dailyTotalNutrients.proteinG, 2)}</Text>g
                        </Text>
                      </View>
                      <View style={styles.metricPill}>
                        <Text style={styles.metricIcon}>🧂</Text>
                        <Text style={styles.metricText}>
                          Na: <Text style={styles.metricBold}>{formatDecimal(selectedDay.dailyTotalNutrients.sodiumMg, 2)}</Text>mg
                        </Text>
                      </View>
                    </View>
                  </View>

                  {/* 5 Interval Cards for Active Day */}
                  {selectedDay.intervals.map((interval, iIdx) => (
                    <View key={iIdx} style={styles.intervalCard}>
                      <View style={styles.intervalHeader}>
                        <View style={styles.intervalTitleCol}>
                          <Text style={styles.intervalName}>{interval.intervalName}</Text>
                          <Text style={styles.intervalTime}>⏰ {interval.timeWindow}</Text>
                        </View>
                        <View style={styles.intervalCalBadge}>
                          <Text style={styles.intervalCalText}>
                            {formatDecimal(interval.totalNutrients.calories, 2)} kcal
                          </Text>
                        </View>
                      </View>

                      <Text style={styles.mealTitle}>{interval.mealTitle}</Text>

                      {/* Scaled Meal Items */}
                      <View style={styles.itemsBlock}>
                        {interval.items.map((it, itIdx) => (
                          <View key={itIdx} style={styles.itemRow}>
                            <View style={styles.itemBullet} />
                            <Text style={styles.itemName}>{it.itemName}</Text>
                            <Text style={styles.itemPortion}>{it.portion}</Text>
                          </View>
                        ))}
                      </View>

                      {/* Clinical Justification */}
                      <View style={styles.justificationBox}>
                        <Text style={styles.justificationText}>
                          💡 <Text style={styles.justificationBold}>Clinical Basis:</Text>{" "}
                          {interval.clinicalJustification}
                        </Text>
                      </View>

                      {/* Prep tips */}
                      {interval.prepTips ? (
                        <Text style={styles.prepTipsText}>
                          🍳 <Text style={styles.prepTipsBold}>Prep Tips:</Text> {interval.prepTips}
                        </Text>
                      ) : null}
                    </View>
                  ))}
                </View>
              )}
            </View>
          ) : (
            /* Categorized Grocery Checklist */
            <View style={styles.groceryCard}>
              <Text style={styles.groceryCardTitle}>🛒 Categorized Weekly Grocery Checklist</Text>
              {Object.entries(activePlan.categorizedGroceries).map(([category, items], cIdx) => (
                <View key={cIdx} style={styles.groceryCategoryBlock}>
                  <Text style={styles.groceryCategoryHeading}>{category}</Text>
                  {items.map((it, itIdx) => (
                    <Text key={itIdx} style={styles.groceryItemText}>
                      ☑️ {it}
                    </Text>
                  ))}
                </View>
              ))}
            </View>
          )}
        </View>
      ) : (
        <View style={styles.placeholderCard}>
          <Text style={styles.placeholderIcon}>🥗</Text>
          <Text style={styles.placeholderTitle}>No Diet Plan Generated Yet</Text>
          <Text style={styles.placeholderDesc}>
            Configure your cultural preferences and clinical targets above, then tap "Generate Personalized 7-Day Regional Diet".
          </Text>
        </View>
      )}

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
  historicalWarningBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderLeftWidth: 4,
    borderLeftColor: Colors.secondary,
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
    gap: 10,
  },
  warningIcon: {
    fontSize: 20,
  },
  warningTextWrap: {
    flex: 1,
  },
  warningTitle: {
    color: Colors.secondaryLight,
    fontSize: 13,
    fontWeight: "700",
  },
  warningSub: {
    color: Colors.textMain,
    fontSize: 11.5,
    marginTop: 2,
    lineHeight: 16,
  },
  warningDate: {
    fontWeight: "700",
    textDecorationLine: "underline",
    color: Colors.secondary,
  },
  calibrationStatusBox: {
    backgroundColor: "rgba(30, 11, 20, 0.95)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.35)",
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
  },
  calibrationHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
    gap: 8,
  },
  calibIconBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    justifyContent: "center",
    alignItems: "center",
  },
  calibrationStatusTitle: {
    color: Colors.secondaryLight,
    fontSize: 13,
    fontWeight: "700",
    flex: 1,
  },
  biomarkerGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 8,
  },
  biomarkerChip: {
    width: "48.5%",
    backgroundColor: "rgba(255, 255, 255, 0.04)",
    borderRadius: 6,
    paddingVertical: 5,
    paddingHorizontal: 8,
    borderWidth: 0.5,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  biomarkerChipLabel: {
    color: Colors.textMuted,
    fontSize: 9.5,
    fontWeight: "600",
  },
  biomarkerChipVal: {
    color: Colors.textMain,
    fontSize: 11.5,
    fontWeight: "700",
    marginTop: 1,
  },
  detectedConditionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  calibConditionChip: {
    backgroundColor: "rgba(244, 63, 94, 0.12)",
    borderWidth: 0.5,
    borderColor: "rgba(244, 63, 94, 0.35)",
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  calibConditionText: {
    color: Colors.dangerRose,
    fontSize: 10.5,
    fontWeight: "600",
  },
  profileCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 16,
    marginBottom: 14,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
    flexWrap: "wrap",
    gap: 8,
  },
  cardHeaderTitle: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "700",
  },
  badgePill: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    borderWidth: 1,
    borderColor: Colors.safeGreen,
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  badgePillText: {
    color: Colors.safeGreen,
    fontSize: 9.5,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  formGroup: {
    marginBottom: 12,
  },
  formLabel: {
    color: "#FBBF24",
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 6,
  },
  chipsScroll: {
    marginVertical: 2,
  },
  chip: {
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    borderRadius: 8,
    paddingVertical: 7,
    paddingHorizontal: 12,
    marginRight: 8,
  },
  chipActive: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderColor: Colors.secondary,
  },
  chipText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#FFF",
    fontWeight: "700",
  },
  chipSubText: {
    color: Colors.textSubtle,
    fontSize: 9.5,
    marginTop: 1,
  },
  chipSubTextActive: {
    color: Colors.secondaryLight,
  },
  skillFullRow: {
    flexDirection: "row",
    gap: 8,
    width: "100%",
    marginTop: 2,
  },
  skillFullChip: {
    flex: 1,
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  skillFullChipActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryLight,
  },
  skillFullChipText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  skillFullChipTextActive: {
    color: "#FFF",
    fontWeight: "700",
  },
  formInput: {
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 8,
    color: "#FFF",
    fontSize: 13,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  inputHint: {
    color: Colors.textSubtle,
    fontSize: 10,
    marginTop: 4,
  },
  btnGenerate: {
    backgroundColor: "#10B981",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 13,
    borderRadius: 10,
    marginTop: 8,
    shadowColor: "#10B981",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35,
    shadowRadius: 6,
    elevation: 4,
  },
  btnGenerateDisabled: {
    opacity: 0.7,
    backgroundColor: "#059669",
  },
  btnGenerateIcon: {
    fontSize: 18,
  },
  btnGenerateText: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 0.3,
  },
  resultsCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 16,
  },
  resultsHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  resultsTitleCol: {
    flex: 1,
    marginRight: 8,
  },
  generationNoticeSub: {
    color: "#FBBF24",
    fontSize: 10,
    fontWeight: "600",
    marginTop: 2,
    opacity: 0.9,
  },
  resultsActionsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  btnQuickRegenerate: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.35)",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    minHeight: 38,
    justifyContent: "center",
  },
  btnQuickRegenerateDisabled: {
    opacity: 0.6,
  },
  btnQuickRegenerateText: {
    color: "#FBBF24",
    fontSize: 10.5,
    fontWeight: "700",
  },
  resultsHeading: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "700",
  },
  regionTag: {
    color: Colors.secondaryLight,
    fontSize: 11,
    fontWeight: "700",
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  targetsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginBottom: 14,
  },
  targetCol: {
    width: "31.5%",
    backgroundColor: Colors.bgInput,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    alignItems: "center",
  },
  targetLabel: {
    color: Colors.textMuted,
    fontSize: 9.5,
    fontWeight: "600",
    marginBottom: 3,
    textAlign: "center",
  },
  targetValue: {
    color: "#FFF",
    fontSize: 11.5,
    fontWeight: "700",
    textAlign: "center",
  },
  medAlertsBox: {
    backgroundColor: "rgba(245, 158, 11, 0.1)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  medAlertHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 6,
  },
  medAlertTitle: {
    color: Colors.secondaryLight,
    fontSize: 12.5,
    fontWeight: "700",
  },
  medAlertText: {
    color: Colors.textMain,
    fontSize: 11.5,
    lineHeight: 17,
    marginTop: 2,
  },
  cravingBox: {
    backgroundColor: "rgba(155, 27, 48, 0.15)",
    borderWidth: 1,
    borderColor: Colors.primaryLight,
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  cravingTitle: {
    color: "#FFF",
    fontSize: 13,
    fontWeight: "700",
  },
  cravingText: {
    color: Colors.secondaryLight,
    fontSize: 11.5,
    marginTop: 4,
  },
  cravingLock: {
    color: Colors.textMuted,
    fontSize: 10.5,
    marginTop: 3,
  },
  viewToggleRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 14,
  },
  viewToggleBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    minHeight: 44,
    borderRadius: 8,
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  viewToggleBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryLight,
  },
  viewToggleText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  viewToggleTextActive: {
    color: "#FFF",
    fontWeight: "700",
  },
  dayNavigatorContainer: {
    marginTop: 2,
  },
  dayButtonsScroll: {
    marginBottom: 14,
  },
  dayButtonsContainer: {
    flexDirection: "row",
    gap: 6,
  },
  dayColBtn: {
    width: 68,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderRadius: 8,
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    alignItems: "center",
  },
  dayColBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.secondaryGold,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 3,
  },
  dayColBtnNumber: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  dayColBtnNumberActive: {
    color: "#FFF",
  },
  dayColBtnName: {
    color: Colors.secondaryLight,
    fontSize: 10,
    fontWeight: "600",
    marginTop: 1,
  },
  dayColBtnNameActive: {
    color: "#FFF",
  },
  dayColBtnCal: {
    color: Colors.textSubtle,
    fontSize: 9,
    marginTop: 3,
  },
  dayColBtnCalActive: {
    color: Colors.secondaryLight,
    fontWeight: "700",
  },
  activeDayView: {
    marginTop: 2,
  },
  activeDayBanner: {
    backgroundColor: Colors.bgInput,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 12,
    marginBottom: 12,
  },
  activeDayTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  dayBadge: {
    backgroundColor: Colors.primary,
    borderRadius: 6,
    paddingVertical: 2,
    paddingHorizontal: 6,
  },
  dayBadgeText: {
    color: "#FFF",
    fontSize: 11,
    fontWeight: "700",
  },
  activeDayTitle: {
    color: "#FFF",
    fontSize: 13.5,
    fontWeight: "700",
    flex: 1,
  },
  dayMetricsStrip: {
    flexDirection: "row",
    gap: 8,
  },
  metricPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  metricIcon: {
    fontSize: 11,
  },
  metricText: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  metricBold: {
    color: "#FFF",
    fontWeight: "700",
  },
  intervalCard: {
    backgroundColor: "rgba(24, 12, 19, 0.95)",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    padding: 12,
    marginBottom: 10,
  },
  intervalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  intervalTitleCol: {
    flex: 1,
  },
  intervalName: {
    color: Colors.secondaryLight,
    fontSize: 12.5,
    fontWeight: "700",
  },
  intervalTime: {
    color: Colors.textSubtle,
    fontSize: 10.5,
    marginTop: 1,
  },
  intervalCalBadge: {
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    paddingVertical: 3,
    paddingHorizontal: 7,
    borderRadius: 6,
  },
  intervalCalText: {
    color: Colors.secondary,
    fontSize: 11,
    fontWeight: "700",
  },
  mealTitle: {
    color: "#FFF",
    fontSize: 13.5,
    fontWeight: "700",
    marginBottom: 8,
  },
  itemsBlock: {
    backgroundColor: Colors.bgInput,
    borderRadius: 8,
    padding: 8,
    marginBottom: 8,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 3,
  },
  itemBullet: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.secondary,
    marginRight: 6,
  },
  itemName: {
    color: Colors.textMain,
    fontSize: 12,
    fontWeight: "600",
    flex: 1,
  },
  itemPortion: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  justificationBox: {
    backgroundColor: "rgba(16, 185, 129, 0.08)",
    borderLeftWidth: 3,
    borderLeftColor: Colors.safeGreen,
    padding: 8,
    borderRadius: 4,
    marginBottom: 6,
  },
  justificationText: {
    color: Colors.textMain,
    fontSize: 11,
    lineHeight: 16,
  },
  justificationBold: {
    fontWeight: "700",
    color: Colors.safeGreen,
  },
  prepTipsText: {
    color: Colors.textMuted,
    fontSize: 11,
    lineHeight: 15,
  },
  prepTipsBold: {
    fontWeight: "600",
    color: Colors.textMain,
  },
  groceryCard: {
    backgroundColor: Colors.bgInput,
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  groceryCardTitle: {
    color: "#FFF",
    fontSize: 13.5,
    fontWeight: "700",
    marginBottom: 10,
  },
  groceryCategoryBlock: {
    marginBottom: 12,
  },
  groceryCategoryHeading: {
    color: Colors.secondaryLight,
    fontSize: 12,
    fontWeight: "700",
    marginBottom: 4,
  },
  groceryItemText: {
    color: Colors.textMuted,
    fontSize: 11.5,
    lineHeight: 18,
    marginLeft: 6,
  },
  placeholderCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    padding: 30,
    alignItems: "center",
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  placeholderIcon: {
    fontSize: 42,
    marginBottom: 10,
  },
  placeholderTitle: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 6,
  },
  placeholderDesc: {
    color: Colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    lineHeight: 18,
  },
});
