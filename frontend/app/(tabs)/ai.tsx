import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { streamChat, apiFetch } from "@/src/api/client";
import { theme } from "@/src/theme";

interface Msg {
  role: "user" | "assistant";
  content: string;
  ts: number;
}

interface Assistant {
  id: string;
  name: string;
  icon: keyof typeof Feather.glyphMap;
  hint: string;
}

const ASSISTANTS: Assistant[] = [
  { id: "advisor", name: "Business Advisor", icon: "compass", hint: "Strategy across the platform" },
  { id: "hr", name: "HR Assistant", icon: "users", hint: "Hiring, leave, compliance" },
  { id: "accountant", name: "Accountant", icon: "bar-chart-2", hint: "AP/AR, taxes, forecasts" },
  { id: "scheduler", name: "Scheduler", icon: "calendar", hint: "Shifts and capacity" },
  { id: "support", name: "Customer Support", icon: "message-circle", hint: "Tickets and replies" },
  { id: "marketing", name: "Marketing", icon: "send", hint: "Campaigns and copy" },
  { id: "analytics", name: "Analytics", icon: "pie-chart", hint: "KPI interpretation" },
];

const SUGGESTIONS: Record<string, string[]> = {
  advisor: ["Summarize my company in 5 bullets", "What's my biggest operational risk this week?"],
  hr: ["Draft an onboarding plan for a field technician", "Explain Canadian vacation accrual rules"],
  accountant: ["What HST should I remit on $48,200 of taxable supplies?", "Forecast Q3 payroll for 24 staff"],
  scheduler: ["Build a 2-week rotation for 8 field technicians", "Who is over 44 hrs this week?"],
  support: ["Draft a reply for a fiber outage complaint", "Summarize ticket TKT-12 in 3 lines"],
  marketing: ["Write a 4-email retention campaign for ISP customers", "3 social posts about safety training"],
  analytics: ["Explain a 12% drop in pipeline velocity", "What KPI tells me technician utilization?"],
};

