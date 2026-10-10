import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Image,
  TouchableOpacity,
  Modal,
  TextInput,
  TouchableWithoutFeedback,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";

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
  activeTestDate,
}) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editingName, setEditingName] = useState(patientName);

  const handleOpenModal = () => {
    setEditingName(patientName);
    setModalVisible(true);
  };

  const handleRollRandom = () => {
    const rolled = getRandomAlliterativeName();
    setEditingName(rolled);
  };

  const handleSave = () => {
    if (editingName.trim() && onPatientNameChange) {
      onPatientNameChange(editingName.trim());
    }
    setModalVisible(false);
  };

  return (
    <View style={styles.headerContainer}>
      <View style={styles.brandRow}>
        <Image
          source={require("../../assets/Nutriloop_1.png")}
          style={styles.brandLogo}
          resizeMode="contain"
        />
        <View style={styles.brandTextContainer}>
          <Text style={styles.brandTitle}>NutriLoop</Text>
          <Text style={styles.brandSubtitle}>Clinical Decision Support</Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.patientChip}
        activeOpacity={0.75}
        onPress={handleOpenModal}
      >
        <View style={styles.patientAvatar}>
          <Ionicons name="person" size={13} color={Colors.secondary} />
        </View>
        <View style={styles.patientMeta}>
          <Text style={styles.patientName} numberOfLines={1}>
            {patientName || "Clever Cheetah"}
          </Text>
          <Text style={styles.patientRole}>Active Patient Record ✏️</Text>
        </View>
      </TouchableOpacity>

      {/* Edit Patient Profile Modal */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setModalVisible(false)}
      >
        <TouchableWithoutFeedback onPress={() => setModalVisible(false)}>
          <View style={styles.modalOverlay}>
            <TouchableWithoutFeedback>
              <View style={styles.modalCard}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Patient Profile Name</Text>
                  <TouchableOpacity onPress={() => setModalVisible(false)}>
                    <Ionicons name="close" size={20} color={Colors.textMuted} />
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
                    onPress={handleSave}
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
  patientChip: {
    backgroundColor: "rgba(24, 12, 19, 0.95)",
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 20,
    paddingVertical: 5,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    maxWidth: 160,
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
  modalTitle: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
  },
  modalDesc: {
    color: Colors.textMuted,
    fontSize: 12.5,
    lineHeight: 18,
    marginBottom: 14,
  },
  modalInput: {
    backgroundColor: Colors.bgInput,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderRadius: 10,
    color: "#FFF",
    fontSize: 15,
    fontWeight: "600",
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 16,
  },
  modalButtonsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  btnRoll: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.secondary,
    backgroundColor: "rgba(245, 158, 11, 0.1)",
  },
  btnRollText: {
    color: Colors.secondary,
    fontSize: 12.5,
    fontWeight: "600",
  },
  btnSave: {
    backgroundColor: Colors.primary,
    paddingVertical: 9,
    paddingHorizontal: 18,
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  btnSaveText: {
    color: "#FFF",
    fontSize: 12.5,
    fontWeight: "700",
  },
});
