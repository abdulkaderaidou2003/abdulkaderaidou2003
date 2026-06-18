import React from "react";
import { View, Text, StyleSheet, ScrollView, Pressable, Image } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { useAuth } from "@/src/contexts/AuthContext";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { CompanySwitcher } from "@/src/components/CompanySwitcher";
import { theme } from "@/src/theme";

interface Row {
  label: string;
  icon: keyof typeof Feather.glyphMap;
  hint?: string;
  href?: string;
}

const SECTIONS: { title: string; rows: Row[] }[] = [
  {
    title: "ACCOUNT",
    rows: [
      { label: "My profile", icon: "user" },
      { label: "Security & MFA", icon: "shield" },
      { label: "Notifications", icon: "bell" },
    ],
  },
  {
    title: "PLATFORM",
    rows: [
      { label: "Modular pricing", icon: "package", hint: "Add or remove modules" },
      { label: "Onboarding team", icon: "users", hint: "Talk to your CSM" },
      { label: "24/7 support", icon: "phone", hint: "Chat, voice, email" },
      { label: "Weekly updates", icon: "refresh-cw", hint: "Latest changelog" },
    ],
  },
  {
    title: "CONTROLS",
    rows: [
      { label: "User roles", icon: "users", href: "/admin/users", hint: "Assign owner / manager / employee / customer" },
      { label: "Switch workspace", icon: "shuffle", href: "/workspaces", hint: "Multi-role identity selector" },
      { label: "Audit log", icon: "list", href: "/audit", hint: "Compliance & security trail" },
      { label: "Backups & DR", icon: "database" },
      { label: "API & integrations", icon: "code" },
    ],
  },
];

export default function Profile() {
  const { user, signOut } = useAuth();
  const { active } = useCompanies();
  const router = useRouter();

  const initials = (user?.name ?? "")
    .split(" ")
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="profile-screen">
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <Text style={styles.title}>Profile</Text>
        </View>

        <View style={styles.card}>
          {user?.picture ? (
            <Image source={{ uri: user.picture }} style={styles.avatar} />
          ) : (
            <View style={[styles.avatar, styles.avatarFallback]}>
              <Text style={styles.avatarTxt}>{initials || "AU"}</Text>
            </View>
          )}
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{user?.name ?? "Aidou Operator"}</Text>
            <Text style={styles.email}>{user?.email ?? "—"}</Text>
            <View style={styles.roleBadge}>
              <Feather name="shield" size={10} color={theme.colors.brand} />
              <Text style={styles.roleTxt}>{(user?.role ?? "admin").toUpperCase()}</Text>
            </View>
          </View>
        </View>

        <Text style={styles.sectionLabel}>ACTIVE COMPANY</Text>
        <CompanySwitcher />
        <Text style={styles.muted}>
          You belong to {user?.company_ids?.length ?? 0} companies. All HR, accounting and reporting
          can be shared or kept separate per company.
        </Text>

        {SECTIONS.map((s) => (
          <View key={s.title} style={{ marginTop: theme.spacing.xl }}>
            <Text style={styles.sectionLabel}>{s.title}</Text>
            <View style={styles.list}>
              {s.rows.map((r, i) => (
                <Pressable
                  key={r.label}
                  testID={`profile-row-${r.label.toLowerCase().replace(/\s+/g, "-")}`}
                  onPress={() => r.href && router.push(r.href as never)}
                  style={[
                    styles.listRow,
                    i < s.rows.length - 1 && {
                      borderBottomWidth: 1,
                      borderBottomColor: theme.colors.divider,
                    },
                  ]}
                >
                  <Feather name={r.icon} size={16} color={theme.colors.onSurfaceSecondary} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowLabel}>{r.label}</Text>
                    {r.hint ? <Text style={styles.rowHint}>{r.hint}</Text> : null}
                  </View>
                  <Feather name="chevron-right" size={16} color={theme.colors.onSurfaceSecondary} />
                </Pressable>
              ))}
            </View>
          </View>
        ))}

        <Pressable testID="signout-btn" onPress={signOut} style={styles.signout}>
          <Feather name="log-out" size={16} color={theme.colors.error} />
          <Text style={styles.signoutTxt}>Sign out</Text>
        </Pressable>

        <Text style={styles.version}>Aidou Command Enterprise Ultimate · v1.0 · {active?.name}</Text>
        <View style={{ height: 60 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  scroll: { padding: theme.spacing.lg },
  header: { marginBottom: theme.spacing.md },
  title: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800" },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: theme.colors.brandTertiary },
  avatarFallback: { alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: theme.colors.brand },
  avatarTxt: { color: theme.colors.brand, fontWeight: "800", fontSize: 18 },
  name: { color: theme.colors.onSurface, fontSize: 16, fontWeight: "800" },
  email: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    alignSelf: "flex-start",
    backgroundColor: theme.colors.brandTertiary,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: theme.radius.sm,
    marginTop: 6,
  },
  roleTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  sectionLabel: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: theme.spacing.sm,
    marginTop: theme.spacing.lg,
  },
  muted: { color: theme.colors.onSurfaceSecondary, fontSize: 11, lineHeight: 16, marginTop: theme.spacing.sm },
  list: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    overflow: "hidden",
  },
  listRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.md,
  },
  rowLabel: { color: theme.colors.onSurface, fontSize: 13 },
  rowHint: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  signout: {
    marginTop: theme.spacing.xl,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: theme.colors.error,
    borderRadius: theme.radius.lg,
  },
  signoutTxt: { color: theme.colors.error, fontWeight: "700", fontSize: 14 },
  version: { textAlign: "center", color: theme.colors.onSurfaceSecondary, fontSize: 10, marginTop: theme.spacing.lg },
});
