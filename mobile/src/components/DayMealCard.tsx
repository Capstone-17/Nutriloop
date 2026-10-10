import React, { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { DayDietPlan } from "../types/clinical";
import { Colors } from "../theme/colors";

interface DayMealCardProps {
  day: DayDietPlan;
  initialExpanded?: boolean;
}

export const DayMealCard: React.FC<DayMealCardProps> = ({ day, initialExpanded = false }) => {
  const [expanded, setExpanded] = useState(initialExpanded);

  return (
    <View style={styles.card}>
      <TouchableOpacity
        style={styles.header}
        activeOpacity={0.8}
        onPress={() => setExpanded(!expanded)}
      >
        <View style={styles.headerTitleRow}>
          <Text style={styles.dayTitle}>
            Day {day.dayNumber}: {day.dayName}
          </Text>
          <View style={styles.macroPill}>
            <Text style={styles.macroPillText}>
              {day.dailyTotalNutrients.calories} kcal | P: {day.dailyTotalNutrients.proteinG}g | Na: {day.dailyTotalNutrients.sodiumMg}mg
            </Text>
          </View>
        </View>
        <Ionicons
          name={expanded ? "chevron-up" : "chevron-down"}
          size={18}
          color={Colors.secondary}
        />
      </TouchableOpacity>

      {expanded && (
        <View style={styles.body}>
          {day.intervals.map((inv, idx) => (
            <View key={idx} style={styles.intervalBlock}>
              <View style={styles.intervalHeader}>
                <Text style={styles.intervalName}>{inv.intervalName}</Text>
                <Text style={styles.intervalTime}>{inv.timeWindow}</Text>
              </View>

              <Text style={styles.mealTitle}>{inv.mealTitle}</Text>

              {inv.items.map((it, itemIdx) => (
                <Text key={itemIdx} style={styles.itemText}>
                  • <Text style={styles.itemName}>{it.itemName}</Text> ({it.portion})
                </Text>
              ))}

              <View style={styles.justificationBox}>
                <Text style={styles.justificationText}>
                  💡 <Text style={styles.justificationLabel}>Clinical Rationale:</Text> {inv.clinicalJustification}
                </Text>
              </View>

              <Text style={styles.prepTipText}>
                👨‍🍳 <Text style={styles.prepTipLabel}>Prep:</Text> {inv.prepTips}
              </Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    marginVertical: 6,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 14,
    backgroundColor: "rgba(155, 27, 48, 0.18)",
  },
  headerTitleRow: {
    flex: 1,
    marginRight: 10,
  },
  dayTitle: {
    color: Colors.textMain,
    fontSize: 16,
    fontWeight: "700",
  },
  macroPill: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginTop: 4,
    borderWidth: 0.5,
    borderColor: "rgba(245, 158, 11, 0.3)",
  },
  macroPillText: {
    color: Colors.secondaryLight,
    fontSize: 11,
    fontWeight: "600",
  },
  body: {
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: "rgba(212, 175, 55, 0.1)",
  },
  intervalBlock: {
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.06)",
  },
  intervalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 3,
  },
  intervalName: {
    color: Colors.secondary,
    fontSize: 13,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  intervalTime: {
    color: Colors.textSubtle,
    fontSize: 11,
  },
  mealTitle: {
    color: Colors.textMain,
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 6,
  },
  itemText: {
    color: Colors.textMuted,
    fontSize: 13,
    marginLeft: 6,
    marginVertical: 1,
  },
  itemName: {
    color: Colors.textMain,
    fontWeight: "500",
  },
  justificationBox: {
    backgroundColor: "rgba(20, 10, 16, 0.85)",
    padding: 8,
    borderRadius: 6,
    marginTop: 6,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  justificationText: {
    color: Colors.textMuted,
    fontSize: 11.5,
    lineHeight: 16,
  },
  justificationLabel: {
    color: Colors.secondaryLight,
    fontWeight: "600",
  },
  prepTipText: {
    color: Colors.textSubtle,
    fontSize: 11,
    marginTop: 4,
    marginLeft: 4,
  },
  prepTipLabel: {
    color: Colors.textMuted,
    fontWeight: "500",
  },
});
