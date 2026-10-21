import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";

interface MedicalDisclaimerModalProps {
  visible: boolean;
  onAccept: () => void;
}

export const MedicalDisclaimerModal: React.FC<MedicalDisclaimerModalProps> = ({
  visible,
  onAccept,
}) => {
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={() => {
        // Prevent back-button dismiss; acceptance is mandatory for clinical safety
      }}
    >
      <View style={styles.overlay}>
        <View style={styles.card}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.shieldIconContainer}>
              <Ionicons name="shield-checkmark" size={28} color={Colors.secondary} />
            </View>
            <View style={styles.headerTextCol}>
              <Text style={styles.title}>Clinical & Medical Disclaimer</Text>
              <Text style={styles.subtitle}>KDIGO 2024 • ADA 2024 • AHA DASH</Text>
            </View>
          </View>

          {/* Content Body */}
          <ScrollView
            style={styles.body}
            contentContainerStyle={styles.bodyContent}
            onScroll={({ nativeEvent }) => {
              const { layoutMeasurement, contentOffset, contentSize } = nativeEvent;
              const isCloseToBottom =
                layoutMeasurement.height + contentOffset.y >= contentSize.height - 40;
              if (isCloseToBottom && !hasScrolledToBottom) {
                setHasScrolledToBottom(true);
              }
            }}
            scrollEventThrottle={16}
          >
            <View style={styles.warningBox}>
              <Ionicons name="warning" size={18} color={Colors.warningAmber} />
              <Text style={styles.warningText}>
                NutriLoop is an AI-augmented dietary decision support tool. It does NOT provide definitive medical diagnoses or prescribe pharmaceutical regimens.
              </Text>
            </View>

            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="fitness-outline" size={16} color={Colors.secondary} />
                <Text style={styles.sectionTitle}>1. Supplemental Dietary Support</Text>
              </View>
              <Text style={styles.sectionBody}>
                All risk assessments, renal/glycemic/cardiovascular dietary targets, and meal plans are generated using machine learning models calibrated to clinical benchmarks. These recommendations are intended to assist in informed nutritional choices and lifestyle management.
              </Text>
            </View>

            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="medkit-outline" size={16} color={Colors.secondary} />
                <Text style={styles.sectionTitle}>2. Consult Your Healthcare Provider</Text>
              </View>
              <Text style={styles.sectionBody}>
                Always consult your nephrologist, endocrinologist, cardiologist, or registered dietitian before making significant changes to your electrolyte (potassium, sodium, phosphorus) or macronutrient intake, particularly if you are prescribed ACE inhibitors, ARBs, diuretics, or insulin.
              </Text>
            </View>

            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="alert-circle-outline" size={16} color={Colors.dangerRose} />
                <Text style={styles.sectionTitle}>3. Acute Emergencies</Text>
              </View>
              <Text style={styles.sectionBody}>
                If you experience sudden shortness of breath, chest pressure, severe peripheral edema, extreme hyperglycemia/hypoglycemia, or muscle weakness, immediately seek emergency medical attention or contact your local hospital.
              </Text>
            </View>

            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="lock-closed-outline" size={16} color={Colors.safeGreen} />
                <Text style={styles.sectionTitle}>4. Data Privacy & Confidentiality</Text>
              </View>
              <Text style={styles.sectionBody}>
                Biomarkers and dietary history are stored locally in on-device encrypted storage and transmitted exclusively over secure endpoints. No patient health identifiers are shared with third parties.
              </Text>
            </View>
          </ScrollView>

          {/* Action Footer */}
          <View style={styles.footer}>
            <TouchableOpacity
              style={styles.acceptButton}
              activeOpacity={0.85}
              onPress={onAccept}
            >
              <Ionicons name="checkmark-circle" size={20} color="#FFFFFF" />
              <Text style={styles.acceptButtonText}>I Understand and Accept</Text>
            </TouchableOpacity>
            <Text style={styles.footerNote}>
              By proceeding, you acknowledge that you have reviewed and understand this clinical disclaimer.
            </Text>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.85)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: Platform.OS === "ios" ? 44 : 24,
  },
  card: {
    width: "100%",
    maxHeight: "88%",
    backgroundColor: Colors.bgSurface,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: Colors.borderCard,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 12,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 18,
    backgroundColor: "rgba(155, 27, 48, 0.25)",
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
    gap: 14,
  },
  shieldIconContainer: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1.5,
    borderColor: Colors.secondary,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTextCol: {
    flex: 1,
  },
  title: {
    fontSize: 17,
    fontWeight: "800",
    color: Colors.textMain,
    letterSpacing: 0.3,
  },
  subtitle: {
    fontSize: 11,
    fontWeight: "600",
    color: Colors.secondary,
    marginTop: 2,
    letterSpacing: 0.5,
  },
  body: {
    maxHeight: 380,
  },
  bodyContent: {
    padding: 20,
    gap: 16,
  },
  warningBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderLeftWidth: 3.5,
    borderLeftColor: Colors.warningAmber,
    padding: 12,
    borderRadius: 8,
    gap: 10,
  },
  warningText: {
    flex: 1,
    fontSize: 12.5,
    lineHeight: 18,
    fontWeight: "600",
    color: "#FDE68A",
  },
  section: {
    gap: 6,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sectionTitle: {
    fontSize: 13.5,
    fontWeight: "700",
    color: Colors.textMain,
  },
  sectionBody: {
    fontSize: 12,
    lineHeight: 17,
    color: Colors.textMuted,
    paddingLeft: 24,
  },
  footer: {
    padding: 18,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    backgroundColor: "rgba(20, 10, 16, 0.95)",
    gap: 10,
  },
  acceptButton: {
    minHeight: 50,
    backgroundColor: Colors.primary,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.4)",
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 4,
  },
  acceptButtonText: {
    fontSize: 14.5,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: 0.4,
  },
  footerNote: {
    fontSize: 10,
    color: Colors.textSubtle,
    textAlign: "center",
    lineHeight: 14,
  },
});
