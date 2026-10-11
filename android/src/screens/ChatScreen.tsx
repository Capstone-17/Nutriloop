import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors } from "../theme/colors";
import { PatientVitals } from "../types/clinical";
import { dbManager } from "../db/database";
import { ApiService } from "../services/api";
import { formatDecimal } from "../utils/formatters";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface ChatScreenProps {
  vitals: PatientVitals;
}

const QUICK_SUGGESTIONS = [
  "Why is my potassium intake restricted?",
  "Recommend low-glycemic breakfast ideas",
  "How does high blood pressure affect kidney function?",
  "What spices enhance flavor without sodium?",
];

export const ChatScreen: React.FC<ChatScreenProps> = ({ vitals }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I am NutriLoop AI, your clinical dietary assistant. I am calibrated to your laboratory biomarkers and chronic condition risks. How can I assist your nutrition plan today?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [apiKey, setApiKey] = useState<string>("");
  const [keyModalVisible, setKeyModalVisible] = useState(false);
  const [tempKeyInput, setTempKeyInput] = useState("");
  const [backendUrlModalVisible, setBackendUrlModalVisible] = useState(false);
  const [backendUrlInput, setBackendUrlInput] = useState("");

  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    async function loadSettings() {
      try {
        const savedKey = await dbManager.getSetting("user_api_key");
        if (savedKey) {
          setApiKey(savedKey);
        }
        const currentUrl = await ApiService.getBaseUrl();
        setBackendUrlInput(currentUrl);
      } catch (err) {
        console.warn("Failed to load chat settings:", err);
      }
    }
    loadSettings();
  }, []);

  const handleSaveApiKey = async () => {
    const cleanKey = tempKeyInput.trim();
    if (!cleanKey) {
      Alert.alert("Input Required", "Please enter a valid Gemini or OpenAI API key.");
      return;
    }
    setApiKey(cleanKey);
    await dbManager.saveSetting("user_api_key", cleanKey);
    setKeyModalVisible(false);
    Alert.alert("API Key Saved", "Your LLM API Key is securely configured for conversational clinical consultations.");
  };

  const handleSaveBackendUrl = async () => {
    const cleanUrl = backendUrlInput.trim();
    if (!cleanUrl) return;
    await ApiService.setBaseUrl(cleanUrl);
    setBackendUrlModalVisible(false);
    Alert.alert("Backend URL Updated", `Nutriloop common backend host set to: ${cleanUrl}`);
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isTyping) return;

    if (!apiKey) {
      setTempKeyInput("");
      setKeyModalVisible(true);
      return;
    }

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsTyping(true);

    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);

    const vitalsSummary = `BP: ${vitals.systolicBpMmhg}/${vitals.diastolicBpMmhg} mmHg, FBS: ${formatDecimal(vitals.fastingGlucoseMgDl, 2)} mg/dL, HbA1c: ${formatDecimal(vitals.hba1cPct, 2)}%, Creatinine: ${formatDecimal(vitals.serumCreatinineMgDl, 2)} mg/dL, eGFR: ${formatDecimal(vitals.egfrMlMin, 2)} mL/min, Potassium: ${formatDecimal(vitals.serumPotassiumMeqL, 2)} mEq/L, Sodium: ${formatDecimal(vitals.serumSodiumMeqL, 2)} mEq/L, BMI: ${formatDecimal(vitals.bodyMassIndex, 2)}`;

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const reply = await ApiService.chatWithUserApiKey(text, history, apiKey, vitalsSummary);

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `⚠️ Consultation Error: ${err?.message || "Failed to formulate response."}\n\nPlease verify your API key in settings.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      {/* Top Banner: Status & API Key configuration */}
      <View style={styles.topBanner}>
        <View style={styles.topBannerInfo}>
          <View style={[styles.statusIndicator, apiKey ? styles.statusConnected : styles.statusKeyMissing]} />
          <Text style={styles.topBannerText}>
            {apiKey ? "API Key Configured (Direct LLM)" : "API Key Required"}
          </Text>
        </View>
        <View style={styles.topBannerActions}>
          <TouchableOpacity
            style={styles.keyBadgeBtn}
            activeOpacity={0.8}
            onPress={() => {
              setTempKeyInput(apiKey);
              setKeyModalVisible(true);
            }}
          >
            <Ionicons name="key-outline" size={13} color={Colors.secondary} />
            <Text style={styles.keyBadgeBtnText}>{apiKey ? "Change Key" : "Paste API Key"}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.settingsBadgeBtn}
            activeOpacity={0.8}
            onPress={() => setBackendUrlModalVisible(true)}
          >
            <Ionicons name="server-outline" size={13} color={Colors.textMuted} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Messages Scroll View */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messagesList}
        contentContainerStyle={styles.messagesContent}
        onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <View key={msg.id} style={[styles.msgRow, isUser ? styles.msgRowUser : styles.msgRowAssistant]}>
              {!isUser && (
                <View style={styles.avatarAssistant}>
                  <Text style={styles.avatarAssistantText}>NL</Text>
                </View>
              )}
              <View style={[styles.msgBubble, isUser ? styles.msgBubbleUser : styles.msgBubbleAssistant]}>
                <Text style={[styles.msgText, isUser ? styles.msgTextUser : styles.msgTextAssistant]}>
                  {msg.content}
                </Text>
                <Text style={[styles.msgTime, isUser ? styles.msgTimeUser : styles.msgTimeAssistant]}>
                  {msg.timestamp}
                </Text>
              </View>
            </View>
          );
        })}

        {isTyping && (
          <View style={[styles.msgRow, styles.msgRowAssistant]}>
            <View style={styles.avatarAssistant}>
              <Text style={styles.avatarAssistantText}>NL</Text>
            </View>
            <View style={[styles.msgBubble, styles.msgBubbleAssistant, styles.typingBubble]}>
              <ActivityIndicator size="small" color={Colors.secondary} />
              <Text style={styles.typingText}>Consulting clinical evidence guidelines...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Quick Suggestion Chips */}
      <View style={styles.suggestionsContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestionsContent}>
          {QUICK_SUGGESTIONS.map((sug, idx) => (
            <TouchableOpacity
              key={idx}
              style={styles.suggestionChip}
              activeOpacity={0.75}
              onPress={() => handleSend(sug)}
            >
              <Text style={styles.suggestionChipText}>{sug}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Input Bar */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          placeholder="Ask clinical dietary question..."
          placeholderTextColor={Colors.textMuted}
          value={inputText}
          onChangeText={setInputText}
          multiline
          maxLength={600}
        />
        <TouchableOpacity
          style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]}
          activeOpacity={0.8}
          disabled={!inputText.trim() || isTyping}
          onPress={() => handleSend()}
        >
          <Ionicons name="arrow-up" size={18} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      {/* API Key Modal */}
      <Modal visible={keyModalVisible} transparent animationType="fade" onRequestClose={() => setKeyModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <View style={styles.modalTitleRow}>
                <Ionicons name="key" size={20} color={Colors.secondary} />
                <Text style={styles.modalTitle}>Paste Your API Key</Text>
              </View>
              <TouchableOpacity onPress={() => setKeyModalVisible(false)}>
                <Ionicons name="close" size={20} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalDescription}>
              Enter your Google Gemini or OpenAI API key. This key will be stored securely on your device and enables direct, private clinical AI reasoning without any Ollama dependency.
            </Text>

            <TextInput
              style={styles.keyInputField}
              placeholder="Paste AIzaSy... or sk-... key"
              placeholderTextColor={Colors.textMuted}
              value={tempKeyInput}
              onChangeText={setTempKeyInput}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setKeyModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSaveBtn} onPress={handleSaveApiKey}>
                <Text style={styles.modalSaveText}>Save API Key</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Backend Host Configuration Modal */}
      <Modal
        visible={backendUrlModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setBackendUrlModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <View style={styles.modalTitleRow}>
                <Ionicons name="server" size={20} color={Colors.secondary} />
                <Text style={styles.modalTitle}>Common Backend Host</Text>
              </View>
              <TouchableOpacity onPress={() => setBackendUrlModalVisible(false)}>
                <Ionicons name="close" size={20} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalDescription}>
              Configure the host URL for the Nutriloop Python backend (Default: http://10.0.2.2:8000 for Android emulator, or http://192.168.x.x:8000 for physical devices on local Wi-Fi).
            </Text>

            <TextInput
              style={styles.keyInputField}
              placeholder="http://10.0.2.2:8000"
              placeholderTextColor={Colors.textMuted}
              value={backendUrlInput}
              onChangeText={setBackendUrlInput}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setBackendUrlModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSaveBtn} onPress={handleSaveBackendUrl}>
                <Text style={styles.modalSaveText}>Save Host</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgMain,
  },
  topBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: "rgba(30, 15, 24, 0.8)",
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
  },
  topBannerInfo: {
    flexDirection: "row",
    alignItems: "center",
  },
  statusIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusConnected: {
    backgroundColor: "#10b981",
  },
  statusKeyMissing: {
    backgroundColor: "#f59e0b",
  },
  topBannerText: {
    fontSize: 12,
    fontWeight: "600",
    color: Colors.textMuted,
  },
  topBannerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  keyBadgeBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(217, 119, 6, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(217, 119, 6, 0.4)",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  keyBadgeBtnText: {
    fontSize: 11.5,
    fontWeight: "700",
    color: Colors.secondary,
  },
  settingsBadgeBtn: {
    padding: 5,
    borderRadius: 6,
    backgroundColor: "rgba(255, 255, 255, 0.05)",
  },
  messagesList: {
    flex: 1,
  },
  messagesContent: {
    padding: 16,
    paddingBottom: 20,
    gap: 14,
  },
  msgRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },
  msgRowUser: {
    justifyContent: "flex-end",
  },
  msgRowAssistant: {
    justifyContent: "flex-start",
  },
  avatarAssistant: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    borderWidth: 1,
    borderColor: Colors.secondary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },
  avatarAssistantText: {
    fontSize: 11,
    fontWeight: "800",
    color: Colors.secondary,
  },
  msgBubble: {
    maxWidth: "82%",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
  },
  msgBubbleUser: {
    backgroundColor: Colors.primary,
    borderTopRightRadius: 2,
    borderWidth: 1,
    borderColor: "rgba(217, 119, 6, 0.4)",
  },
  msgBubbleAssistant: {
    backgroundColor: "rgba(30, 15, 24, 0.9)",
    borderTopLeftRadius: 2,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  msgText: {
    fontSize: 13.5,
    lineHeight: 20,
  },
  msgTextUser: {
    color: "#FFFFFF",
  },
  msgTextAssistant: {
    color: "#F3F4F6",
  },
  msgTime: {
    fontSize: 10,
    marginTop: 4,
    alignSelf: "flex-end",
  },
  msgTimeUser: {
    color: "rgba(255, 255, 255, 0.6)",
  },
  msgTimeAssistant: {
    color: Colors.textMuted,
  },
  typingBubble: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 12,
  },
  typingText: {
    fontSize: 12,
    fontStyle: "italic",
    color: Colors.textMuted,
  },
  suggestionsContainer: {
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    backgroundColor: "rgba(20, 10, 16, 0.6)",
  },
  suggestionsContent: {
    paddingHorizontal: 14,
    gap: 8,
  },
  suggestionChip: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  suggestionChipText: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "rgba(25, 12, 20, 0.95)",
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    gap: 10,
  },
  textInput: {
    flex: 1,
    minHeight: 40,
    maxHeight: 100,
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 14,
    color: "#FFFFFF",
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: Colors.secondary,
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    width: "100%",
    maxWidth: 440,
    backgroundColor: "#1c0d16",
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "rgba(217, 119, 6, 0.3)",
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  modalTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  modalDescription: {
    fontSize: 12.5,
    lineHeight: 18,
    color: Colors.textMuted,
    marginBottom: 16,
  },
  keyInputField: {
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: "#FFFFFF",
    marginBottom: 20,
  },
  modalFooter: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  modalCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  modalCancelText: {
    fontSize: 13,
    color: Colors.textMuted,
  },
  modalSaveBtn: {
    backgroundColor: Colors.primary,
    borderWidth: 1,
    borderColor: Colors.secondary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  modalSaveText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});