export default function AIChat() {
  const [assistant, setAssistant] = useState<string>("advisor");
  const [sessionId] = useState<string>(`sess_${Date.now()}`);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<ScrollView | null>(null);

  // Load history when assistant changes (for the current session)
  useEffect(() => {
    let cancelled = false;
    apiFetch<{ messages: { role: "user" | "assistant"; content: string; created_at: string }[] }>(
      `/ai/history?session_id=${sessionId}&assistant=${assistant}`,
    )
      .then((r) => {
        if (cancelled) return;
        setMsgs(
          r.messages.map((m) => ({
            role: m.role,
            content: m.content,
            ts: new Date(m.created_at).getTime(),
          })),
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [assistant, sessionId]);

  const send = (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text || streaming) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setInput("");
    const userMsg: Msg = { role: "user", content: text, ts: Date.now() };
    const assistantMsg: Msg = { role: "assistant", content: "", ts: Date.now() + 1 };
    setMsgs((m) => [...m, userMsg, assistantMsg]);
    setStreaming(true);

    streamChat(
      { assistant, session_id: sessionId, message: text },
      (delta) => {
        setMsgs((cur) => {
          const next = [...cur];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") last.content += delta;
          return next;
        });
        scrollRef.current?.scrollToEnd({ animated: true });
      },
      () => setStreaming(false),
      (err) => {
        setStreaming(false);
        setMsgs((cur) => {
          const next = [...cur];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") last.content += `\n[stream error: ${err}]`;
          return next;
        });
      },
    );
  };

  const current = ASSISTANTS.find((a) => a.id === assistant) ?? ASSISTANTS[0];

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="ai-screen">
      <View style={styles.header}>
        <Text style={styles.title}>AI Command Center</Text>
        <Text style={styles.sub}>Powered by GPT-5.2 · {current.hint}</Text>
      </View>

      <View style={styles.selectorWrap}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.selectorContent}
        >
          {ASSISTANTS.map((a) => {
            const active = a.id === assistant;
            return (
              <Pressable
                key={a.id}
                testID={`assistant-${a.id}`}
                onPress={() => setAssistant(a.id)}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Feather
                  name={a.icon}
                  size={13}
                  color={active ? theme.colors.brand : theme.colors.onSurfaceSecondary}
                />
                <Text style={[styles.chipTxt, active && { color: theme.colors.brand }]}>
                  {a.name}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
      >
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1 }}
          contentContainerStyle={styles.stream}
        >
          {msgs.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>{current.name}</Text>
              <Text style={styles.emptyDesc}>Ask anything. Try a prompt below.</Text>
              <View style={styles.suggestions}>
                {(SUGGESTIONS[assistant] ?? []).map((s) => (
                  <Pressable
                    key={s}
                    testID={`suggestion-${s.slice(0, 12)}`}
                    style={styles.suggestion}
                    onPress={() => send(s)}
                  >
                    <Text style={styles.suggestionTxt}>{s}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : (
            msgs.map((m, i) => (
              <View
                key={i}
                style={[
                  styles.bubble,
                  m.role === "user" ? styles.bubbleUser : styles.bubbleAi,
                ]}
                testID={`msg-${m.role}-${i}`}
              >
                {m.role === "assistant" ? (
                  <View style={styles.assistantHead}>
                    <Feather name={current.icon} size={12} color={theme.colors.brand} />
                    <Text style={styles.assistantHeadTxt}>{current.name.toUpperCase()}</Text>
                  </View>
                ) : null}
                <Text
                  style={[styles.bubbleTxt, m.role === "user" && { color: "#fff" }]}
                >
                  {m.content || (streaming && i === msgs.length - 1 ? "…" : "")}
                </Text>
              </View>
            ))
          )}
        </ScrollView>

        <View style={styles.composer}>
          <TextInput
            testID="ai-input"
            placeholder={`Message ${current.name}…`}
            placeholderTextColor={theme.colors.onSurfaceSecondary}
            value={input}
            onChangeText={setInput}
            multiline
            style={styles.input}
            editable={!streaming}
          />
          <Pressable
            testID="ai-send"
            disabled={streaming || !input.trim()}
            style={[styles.sendBtn, (streaming || !input.trim()) && { opacity: 0.4 }]}
            onPress={() => send()}
          >
            <Feather name="arrow-up" size={18} color="#fff" />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.sm },
  title: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800" },
  sub: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },
  selectorWrap: { height: 56, justifyContent: "center" },
  selectorContent: { paddingHorizontal: theme.spacing.lg, gap: theme.spacing.sm, alignItems: "center" },
  chip: {
    flexShrink: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: theme.spacing.md,
    height: 36,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  chipActive: { borderColor: theme.colors.brand, backgroundColor: theme.colors.brandTertiary },
  chipTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700", letterSpacing: 0.3 },
  stream: { padding: theme.spacing.lg, paddingBottom: theme.spacing.xl },
  empty: { alignItems: "flex-start", paddingTop: theme.spacing.xl },
  emptyTitle: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800" },
  emptyDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 13, marginTop: 6, marginBottom: theme.spacing.lg },
  suggestions: { gap: theme.spacing.sm, alignSelf: "stretch" },
  suggestion: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: theme.radius.lg,
  },
  suggestionTxt: { color: theme.colors.onSurface, fontSize: 13 },
  bubble: {
    maxWidth: "92%",
    padding: theme.spacing.md,
    borderRadius: theme.radius.lg,
    marginBottom: theme.spacing.sm,
  },
  bubbleUser: { backgroundColor: theme.colors.brand, alignSelf: "flex-end", borderBottomRightRadius: 2 },
  bubbleAi: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    alignSelf: "flex-start",
    borderBottomLeftRadius: 2,
  },
  assistantHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  assistantHeadTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 1.2 },
  bubbleTxt: { color: theme.colors.onSurface, fontSize: 14, lineHeight: 20 },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    borderTopWidth: 1,
    borderTopColor: theme.colors.divider,
    backgroundColor: theme.colors.surface,
  },
  input: {
    flex: 1,
    color: theme.colors.onSurface,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.md,
    paddingTop: 10,
    paddingBottom: 10,
    fontSize: 14,
    maxHeight: 120,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: theme.colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
});
