import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { Colors } from "../theme/colors";
import { formatDecimal } from "../utils/formatters";

interface NutriGaugeProps {
  value: number;
  min: number;
  max: number;
  unit: string;
  label: string;
  strokeColor?: string;
  size?: number;
}

export const NutriGauge: React.FC<NutriGaugeProps> = ({
  value,
  min,
  max,
  unit,
  label,
  strokeColor = Colors.secondary,
  size = 100,
}) => {
  const strokeWidth = 8;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const strokeDashoffset = circumference - progress * circumference * 0.75;

  return (
    <View style={[styles.container, { width: size, height: size + 20 }]}>
      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background track circle */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(212, 175, 55, 0.15)"
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform={`rotate(135 ${size / 2} ${size / 2})`}
        />
        {/* Animated active stroke */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform={`rotate(135 ${size / 2} ${size / 2})`}
        />
      </Svg>

      <View style={styles.centerTextContainer}>
        <Text style={styles.valueText}>
          {formatDecimal(value, 2)}
        </Text>
        <Text style={styles.unitText}>{unit}</Text>
      </View>

      <Text style={styles.labelText} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: 4,
  },
  centerTextContainer: {
    position: "absolute",
    top: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  valueText: {
    color: Colors.textMain,
    fontSize: 16,
    fontWeight: "700",
  },
  unitText: {
    color: Colors.textMuted,
    fontSize: 10,
    marginTop: -2,
  },
  labelText: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "500",
  },
});
