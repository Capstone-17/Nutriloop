import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Slider from "@react-native-community/slider";
import { Colors } from "../theme/colors";
import { formatDecimal } from "../utils/formatters";

interface VitalSliderCardProps {
  title: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  statusText?: string;
  statusType?: "normal" | "warning" | "danger";
  onValueChange: (val: number) => void;
}

export const VitalSliderCard: React.FC<VitalSliderCardProps> = ({
  title,
  value,
  min,
  max,
  step = 1,
  unit,
  statusText,
  statusType = "normal",
  onValueChange,
}) => {
  const badgeBg =
    statusType === "danger"
      ? Colors.badgeHighBg
      : statusType === "warning"
      ? Colors.badgeModBg
      : Colors.badgeLowBg;

  const badgeColor =
    statusType === "danger"
      ? Colors.dangerRose
      : statusType === "warning"
      ? Colors.warningAmber
      : Colors.safeGreen;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.titleText} numberOfLines={1}>
          {title}
        </Text>
        <View style={[styles.badge, { backgroundColor: badgeBg, borderColor: badgeColor }]}>
          <Text style={[styles.badgeText, { color: badgeColor }]}>
            {formatDecimal(value, 2)} {unit}
          </Text>
        </View>
      </View>

      {statusText ? (
        <Text style={[styles.statusSubtext, { color: badgeColor }]} numberOfLines={1}>
          {statusText}
        </Text>
      ) : null}

      <Slider
        style={styles.slider}
        minimumValue={min}
        maximumValue={max}
        step={step}
        value={value}
        onValueChange={onValueChange}
        minimumTrackTintColor={Colors.primary}
        maximumTrackTintColor="rgba(212, 175, 55, 0.2)"
        thumbTintColor={Colors.secondary}
      />

      <View style={styles.limitsRow}>
        <Text style={styles.limitText}>
          {min} {unit}
        </Text>
        <Text style={styles.limitText}>
          {max} {unit}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 10,
    padding: 10,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: Colors.borderCard,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 4,
  },
  titleText: {
    flex: 1,
    color: Colors.textMain,
    fontSize: 12,
    fontWeight: "700",
  },
  badge: {
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 6,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 10.5,
    fontWeight: "700",
  },
  statusSubtext: {
    fontSize: 9.5,
    fontWeight: "600",
    marginTop: 2,
    marginBottom: 1,
  },
  slider: {
    width: "100%",
    height: 32,
    marginVertical: 0,
  },
  limitsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 2,
  },
  limitText: {
    color: Colors.textSubtle,
    fontSize: 9,
    fontWeight: "500",
  },
});
