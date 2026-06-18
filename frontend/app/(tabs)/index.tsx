import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Pressable,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { CompanySwitcher } from "@/src/components/CompanySwitcher";
import { apiFetch } from "@/src/api/client";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { useAuth } from "@/src/contexts/AuthContext";
import { theme } from "@/src/theme";

interface Kpis {
  revenue_mtd: number;
  payroll_mtd: number;
  pipeline: number;
  employees_total: number;
  employees_active: number;
  open_tickets: number;
  high_priority_tickets: number;
  customers: number;
  alerts_unread: number;
}
interface FeedItem {
  ticket_id: string;
  title: string;
  priority: string;
  status: string;
  assignee: string;
  created_at: string;
}

function fmtMoney(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n}`;
}

const KpiCard = ({
  label,
  value,
  delta,
  icon,
  accent,
  testID,
}: {
  label: string;
  value: string;
  delta?: string;
  icon: keyof typeof Feather.glyphMap;
  accent?: boolean;
  testID?: string;
}) => (
  <View
    style={[styles.kpi, accent && { borderColor: theme.colors.brand }]}
    testID={testID}
  >
    <View style={styles.kpiHead}>
      <Feather
        name={icon}
        size={14}
        color={accent ? theme.colors.brand : theme.colors.onSurfaceSecondary}
      />
      <Text style={styles.kpiLabel}>{label}</Text>
    </View>
    <Text style={styles.kpiValue}>{value}</Text>
    {delta ? <Text style={styles.kpiDelta}>{delta}</Text> : null}
  </View>
);

export default function Dashboard() {
  const { active } = useCompanies();
  const { user } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<{ kpis: Kpis; feed: FeedItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{ kpis: Kpis; feed: FeedItem[] }>("/dashboard");
      setData(r);
    } catch (e) {
      console.warn(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
  }, [active?.company_id, load]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="dashboard-screen">
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.helloTxt}>Good day, {user?.name?.split(" ")[0] ?? "Operator"}</Text>
          <Text style={styles.headerSub}>Command center · real-time</Text>
        </View>
        <View style={styles.statusDot}>
          <View style={styles.pulse} />
          <Text style={styles.statusTxt}>LIVE</Text>
        </View>
      </View>
      <View style={styles.switcherWrap}>
        <CompanySwitcher />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
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
        >
          <Text style={styles.sectionLabel}>OPERATIONAL KPIS</Text>
          <View style={styles.grid}>
            <KpiCard
              label="REVENUE MTD"
              value={fmtMoney(data?.kpis.revenue_mtd ?? 0)}
              delta="+8.4% vs last"
              icon="trending-up"
              accent
              testID="kpi-revenue"
            />
            <KpiCard
              label="PAYROLL MTD"
              value={fmtMoney(data?.kpis.payroll_mtd ?? 0)}
              delta="On budget"
              icon="credit-card"
              testID="kpi-payroll"
            />
            <KpiCard
              label="PIPELINE"
              value={fmtMoney(data?.kpis.pipeline ?? 0)}
              delta="42 deals"
              icon="git-branch"
              testID="kpi-pipeline"
            />
            <KpiCard
              label="EMPLOYEES"
              value={`${data?.kpis.employees_active ?? 0} / ${data?.kpis.employees_total ?? 0}`}
              delta="Active / total"
              icon="users"
              testID="kpi-employees"
            />
            <KpiCard
              label="OPEN TICKETS"
              value={String(data?.kpis.open_tickets ?? 0)}
              delta={`${data?.kpis.high_priority_tickets ?? 0} high pri`}
              icon="clipboard"
              accent={(data?.kpis.high_priority_tickets ?? 0) > 0}
              testID="kpi-tickets"
            />
            <KpiCard
              label="CUSTOMERS"
              value={String(data?.kpis.customers ?? 0)}
              delta="+3 this week"
              icon="user-check"
              testID="kpi-customers"
            />
          </View>

          <View style={styles.aiCard} testID="ai-quick-action">
            <View style={styles.aiHead}>
              <Feather name="cpu" size={16} color={theme.colors.brand} />
              <Text style={styles.aiTitle}>AI EXECUTIVE SUMMARY</Text>
            </View>
            <Text style={styles.aiBody}>
              {active?.name} is tracking on revenue and payroll. {data?.kpis.high_priority_tickets ?? 0}
              {" "}high-priority tickets need triage. Pipeline up 8.4% — recommend reviewing the top 5 deals
              with sales leads this week.
            </Text>
            <Pressable
              testID="open-ai-cta"
              style={styles.aiCta}
              onPress={() => router.push("/(tabs)/ai")}
            >
              <Text style={styles.aiCtaTxt}>Ask AI Command Center</Text>
              <Feather name="arrow-right" size={14} color={theme.colors.brand} />
            </Pressable>
          </View>

          <Text style={styles.sectionLabel}>LIVE OPERATIONS FEED</Text>
          <View style={styles.feed}>
            {(data?.feed ?? []).map((f) => (
              <Pressable
                key={f.ticket_id}
                testID={`feed-${f.ticket_id}`}
                style={styles.feedRow}
                onPress={() => router.push("/module/tickets")}
              >
                <View
                  style={[
                    styles.feedDot,
                    {
                      backgroundColor:
                        f.priority === "high"
                          ? theme.colors.brand
                          : f.priority === "medium"
                          ? theme.colors.warning
                          : theme.colors.success,
                    },
                  ]}
                />
                <View style={{ flex: 1 }}>
                  <Text style={styles.feedTitle} numberOfLines={1}>
                    {f.title}
                  </Text>
                  <Text style={styles.feedMeta}>
                    {f.assignee} · {f.status.toUpperCase()}
                  </Text>
                </View>
                <Feather name="chevron-right" size={16} color={theme.colors.onSurfaceSecondary} />
              </Pressable>
            ))}
          </View>
          <View style={{ height: 80 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.sm,
    paddingBottom: theme.spacing.md,
  },
  helloTxt: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800" },
  headerSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2, letterSpacing: 1 },
  statusDot: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: theme.colors.brandTertiary,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.brand,
  },
  pulse: { width: 6, height: 6, borderRadius: 3, backgroundColor: theme.colors.brand },
  statusTxt: { color: theme.colors.brand, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  switcherWrap: { paddingHorizontal: theme.spacing.lg, marginBottom: theme.spacing.lg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  scroll: { paddingHorizontal: theme.spacing.lg, paddingBottom: theme.spacing.xl },
  sectionLabel: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: theme.spacing.sm,
    marginTop: theme.spacing.sm,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: theme.spacing.sm },
  kpi: {
    width: "48.5%",
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  kpiHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8 },
  kpiLabel: { color: theme.colors.onSurfaceSecondary, fontSize: 10, fontWeight: "700", letterSpacing: 1 },
  kpiValue: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800", letterSpacing: -0.5 },
  kpiDelta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 4 },
  aiCard: {
    marginTop: theme.spacing.lg,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
  },
  aiHead: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: theme.spacing.sm },
  aiTitle: { color: theme.colors.brand, fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  aiBody: { color: theme.colors.onSurfaceTertiary, fontSize: 13, lineHeight: 19 },
  aiCta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: theme.spacing.md,
  },
  aiCtaTxt: { color: theme.colors.brand, fontSize: 12, fontWeight: "700", letterSpacing: 0.5 },
  feed: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    overflow: "hidden",
  },
  feedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    padding: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.divider,
  },
  feedDot: { width: 8, height: 8, borderRadius: 4 },
  feedTitle: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "600" },
  feedMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
});
