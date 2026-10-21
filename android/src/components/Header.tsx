import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Image,
  TouchableOpacity,
  Modal,
  TextInput,
  TouchableWithoutFeedback,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";
import { ApiService } from "../services/api";

export const ALLITERATIVE_ANIMAL_NAMES = [
  "Sorcerer Swan", "Beauty Bee", "Clever Cheetah", "Daring Dolphin",
  "Fearless Falcon", "Gentle Giraffe", "Heroic Hawk", "Jolly Jaguar",
  "Kind Koala", "Luminous Lynx", "Mighty Monkey", "Noble Narwhal",
  "Peppy Penguin", "Quick Quail", "Radiant Raven", "Stellar Starling",
  "Valiant Viper", "Wise Walrus", "Mystic Moose", "Astral Alpaca",
  "Brave Bear", "Cosmic Crane", "Dynamic Deer", "Epic Eagle",
  "Gallant Gecko", "Harmonious Hummingbird", "Infinite Iguana", "Jovial Jackal",
  "Keen Kingfisher", "Loyal Leopard", "Majestic Mustang", "Nimble Newt",
  "Optimistic Otter", "Peaceful Panda", "Quantum Quokka", "Royal Rhino",
  "Serene Seal", "Thunder Tiger", "Unique Unicorn", "Victorious Vulture",
  "Witty Wolf", "Xenon X-Ray Tetra", "Youthful Yak", "Zen Zebra"
];

export function getRandomAlliterativeName(): string {
  const idx = Math.floor(Math.random() * ALLITERATIVE_ANIMAL_NAMES.length);
  return ALLITERATIVE_ANIMAL_NAMES[idx];
}

interface HeaderProps {
  patientName: string;
  onPatientNameChange?: (name: string) => void;
  activeTestDate?: string;
}

