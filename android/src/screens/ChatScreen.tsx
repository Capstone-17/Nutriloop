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
import { ApiService } from "../services/api";

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

export const ChatScreen: React.FC<ChatScreenProps> = ({ vitals: _vitals }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I am Dr. Nutriloop Clinical AI, your dietary intelligence assistant. My reasoning is grounded in KDIGO 2024, ADA 2024, and AHA DASH clinical guidelines, with real-time access to your metabolic biomarkers. How may I assist your nutritional strategy today?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [serverConnected, setServerConnected] = useState<boolean | null>(null);
  const [backendUrl, setBackendUrl] = useState<string>("");
  const [backendUrlModalVisible, setBackendUrlModalVisible] = useState(false);
  const [backendUrlInput, setBackendUrlInput] = useState("");
  const [isPingingServer, setIsPingingServer] = useState(false);

  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    async function loadConfig() {
      try {
        const currentUrl = await ApiService.getBaseUrl();
        setBackendUrl(currentUrl);
        setBackendUrlInput(currentUrl);
        checkHealth();
      } catch (err) {
        console.warn("Failed to load chat settings:", err);
      }
    }
    loadConfig();
  }, []);

  const checkHealth = async () => {
    setIsPingingServer(true);
    try {
      const isHealthy = await ApiService.checkServerHealth();
      setServerConnected(isHealthy);
    } catch {
      setServerConnected(false);
    } finally {
      setIsPingingServer(false);
    }
  };

  const handleSaveBackendUrl = async () => {
    const cleanUrl = backendUrlInput.trim();
    if (!cleanUrl) return;
    await ApiService.setBaseUrl(cleanUrl);
    setBackendUrl(cleanUrl);
    setBackendUrlModalVisible(false);
    Alert.alert("Backend URL Updated", `Nutriloop clinical server host set to:\n${cleanUrl}`);
    checkHealth();
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isTyping) return;

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

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .slice(-8)
        .map((m) => ({ role: m.role, content: m.content }));

      const reply = await ApiService.sendChatMessage(text, history, "ckd", "patient_mobile");

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);
      setServerConnected(true);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `⚠️ Consultation Error: ${err?.message || "Failed to formulate clinical response."}\n\nPlease check server connection.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setServerConnected(false);
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
      {/* Top Banner: Clinical Engine Status & Server Host Configuration */}
      <View style={styles.topBanner}>
        <View style={styles.topBannerInfo}>
          <View
            style={[
              styles.statusIndicator,
              serverConnected === true
                ? styles.statusConnected
                : serverConnected === false
                ? styles.statusDisconnected
                : styles.statusChecking,
            ]}
          />
          <Text style={styles.topBannerText} numberOfLines={1}>
            {serverConnected === true
              ? "Clinical AI Engine Connected"
              : serverConnected === false
              ? "Server Offline (Fallback Mode)"
              : "Connecting to Clinical Engine..."}
          </Text>
        </View>

        <View style={styles.topBannerActions}>
          <TouchableOpacity
            style={styles.pingBtn}
            activeOpacity={0.7}
            onPress={checkHealth}
            disabled={isPingingServer}
          >
            {isPingingServer ? (
              <ActivityIndicator size="small" color={Colors.secondary} />
            ) : (
              <Ionicons name="refresh" size={13} color={Colors.secondary} />
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.serverHostBtn}
            activeOpacity={0.8}
            onPress={() => setBackendUrlModalVisible(true)}
          >
            <Ionicons name="server-outline" size={13} color={Colors.secondary} />
            <Text style={styles.serverHostBtnText}>Host</Text>
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
            <View
              key={msg.id}
              style={[styles.msgRow, isUser ? styles.msgRowUser : styles.msgRowAssistant]}
            >
              {!isUser && (
                <View style={styles.avatarAssistant}>
                  <Text style={styles.avatarAssistantText}>NL</Text>
                </View>
              )}
              <View
                style={[
                  styles.msgBubble,
                  isUser ? styles.msgBubbleUser : styles.msgBubbleAssistant,
                ]}
              >
                <Text
                  style={[
                    styles.msgText,
                    isUser ? styles.msgTextUser : styles.msgTextAssistant,
                  ]}
                >
                  {msg.content}
                </Text>
                <Text
                  style={[
                    styles.msgTime,
                    isUser ? styles.msgTimeUser : styles.msgTimeAssistant,
                  ]}
                >
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
              <Text style={styles.typingText}>Reasoning over clinical guidelines...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Quick Suggestion Chips */}
      <View style={styles.suggestionsContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.suggestionsContent}
        >
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
                <Text style={styles.modalTitle}>Clinical Backend Server</Text>
              </View>
              <TouchableOpacity onPress={() => setBackendUrlModalVisible(false)}>
                <Ionicons name="close" size={20} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalDescription}>
              Configure the FastAPI server endpoint. All ML assessment, dietary algorithms, and Dr. Nutriloop clinical AI reasoning are hosted centrally.
            </Text>

            <View style={styles.quickHostPills}>
              <TouchableOpacity
                style={styles.hostPill}
                onPress={() => setBackendUrlInput("http://10.0.2.2:8000")}
              >
                <Text style={styles.hostPillText}>Android Emulator (10.0.2.2:8000)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.hostPill}
                onPress={() => setBackendUrlInput("http://localhost:8000")}
              >
                <Text style={styles.hostPillText}>Localhost / iOS (localhost:8000)</Text>
              </TouchableOpacity>
            </View>

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
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setBackendUrlModalVisible(false)}
              >
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
    backgroundColor: "rgba(30, 15, 24, 0.85)",
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
  },
  topBannerInfo: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    marginRight: 10,
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
  statusDisconnected: {
    backgroundColor: "#ef4444",
  },
  statusChecking: {
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
  pingBtn: {
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    alignItems: "center",
    justifyContent: "center",
  },
  serverHostBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.35)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    minHeight: 32,
  },
  serverHostBtnText: {
    fontSize: 11.5,
    fontWeight: "700",
    color: Colors.secondary,
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
    color: "#FFFFFF",
  },
  msgBubble: {
    maxWidth: "80%",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  msgBubbleUser: {
    backgroundColor: Colors.primary,
    borderBottomRightRadius: 4,
  },
  msgBubbleAssistant: {
    backgroundColor: Colors.bgCardSolid,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    borderBottomLeftRadius: 4,
  },
  msgText: {
    fontSize: 13.5,
    lineHeight: 19,
  },
  msgTextUser: {
    color: "#FFFFFF",
  },
  msgTextAssistant: {
    color: Colors.textMain,
  },
  msgTime: {
    fontSize: 9.5,
    marginTop: 4,
    alignSelf: "flex-end",
  },
  msgTimeUser: {
    color: "rgba(255, 255, 255, 0.65)",
  },
  msgTimeAssistant: {
    color: Colors.textSubtle,
  },
  typingBubble: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 12,
  },
  typingText: {
    fontSize: 12,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
  suggestionsContainer: {
    paddingVertical: 8,
    backgroundColor: "rgba(12, 6, 8, 0.95)",
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
  },
  suggestionsContent: {
    paddingHorizontal: 14,
    gap: 8,
  },
  suggestionChip: {
    backgroundColor: "rgba(24, 12, 19, 0.9)",
    borderWidth: 1,
    borderColor: Colors.borderCard,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    minHeight: 36,
    justifyContent: "center",
  },
  suggestionChipText: {
    fontSize: 11.5,
    color: Colors.textMuted,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: Colors.bgSurface,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    gap: 10,
  },
  textInput: {
    flex: 1,
    minHeight: 44,
    maxHeight: 100,
    backgroundColor: Colors.bgInput,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: Colors.textMain,
    fontSize: 13.5,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  modalCard: {
    width: "100%",
    backgroundColor: Colors.bgSurface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.borderCard,
    padding: 20,
    gap: 14,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  modalTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: Colors.textMain,
  },
  modalDescription: {
    fontSize: 12,
    color: Colors.textMuted,
    lineHeight: 17,
  },
  quickHostPills: {
    gap: 6,
  },
  hostPill: {
    backgroundColor: "rgba(245, 158, 11, 0.08)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.25)",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  hostPillText: {
    fontSize: 11,
    color: Colors.secondary,
    fontWeight: "600",
  },
  keyInputField: {
    backgroundColor: Colors.bgInput,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.borderFocus,
    padding: 12,
    color: Colors.textMain,
    fontSize: 13,
  },
  modalFooter: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 4,
  },
  modalCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 44,
    justifyContent: "center",
  },
  modalCancelText: {
    color: Colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
  },
  modalSaveBtn: {
    backgroundColor: Colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    minHeight: 44,
    justifyContent: "center",
  },
  modalSaveText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
});
