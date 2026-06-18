import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";

import { apiFetch } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { theme } from "@/src/theme";

export interface Workspace {
  membership_id: string;
  company_id: string;
  company_name: string;
  industry: string;
  logo_color: string;
  role: "owner" | "manager" | "employee" | "customer";
}

const ROLE_META: Record<
  string,
  { icon: keyof typeof Feather.glyphMap; label: string; emoji: string; tagline: string }
> = {
  owner: { icon: "award", emoji: "👑", label: "OWNER", tagline: "Full command of the business" },
  manager: { icon: "briefcase", emoji: "🧑‍💼", label: "MANAGER", tagline: "Operations & teams" },
  employee: { icon: "tool", emoji: "👷", label: "EMPLOYEE", tagline: "Your shifts, tasks & pay" },
  customer: { icon: "shopping-bag", emoji: "🛒", label: "CUSTOMER", tagline: "Orders & support" },
};

export default function Workspaces() {
  const router = useRouter();
  const { user, refresh } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{
        workspaces: Workspace[];
        active_company_id: string;
        active_role: string;
      }>("/workspaces");
      setWorkspaces(r.workspaces);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const choose = async (w: Workspace) => {
    setSwitching(w.membership_id);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => undefined);
    try {
      await apiFetch("/workspaces/switch", {
        method: "POST",
        body: JSON.stringify({ company_id: w.company_id, role: w.role }),
      });
      await refresh();
      router.replace("/(tabs)");
    } finally {
      setSwitching(null);
    }
  };

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]} testID="workspaces-screen">
      <LinearGradient colors={["#0F0F12", "#090A0C"]} style={styles.gradient}>
        <View style={styles.header}>
          <View style={styles.logoMark}>
            <Feather name="command" size={20} color={theme.colors.brand} />
          </View>
          <View>
            <Text style={styles.brand}>AIDOU COMMAND</Text>
            <Text style={styles.welcome}>Welcome back, {user?.name?.split(" ")[0] ?? "Operator"}</Text>
          </View>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroBig}>Who are you</Text>
          <Text style={styles.heroBigAccent}>today?</Text>
          <Text style={styles.heroDesc}>
            Your identity spans the entire Aidou ecosystem. Pick the workspace and role you want for
            this session — one tap and the whole app reshapes around you.
          </Text>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color={theme.colors.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.scroll}>
            {workspaces.map((w) => {
              const meta = ROLE_META[w.role] ?? ROLE_META.employee;
              const isSwitching = switching === w.membership_id;
              return (
                <Pressable
                  key={w.membership_id}
                  testID={`workspace-${w.membership_id}`}
                  disabled={isSwitching}
                  onPress={() => choose(w)}
                  style={({ pressed }) => [
                    styles.card,
                    { borderLeftColor: w.logo_color },
                    pressed && { borderColor: theme.colors.brand },
                  ]}
                >
                  <View
                    style={[
                      styles.roleBadge,
                      { backgroundColor: w.logo_color + "22", borderColor: w.logo_color },
                    ]}
                  >
                    <Text style={[styles.roleEmoji]}>{meta.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.cardCompany}>{w.company_name}</Text>
                    <Text style={styles.cardIndustry}>{w.industry}</Text>
                    <View style={styles.roleRow}>
                      <Feather name={meta.icon} size={11} color={theme.colors.brand} />
                      <Text style={styles.roleLabel}>{meta.label}</Text>
                      <Text style={styles.roleTagline}>· {meta.tagline}</Text>
                    </View>
                  </View>
                  {isSwitching ? (
                    <ActivityIndicator size="small" color={theme.colors.brand} />
                  ) : (
                    <Feather name="arrow-right" size={18} color={theme.colors.onSurfaceSecondary} />
                  )}
                </Pressable>
              );
            })}
            <Text style={styles.footnote}>
              {workspaces.length} workspaces · one identity · automatic role detection on every sign-in
            </Text>
          </ScrollView>
        )}
      </LinearGradient>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  gradient: { flex: 1, paddingHorizontal: theme.spacing.lg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
  },
  logoMark: {
    width: 38,
    height: 38,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: theme.colors.brand,
  },
  brand: { color: theme.colors.onSurface, fontSize: 12, fontWeight: "800", letterSpacing: 2 },
  welcome: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  hero: { paddingTop: theme.spacing.lg, paddingBottom: theme.spacing.lg },
  heroBig: { color: theme.colors.onSurface, fontSize: 34, fontWeight: "800", letterSpacing: -1, lineHeight: 38 },
  heroBigAccent: { color: theme.colors.brand, fontSize: 34, fontWeight: "800", letterSpacing: -1, lineHeight: 38 },
  heroDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 13, lineHeight: 20, marginTop: theme.spacing.md },
  center: { alignItems: "center", paddingTop: 60 },
  scroll: { paddingBottom: 60, gap: theme.spacing.sm },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    padding: theme.spacing.md,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderLeftWidth: 4,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceSecondary,
  },
  roleBadge: {
    width: 52,
    height: 52,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  roleEmoji: { fontSize: 24 },
  cardCompany: { color: theme.colors.onSurface, fontSize: 15, fontWeight: "800" },
  cardIndustry: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  roleRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 6 },
  roleLabel: { color: theme.colors.brand, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  roleTagline: { color: theme.colors.onSurfaceSecondary, fontSize: 10 },
  footnote: { color: theme.colors.onSurfaceSecondary, fontSize: 11, textAlign: "center", marginTop: theme.spacing.xl },
});