export const Header: React.FC<HeaderProps> = ({
  patientName,
  onPatientNameChange,
  activeTestDate: _activeTestDate,
}) => {
  const [nameModalVisible, setNameModalVisible] = useState(false);
  const [editingName, setEditingName] = useState(patientName);

  // Server Host & Status state
  const [serverConnected, setServerConnected] = useState<boolean | null>(null);
  const [hostModalVisible, setHostModalVisible] = useState(false);
  const [currentHostUrl, setCurrentHostUrl] = useState("");
  const [hostInput, setHostInput] = useState("");
  const [isTestingHost, setIsTestingHost] = useState(false);

  const checkConnection = async () => {
    try {
      const isHealthy = await ApiService.checkServerHealth();
      setServerConnected(isHealthy);
    } catch {
      setServerConnected(false);
    }
  };

  useEffect(() => {
    async function initHost() {
      try {
        const url = await ApiService.getBaseUrl();
        setCurrentHostUrl(url);
        setHostInput(url);
        checkConnection();
      } catch {
        // Fallback
      }
    }
    initHost();

    // Check health every 30 seconds
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenNameModal = () => {
    setEditingName(patientName);
    setNameModalVisible(true);
  };

  const handleOpenHostModal = async () => {
    const url = await ApiService.getBaseUrl();
    setCurrentHostUrl(url);
    setHostInput(url);
    setHostModalVisible(true);
    checkConnection();
  };

  const handleTestConnection = async () => {
    setIsTestingHost(true);
    const candidateUrl = hostInput.trim().replace(/\/+$/, "");
    try {
      const response = await fetch(`${candidateUrl}/health`, { method: "GET" });
      if (response.ok) {
        Alert.alert("Connection Success", `✅ Successfully connected to Nutriloop server at:\n${candidateUrl}`);
        setServerConnected(true);
      } else {
        Alert.alert("Connection Warning", `⚠️ Server returned HTTP ${response.status} at ${candidateUrl}`);
        setServerConnected(false);
      }
    } catch (err: any) {
      Alert.alert(
        "Connection Failed",
        `❌ Cannot reach server at:\n${candidateUrl}\n\nError: ${err?.message || "Network request failed"}\n\nTips:\n• Verify computer and phone are on the same Wi-Fi.\n• Run backend with: uvicorn backend.app:app --host 0.0.0.0 --port 8000\n• Ensure Windows Firewall allows port 8000.`
      );
      setServerConnected(false);
    } finally {
      setIsTestingHost(false);
    }
  };

  const handleSaveHost = async () => {
    const cleanUrl = hostInput.trim().replace(/\/+$/, "");
    if (!cleanUrl) {
      Alert.alert("Input Required", "Please enter a valid backend host URL (e.g. http://192.168.1.50:8000)");
      return;
    }
    await ApiService.setBaseUrl(cleanUrl);
    setCurrentHostUrl(cleanUrl);
    setHostModalVisible(false);
    checkConnection();
    Alert.alert("Backend Host Updated", `Nutriloop clinical server configured to:\n${cleanUrl}`);
  };

  const handleRollRandom = () => {
    const rolled = getRandomAlliterativeName();
    setEditingName(rolled);
  };

  const handleSaveName = () => {
    if (editingName.trim() && onPatientNameChange) {
      onPatientNameChange(editingName.trim());
    }
    setNameModalVisible(false);
  };

  return (
    <View style={styles.headerContainer}>
      <View style={styles.brandRow}>
        <Image
          source={require("../../../assets/Nutriloop_1.png")}
          style={styles.brandLogo}
          resizeMode="contain"
        />
        <View style={styles.brandTextContainer}>
          <Text style={styles.brandTitle}>NutriLoop</Text>
          <Text style={styles.brandSubtitle}>Clinical Decision Support</Text>
        </View>
      </View>

      <View style={styles.headerActions}>
        {/* Server Connection Badge & Host Switcher */}
        <TouchableOpacity
          style={[
            styles.serverBadge,
            serverConnected === true
              ? styles.serverBadgeConnected
              : serverConnected === false
              ? styles.serverBadgeDisconnected
              : styles.serverBadgeChecking,
          ]}
          activeOpacity={0.75}
          onPress={handleOpenHostModal}
        >
          <Ionicons
            name="server"
            size={13}
            color={
              serverConnected === true
                ? "#10B981"
                : serverConnected === false
                ? "#EF4444"
                : Colors.secondary
            }
          />
          <View
            style={[
              styles.serverDot,
              {
                backgroundColor:
                  serverConnected === true
                    ? "#10B981"
                    : serverConnected === false
                    ? "#EF4444"
                    : Colors.secondary,
              },
            ]}
          />
        </TouchableOpacity>

        {/* Patient Profile Pill */}
        <TouchableOpacity
          style={styles.patientChip}
          activeOpacity={0.75}
          onPress={handleOpenNameModal}
        >
          <View style={styles.patientAvatar}>
            <Ionicons name="person" size={13} color={Colors.secondary} />
          </View>
          <View style={styles.patientMeta}>
            <Text style={styles.patientName} numberOfLines={1}>
              {patientName || "Clever Cheetah"}
            </Text>
            <Text style={styles.patientRole}>Active Record ✏️</Text>
          </View>
        </TouchableOpacity>
      </View>

      {/* Edit Patient Profile Modal */}
      <Modal
        visible={nameModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setNameModalVisible(false)}
      >
        <TouchableWithoutFeedback onPress={() => setNameModalVisible(false)}>
          <View style={styles.modalOverlay}>
            <TouchableWithoutFeedback>
              <View style={styles.modalCard}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Patient Profile Name</Text>
                  <TouchableOpacity
                    style={styles.modalCloseBtn}
                    onPress={() => setNameModalVisible(false)}
                  >
                    <Ionicons name="close" size={22} color={Colors.textMuted} />
                  </TouchableOpacity>
                </View>

                <Text style={styles.modalDesc}>
                  In Nutriloop, patients are assigned memorable alliterative animal titles (or enter a custom name):
                </Text>

                <TextInput
                  style={styles.modalInput}
                  value={editingName}
                  onChangeText={setEditingName}
                  placeholder="e.g. Clever Cheetah"
                  placeholderTextColor={Colors.textSubtle}
                  autoFocus
                />

                <View style={styles.modalButtonsRow}>
                  <TouchableOpacity
                    style={styles.btnRoll}
                    onPress={handleRollRandom}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="dice-outline" size={16} color={Colors.secondary} />
                    <Text style={styles.btnRollText}>Roll Animal Title</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.btnSave}
                    onPress={handleSaveName}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.btnSaveText}>Save</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>

      {/* Backend Server Host Configuration Modal */}
      <Modal
        visible={hostModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setHostModalVisible(false)}
      >
        <TouchableWithoutFeedback onPress={() => setHostModalVisible(false)}>
          <View style={styles.modalOverlay}>
            <TouchableWithoutFeedback>
              <View style={styles.modalCard}>
                <View style={styles.modalHeader}>
                  <View style={styles.modalTitleRow}>
                    <Ionicons name="server" size={20} color={Colors.secondary} />
                    <Text style={styles.modalTitle}>Nutriloop Backend Server</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.modalCloseBtn}
                    onPress={() => setHostModalVisible(false)}
                  >
                    <Ionicons name="close" size={22} color={Colors.textMuted} />
                  </TouchableOpacity>
                </View>

                <Text style={styles.modalDesc}>
                  The mobile APK connects to the FastAPI clinical server. Ensure your backend is running with:{"\n"}
                  <Text style={{ color: "#FBBF24", fontWeight: "700" }}>
                    uvicorn backend.app:app --host 0.0.0.0 --port 8000
                  </Text>
                </Text>

                {/* Quick Presets */}
                <View style={styles.quickPresetsWrap}>
                  <Text style={styles.presetLabel}>Quick Presets:</Text>
                  <TouchableOpacity
                    style={styles.presetPill}
                    onPress={() => setHostInput("http://10.0.2.2:8000")}
                  >
                    <Text style={styles.presetPillText}>Android Emulator (10.0.2.2:8000)</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.presetPill}
                    onPress={() => setHostInput("http://localhost:8000")}
                  >
                    <Text style={styles.presetPillText}>Localhost / iOS (localhost:8000)</Text>
                  </TouchableOpacity>
                </View>

                <Text style={styles.inputFieldLabel}>Server URL:</Text>
                <TextInput
                  style={styles.modalInput}
                  value={hostInput}
                  onChangeText={setHostInput}
                  placeholder="http://192.168.1.x:8000"
                  placeholderTextColor={Colors.textSubtle}
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <View style={styles.modalButtonsRow}>
                  <TouchableOpacity
                    style={styles.btnTest}
                    onPress={handleTestConnection}
                    disabled={isTestingHost}
                    activeOpacity={0.8}
                  >
                    {isTestingHost ? (
                      <ActivityIndicator size="small" color={Colors.secondary} />
                    ) : (
                      <>
                        <Ionicons name="pulse" size={15} color={Colors.secondary} />
                        <Text style={styles.btnTestText}>Test Ping</Text>
                      </>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.btnSave}
                    onPress={handleSaveHost}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.btnSaveText}>Save Host</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  headerContainer: {
    backgroundColor: Colors.bgSurface,
    paddingTop: 45,
    paddingBottom: 14,
    paddingHorizontal: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  brandLogo: {
    width: 38,
    height: 38,
    borderRadius: 8,
  },
  brandTextContainer: {
    justifyContent: "center",
  },
  brandTitle: {
    color: Colors.textMain,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  brandSubtitle: {
    color: Colors.secondaryGold,
    fontSize: 10,
    fontWeight: "600",
    letterSpacing: 0.3,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  serverBadge: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1,
    backgroundColor: "rgba(24, 12, 19, 0.95)",
    position: "relative",
  },
  serverBadgeConnected: {
    borderColor: "rgba(16, 185, 129, 0.4)",
  },
  serverBadgeDisconnected: {
    borderColor: "rgba(239, 68, 68, 0.4)",
  },
  serverBadgeChecking: {
    borderColor: "rgba(245, 158, 11, 0.4)",
  },
  serverDot: {
    position: "absolute",
    top: 6,
    right: 6,
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  patientChip: {
    backgroundColor: "rgba(24, 12, 19, 0.95)",
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 22,
    paddingVertical: 6,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    maxWidth: 155,
    minHeight: 44,
  },
  patientAvatar: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
  },
  patientMeta: {
    flex: 1,
  },
  patientName: {
    color: "#FFF",
    fontSize: 11.5,
    fontWeight: "700",
  },
  patientRole: {
    color: Colors.secondaryLight,
    fontSize: 8.5,
    fontWeight: "500",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  modalCard: {
    width: "100%",
    backgroundColor: Colors.bgCardSolid,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 20,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  modalTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  modalTitle: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
  },
  modalCloseBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  modalDesc: {
    color: Colors.textMuted,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 12,
  },
  quickPresetsWrap: {
    gap: 6,
    marginBottom: 12,
  },
  presetLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: Colors.textSubtle,
  },
  presetPill: {
    backgroundColor: "rgba(245, 158, 11, 0.08)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.25)",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  presetPillText: {
    fontSize: 11,
    color: Colors.secondary,
    fontWeight: "600",
  },
  inputFieldLabel: {
    fontSize: 11.5,
    fontWeight: "700",
    color: Colors.textMain,
    marginBottom: 6,
  },
  modalInput: {
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 10,
    color: "#FFF",
    fontSize: 13.5,
    fontWeight: "600",
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 44,
    marginBottom: 16,
  },
  modalButtonsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  btnTest: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.secondary,
    backgroundColor: "rgba(245, 158, 11, 0.1)",
    minHeight: 44,
    justifyContent: "center",
  },
  btnTestText: {
    color: Colors.secondary,
    fontSize: 12.5,
    fontWeight: "600",
  },
  btnRoll: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.secondary,
    backgroundColor: "rgba(245, 158, 11, 0.1)",
    minHeight: 44,
    justifyContent: "center",
  },
  btnRollText: {
    color: Colors.secondary,
    fontSize: 12.5,
    fontWeight: "600",
  },
  btnSave: {
    backgroundColor: Colors.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
    minHeight: 44,
  },
  btnSaveText: {
    color: "#FFF",
    fontSize: 12.5,
    fontWeight: "700",
  },
});
