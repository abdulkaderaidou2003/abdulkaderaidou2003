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

import { apiFetch } from "@/src/api/client";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { theme } from "@/src/theme";

interface Alert {
  alert_id: string;
  title: string;
  severity: "high" | "medium" | "low";
  kind: string;
  created_at: string;
  read: boolean;
}

const ICON: Record<string, keyof typeof Feather.glyphMap> = {
  tax: "file-text",
  insurance: "umbrella",
  compliance: "flag",
  fleet: "truck",
  labour: "shield",
  security: "lock",
};

export default function Alerts() {
  const { active } = useCompanies();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{ alerts: Alert[] }>("/alerts");
      setAlerts(r.alerts);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
  }, [active?.company_id, load]);

  const visible = filter === "all" ? alerts : alerts.filter((a) => a.severity === filter);

  const markRead = async (id: string) => {
    setAlerts((cur) => cur.map((a) => (a.alert_id === id ? { ...a, read: true } : a)));
    try {
      await apiFetch(`/alerts/${id}/read`, { method: "POST" });
    } catch {}
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="alerts-screen">
      <View style={styles.header}>
        <Text style={styles.title}>Alerts & Compliance</Text>
        <Text style={styles.sub}>
          {alerts.filter((a) => !a.read).length} unread for {active?.name ?? "company"}
        </Text>
      </View>

      <View style={styles.chipRow}>
        {(["all", "high", "medium", "low"] as const).map((f) => {
          const active2 = f === filter;
          return (
            <Pressable
              key={f}
              testID={`alerts-filter-${f}`}
              onPress={() => setFilter(f)}
              style={[styles.chip, active2 && styles.chipActive]}
            >
              <Text style={[styles.chipTxt, active2 && { color: theme.colors.brand }]}>
                {f.toUpperCase()}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <FlatList
          data={visible}
          keyExtractor={(it) => it.alert_id}
          contentContainerStyle={{ padding: theme.spacing.lg, paddingBottom: 90 }}
          ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              tintColor={theme.colors.brand}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Feather name="check-circle" size={28} color={theme.colors.success} />
              <Text style={styles.emptyTxt}>All clear. No alerts.</Text>
            </View>
          }
          renderItem={({ item }) => {
            const color =
              item.severity === "high"
                ? theme.colors.brand
                : item.severity === "medium"
                ? theme.colors.warning
                : theme.colors.success;
            return (
              <Pressable
                testID={`alert-${item.alert_id}`}
                onPress={() => markRead(item.alert_id)}
                style={[styles.card, { borderLeftColor: color }]}
              >
                <View style={styles.cardIcon}>
                  <Feather
                    name={ICON[item.kind] ?? "alert-triangle"}
                    size={16}
                    color={color}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.cardTitle, !item.read && { fontWeight: "800" }]}>
                    {item.title}
                  </Text>
                  <Text style={styles.cardMeta}>
                    {item.kind.toUpperCase()} · {item.severity.toUpperCase()}
                  </Text>
                </View>
                {!item.read ? <View style={[styles.unreadDot, { backgroundColor: color }]} /> : null}
              </Pressable>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.sm, paddingBottom: theme.spacing.sm },
  title: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800" },
  sub: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },
  chipRow: { flexDirection: "row", gap: theme.spacing.sm, paddingHorizontal: theme.spacing.lg, paddingBottom: theme.spacing.md },
  chip: {
    paddingHorizontal: theme.spacing.md,
    height: 32,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: { borderColor: theme.colors.brand, backgroundColor: theme.colors.brandTertiary },
  chipTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderLeftWidth: 3,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
  },
  cardIcon: {
    width: 32,
    height: 32,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: { color: theme.colors.onSurface, fontSize: 13 },
  cardMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 10, marginTop: 4, letterSpacing: 1 },
  unreadDot: { width: 8, height: 8, borderRadius: 4 },
  empty: { alignItems: "center", paddingTop: 60, gap: theme.spacing.md },
  emptyTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 13 },
});
