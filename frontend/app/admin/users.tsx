import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  ActivityIndicator,
  Modal,
  Image,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";

import { apiFetch } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { theme } from "@/src/theme";

interface Member {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
  memberships: { membership_id: string; role: string; company_id: string }[];
}

const ROLE_OPTIONS: { id: "owner" | "manager" | "employee" | "customer"; label: string; emoji: string }[] = [
  { id: "owner", label: "OWNER", emoji: "👑" },
  { id: "manager", label: "MANAGER", emoji: "🧑‍💼" },
  { id: "employee", label: "EMPLOYEE", emoji: "👷" },
  { id: "customer", label: "CUSTOMER", emoji: "🛒" },
];

export default function AdminUsers() {
  const router = useRouter();
  const { user } = useAuth();
  const { active } = useCompanies();
  const isOwner = user?.active_role === "owner" || user?.role === "admin";

  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Member | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ users: Member[]; company_id: string }>("/admin/users");
      setMembers(r.users);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOwner) load();
    else setLoading(false);
  }, [isOwner, load, active?.company_id]);

  const setRole = async (m: Member, role: string) => {
    setSaving(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => undefined);
    try {
      await apiFetch(`/admin/users/${m.user_id}/role`, {
        method: "POST",
        body: JSON.stringify({ role }),
      });
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  };

  const currentRole = (m: Member) =>
    m.memberships.find((x) => x.company_id === active?.company_id)?.role ?? "—";

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="admin-users-screen">
      <View style={styles.header}>
        <Pressable testID="admin-back" onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="chevron-left" size={20} color={theme.colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>User Roles</Text>
          <Text style={styles.sub}>{active?.name ?? "—"} · Workspace administration</Text>
        </View>
        <View style={styles.ownerPill}>
          <Feather name="award" size={11} color={theme.colors.brand} />
          <Text style={styles.ownerPillTxt}>OWNER</Text>
        </View>
      </View>

      {!isOwner ? (
        <View style={styles.gate}>
          <Feather name="lock" size={28} color={theme.colors.warning} />
          <Text style={styles.gateTitle}>Owner access required</Text>
          <Text style={styles.gateDesc}>
            Role assignment is restricted to the workspace owner. Switch to your Owner workspace if you have one.
          </Text>
        </View>
      ) : loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <FlatList
          data={members}
          keyExtractor={(m) => m.user_id}
          contentContainerStyle={{ padding: theme.spacing.lg, paddingBottom: 80 }}
          ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
          renderItem={({ item }) => {
            const r = currentRole(item);
            const meta = ROLE_OPTIONS.find((o) => o.id === r);
            const initials = item.name.split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
            return (
              <Pressable
                testID={`admin-user-${item.user_id}`}
                onPress={() => setEditing(item)}
                style={styles.row}
              >
                {item.picture ? (
                  <Image source={{ uri: item.picture }} style={styles.avatar} />
                ) : (
                  <View style={[styles.avatar, styles.avatarFallback]}>
                    <Text style={styles.avatarTxt}>{initials || "AU"}</Text>
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowName}>{item.name}</Text>
                  <Text style={styles.rowEmail}>{item.email}</Text>
                </View>
                <View style={styles.roleChip}>
                  <Text style={styles.roleEmoji}>{meta?.emoji ?? "—"}</Text>
                  <Text style={styles.roleLabel}>{meta?.label ?? r.toUpperCase()}</Text>
                </View>
              </Pressable>
            );
          }}
        />
      )}

      <Modal visible={!!editing} transparent animationType="slide" onRequestClose={() => setEditing(null)}>
        <Pressable style={styles.backdrop} onPress={() => setEditing(null)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>Assign role</Text>
              <Pressable onPress={() => setEditing(null)} testID="admin-edit-close">
                <Feather name="x" size={20} color={theme.colors.onSurface} />
              </Pressable>
            </View>
            <Text style={styles.sheetSub}>{editing?.name} · {active?.name}</Text>
            {ROLE_OPTIONS.map((r) => {
              const current = editing ? currentRole(editing) === r.id : false;
              return (
                <Pressable
                  key={r.id}
                  testID={`assign-role-${r.id}`}
                  disabled={saving}
                  onPress={() => editing && setRole(editing, r.id)}
                  style={[styles.optionRow, current && styles.optionRowActive]}
                >
                  <Text style={styles.optionEmoji}>{r.emoji}</Text>
                  <Text style={styles.optionLabel}>{r.label}</Text>
                  {current ? (
                    <View style={styles.optionCurrent}><Text style={styles.optionCurrentTxt}>CURRENT</Text></View>
                  ) : (
                    <Feather name="arrow-right" size={16} color={theme.colors.onSurfaceSecondary} />
                  )}
                </Pressable>
              );
            })}
            {saving ? <ActivityIndicator color={theme.colors.brand} style={{ marginTop: 14 }} /> : null}
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.sm,
    paddingBottom: theme.spacing.md,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800" },
  sub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  ownerPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    backgroundColor: theme.colors.brandTertiary,
  },
  ownerPillTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  gate: { flex: 1, padding: 32, alignItems: "center", justifyContent: "center", gap: 14 },
  gateTitle: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800", textAlign: "center" },
  gateDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19, textAlign: "center", maxWidth: 320 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: theme.colors.brandTertiary },
  avatarFallback: { alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: theme.colors.brand },
  avatarTxt: { color: theme.colors.brand, fontWeight: "800", fontSize: 13 },
  rowName: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800" },
  rowEmail: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  roleChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surfaceTertiary,
  },
  roleEmoji: { fontSize: 14 },
  roleLabel: { color: theme.colors.onSurface, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.75)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderTopLeftRadius: theme.radius.lg,
    borderTopRightRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    borderTopWidth: 1,
    borderColor: theme.colors.border,
    gap: theme.spacing.sm,
  },
  sheetHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  sheetTitle: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800" },
  sheetSub: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginBottom: theme.spacing.md },
  optionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    padding: theme.spacing.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
  },
  optionRowActive: { borderColor: theme.colors.brand, backgroundColor: theme.colors.brandTertiary },
  optionEmoji: { fontSize: 22 },
  optionLabel: { color: theme.colors.onSurface, flex: 1, fontWeight: "700" },
  optionCurrent: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.brand,
  },
  optionCurrentTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
});
