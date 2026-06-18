import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { apiFetch } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { theme } from "@/src/theme";

interface Entry {
  audit_id: string;
  user_email: string;
  role: string;
  action: string;
  resource: string;
  created_at: string;
  meta?: Record<string, unknown>;
  ip?: string | null;
}

const ICON: Record<string, keyof typeof Feather.glyphMap> = {
  login: "log-in",
  switch: "shuffle",
  create: "plus-circle",
  view: "eye",
  update: "edit-2",
};

export default function AuditLog() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = (user?.role ?? "viewer") === "admin";

  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{ entries: Entry[] }>("/audit/log?limit=200");
      setEntries(r.entries);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    load();
  }, [load, isAdmin]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="audit-screen">
      <View style={styles.header}>
        <Pressable testID="audit-back" onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="chevron-left" size={20} color={theme.colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Audit Log</Text>
          <Text style={styles.sub}>Compliance & security trail</Text>
        </View>
        <View style={styles.adminPill}>
          <Feather name="shield" size={11} color={theme.colors.brand} />
          <Text style={styles.adminPillTxt}>ADMIN</Text>
        </View>
      </View>

      {!isAdmin ? (
        <View style={styles.gate}>
          <Feather name="lock" size={28} color={theme.colors.warning} />
          <Text style={styles.gateTitle}>Admin access only</Text>
          <Text style={styles.gateDesc}>
            The audit log is restricted to administrators. Your current role is
            {" "}
            <Text style={{ color: theme.colors.brand }}>{(user?.role ?? "viewer").toUpperCase()}</Text>.
            Contact your account owner to request elevated access.
          </Text>
        </View>
      ) : loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : error ? (
        <View style={styles.gate}>
          <Feather name="alert-triangle" size={28} color={theme.colors.error} />
          <Text style={styles.gateTitle}>Could not load audit log</Text>
          <Text style={styles.gateDesc}>{error}</Text>
        </View>
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(e) => e.audit_id}
          contentContainerStyle={{ padding: theme.spacing.lg, paddingBottom: 80 }}
          ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
          refreshControl={
            <RefreshControl
              tintColor={theme.colors.brand}
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
          ListEmptyComponent={
            <View style={styles.gate}>
              <Feather name="inbox" size={28} color={theme.colors.onSurfaceSecondary} />
              <Text style={styles.gateTitle}>No audit entries yet</Text>
              <Text style={styles.gateDesc}>Actions like creating tickets, sales and switching companies will appear here.</Text>
            </View>
          }
          renderItem={({ item }) => {
            const date = new Date(item.created_at);
            const time =
              date.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
              " · " +
              date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
            const metaPairs = Object.entries(item.meta ?? {}).slice(0, 2);
            return (
              <View style={styles.row} testID={`audit-${item.audit_id}`}>
                <View style={styles.iconWrap}>
                  <Feather
                    name={ICON[item.action] ?? "activity"}
                    size={14}
                    color={theme.colors.brand}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowTitle}>
                    <Text style={{ fontWeight: "800" }}>{item.action.toUpperCase()}</Text>
                    <Text style={{ color: theme.colors.onSurfaceSecondary }}> · {item.resource}</Text>
                  </Text>
                  <Text style={styles.rowMeta} numberOfLines={1}>
                    {item.user_email} · {time}
                    {metaPairs.length
                      ? " · " + metaPairs.map(([k, v]) => `${k}=${String(v)}`).join(" ")
                      : ""}
                  </Text>
                </View>
                <Text style={styles.rolePill}>{(item.role ?? "").toUpperCase()}</Text>
              </View>
            );
          }}
        />
      )}
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
  adminPill: {
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
  adminPillTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  gate: { flex: 1, padding: 32, alignItems: "center", justifyContent: "center", gap: 14 },
  gateTitle: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800", textAlign: "center" },
  gateDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19, textAlign: "center", maxWidth: 320 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
  },
  iconWrap: {
    width: 30,
    height: 30,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  rowTitle: { color: theme.colors.onSurface, fontSize: 13 },
  rowMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 4 },
  rolePill: {
    color: theme.colors.brand,
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.5,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
  },
});
