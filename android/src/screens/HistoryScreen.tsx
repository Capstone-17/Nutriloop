import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Modal,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";
import {
  PatientTestHistoryRecord,
  PatientVitals,
  DEFAULT_PATIENT_VITALS,
} from "../types/clinical";
import { dbManager } from "../db/database";
import { formatDecimal } from "../utils/formatters";

interface HistoryScreenProps {
  onLoadTest: (vitals: PatientVitals, createdAt?: string, isHistorical?: boolean) => void;
}

export const HistoryScreen: React.FC<HistoryScreenProps> = ({ onLoadTest }) => {
  const [history, setHistory] = useState<PatientTestHistoryRecord[]>([]);
  const [recordToDelete, setRecordToDelete] = useState<PatientTestHistoryRecord | null>(null);

  const fetchHistory = async () => {
    try {
      const records = await dbManager.getPatientTestHistory("patient_local");
      setHistory(records);
    } catch (e) {
      console.warn("Failed to load test history:", e);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const confirmDelete = async () => {
    if (!recordToDelete) return;
    try {
      await dbManager.deletePatientTest(recordToDelete.id);
      setRecordToDelete(null);
      await fetchHistory();
    } catch (e) {
      console.warn("Delete error:", e);
      Alert.alert("Error", "Could not delete test report.");
    }
  };

  return (
    <View style={styles.outerContainer}>
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.heading}>📜 Saved Lab Test History</Text>
            <Text style={styles.subheading}>
              All historical patient reports are stored strictly in local device SQLite without cloud dependencies.
            </Text>
          </View>
        </View>

        {history.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="documents-outline" size={38} color={Colors.textSubtle} />
            <Text style={styles.emptyTitle}>No Saved Lab Reports Yet</Text>
            <Text style={styles.emptyText}>
              Run a Multi-Disease Assessment on the Assessment tab to save test reports into your device.
            </Text>
            <TouchableOpacity
              style={styles.btnEmptyBaseline}
              activeOpacity={0.8}
              onPress={() => onLoadTest({ ...DEFAULT_PATIENT_VITALS }, undefined, false)}
            >
              <Ionicons name="shield-checkmark-outline" size={16} color={Colors.secondary} />
              <Text style={styles.btnEmptyBaselineText}>Apply Safe Reference Baseline</Text>
            </TouchableOpacity>
          </View>
        ) : (
          history.map((rec, index) => {
            const isLatest = index === 0;
            return (
              <View key={rec.id} style={[styles.recordCard, isLatest && styles.recordCardLatest]}>
                <View style={styles.recordHeader}>
                  <View style={styles.recordMetaCol}>
                    <View style={styles.dateBadgeRow}>
                      <Text style={styles.recordDate}>
                        📅 {rec.createdAt?.substring(0, 16).replace("T", " ")}
                      </Text>
                      {isLatest && (
                        <View style={styles.latestPill}>
                          <Text style={styles.latestPillText}>LATEST REPORT</Text>
                        </View>
                      )}
                    </View>
                    <Text style={styles.recordVitalsSummary}>
                      BP {rec.vitals.systolicBpMmhg}/{rec.vitals.diastolicBpMmhg} mmHg • Gluc {formatDecimal(rec.vitals.fastingGlucoseMgDl, 2)} • Cr {formatDecimal(rec.vitals.serumCreatinineMgDl, 2)} • eGFR {formatDecimal(rec.vitals.egfrMlMin, 2)} • K+ {formatDecimal(rec.vitals.serumPotassiumMeqL, 2)}
                    </Text>
                  </View>

                  {/* Styled Delete Notice Button on Card */}
                  <TouchableOpacity
                    style={styles.deleteNoticeBtn}
                    activeOpacity={0.75}
                    onPress={() => setRecordToDelete(rec)}
                  >
                    <Ionicons name="trash-outline" size={13} color={Colors.dangerRose} />
                    <Text style={styles.deleteNoticeBtnText}>Delete</Text>
                  </TouchableOpacity>
                </View>

                {/* Conditions pills */}
                <View style={styles.conditionsRow}>
                  {rec.detectedConditions.map((c, idx) => (
                    <View key={idx} style={styles.conditionChip}>
                      <Text style={styles.conditionChipText}>{c}</Text>
                    </View>
                  ))}
                </View>

                {/* Load Button */}
                <TouchableOpacity
                  style={styles.loadBtn}
                  activeOpacity={0.8}
                  onPress={() => {
                    onLoadTest(rec.vitals, rec.createdAt, !isLatest);
                    Alert.alert(
                      "Loaded into Monitors & Diet",
                      isLatest
                        ? "Latest test biomarkers loaded into monitors and diet calibration!"
                        : `Historical test report from ${rec.createdAt?.substring(0, 10)} loaded into assessment and diet calibration.`
                    );
                  }}
                >
                  <Ionicons name="arrow-undo-outline" size={14} color={Colors.secondary} />
                  <Text style={styles.loadBtnText}>Load into Assessment &amp; Diet Plan</Text>
                </TouchableOpacity>
              </View>
            );
          })
        )}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* ──────────────────────────────────────────────────────────────────
          Custom Styled Delete Confirmation Modal Card
          ────────────────────────────────────────────────────────────────── */}
      <Modal
        visible={recordToDelete !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setRecordToDelete(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            {/* Modal Header */}
            <View style={styles.modalHeader}>
              <View style={styles.modalTitleRow}>
                <View style={styles.warningIconBadge}>
                  <Ionicons name="warning-outline" size={18} color={Colors.dangerRose} />
                </View>
                <Text style={styles.modalTitle}>Delete Test Report</Text>
              </View>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => setRecordToDelete(null)}
              >
                <Ionicons name="close" size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            {/* Modal Body */}
            <View style={styles.modalBody}>
              <Text style={styles.modalWarningText}>
                Are you sure you want to permanently delete test report #{recordToDelete?.id}? This action cannot be undone.
              </Text>

              {recordToDelete && (
                <View style={styles.modalSummaryBox}>
                  <Text style={styles.modalSummaryDate}>
                    📅 {recordToDelete.createdAt?.substring(0, 16).replace("T", " ")}
                  </Text>
                  <Text style={styles.modalSummaryVitals}>
                    BP {recordToDelete.vitals.systolicBpMmhg}/{recordToDelete.vitals.diastolicBpMmhg} mmHg • Gluc {formatDecimal(recordToDelete.vitals.fastingGlucoseMgDl, 2)} mg/dL • Cr {formatDecimal(recordToDelete.vitals.serumCreatinineMgDl, 2)} mg/dL • eGFR {formatDecimal(recordToDelete.vitals.egfrMlMin, 2)} mL/min
                  </Text>
                </View>
              )}
            </View>

            {/* Modal Action Buttons */}
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                activeOpacity={0.8}
                onPress={() => setRecordToDelete(null)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.modalDeleteBtn}
                activeOpacity={0.85}
                onPress={confirmDelete}
              >
                <Ionicons name="trash" size={15} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.modalDeleteText}>Yes, Delete Report</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  outerContainer: {
    flex: 1,
    backgroundColor: Colors.bgMain,
  },
  container: {
    flex: 1,
    backgroundColor: Colors.bgMain,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  headerRow: {
    marginBottom: 16,
  },
  heading: {
    color: Colors.textMain,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
  },
  subheading: {
    color: Colors.textMuted,
    fontSize: 12.5,
    lineHeight: 17,
  },
  emptyCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 14,
    padding: 28,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: Colors.borderCard,
    marginTop: 20,
  },
  emptyTitle: {
    color: Colors.textMain,
    fontSize: 15,
    fontWeight: "600",
    marginTop: 10,
  },
  emptyText: {
    color: Colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    marginTop: 6,
    lineHeight: 16,
    marginBottom: 12,
  },
  btnEmptyBaseline: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "rgba(245, 158, 11, 0.14)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.4)",
    paddingVertical: 9,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginTop: 4,
  },
  btnEmptyBaselineText: {
    color: Colors.secondary,
    fontSize: 13,
    fontWeight: "700",
  },
  recordCard: {
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.borderCard,
  },
  recordCardLatest: {
    borderColor: "rgba(245, 158, 11, 0.45)",
    backgroundColor: "rgba(42, 14, 27, 0.95)",
  },
  recordHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  recordMetaCol: {
    flex: 1,
    marginRight: 10,
  },
  dateBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
  },
  recordDate: {
    color: Colors.secondaryLight,
    fontSize: 13,
    fontWeight: "700",
  },
  latestPill: {
    backgroundColor: "rgba(245, 158, 11, 0.2)",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 0.5,
    borderColor: Colors.secondary,
  },
  latestPillText: {
    color: Colors.secondary,
    fontSize: 9.5,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  recordVitalsSummary: {
    color: Colors.textMain,
    fontSize: 12,
    marginTop: 4,
    fontWeight: "500",
    lineHeight: 16,
  },
  deleteNoticeBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(244, 63, 94, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(244, 63, 94, 0.35)",
    borderRadius: 7,
    paddingHorizontal: 9,
    paddingVertical: 5,
    gap: 4,
  },
  deleteNoticeBtnText: {
    color: Colors.dangerRose,
    fontSize: 11,
    fontWeight: "600",
  },
  conditionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginVertical: 6,
  },
  conditionChip: {
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    marginRight: 6,
    marginBottom: 4,
  },
  conditionChipText: {
    color: Colors.secondaryLight,
    fontSize: 10.5,
    fontWeight: "600",
  },
  loadBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(155, 27, 48, 0.25)",
    paddingVertical: 10,
    minHeight: 44,
    borderRadius: 8,
    marginTop: 6,
    borderWidth: 0.8,
    borderColor: Colors.secondary,
  },
  loadBtnText: {
    color: Colors.secondaryLight,
    fontSize: 12,
    fontWeight: "600",
    marginLeft: 6,
  },

  /* Confirmation Modal Styles */
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modalCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: "#200914",
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: "rgba(244, 63, 94, 0.4)",
    padding: 18,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 16,
    elevation: 12,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.08)",
  },
  modalTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  warningIconBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(244, 63, 94, 0.15)",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(244, 63, 94, 0.3)",
  },
  modalTitle: {
    color: Colors.textMain,
    fontSize: 15,
    fontWeight: "700",
  },
  modalCloseBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  modalBody: {
    paddingVertical: 14,
  },
  modalWarningText: {
    color: Colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
  },
  modalSummaryBox: {
    backgroundColor: "rgba(0, 0, 0, 0.35)",
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.06)",
  },
  modalSummaryDate: {
    color: Colors.secondary,
    fontSize: 12.5,
    fontWeight: "700",
    marginBottom: 4,
  },
  modalSummaryVitals: {
    color: Colors.textMain,
    fontSize: 11.5,
    lineHeight: 16,
  },
  modalFooter: {
    flexDirection: "row",
    justifyContent: "flex-end",
    alignItems: "center",
    gap: 10,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.08)",
  },
  modalCancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.12)",
    minHeight: 44,
    justifyContent: "center",
  },
  modalCancelText: {
    color: Colors.textMain,
    fontSize: 12.5,
    fontWeight: "600",
  },
  modalDeleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 8,
    backgroundColor: "#e11d48",
    minHeight: 44,
    shadowColor: "#e11d48",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 4,
  },
  modalDeleteText: {
    color: "#FFFFFF",
    fontSize: 12.5,
    fontWeight: "700",
  },
});
