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
  const [brief, setBrief] = useState<string | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);

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

  const loadBrief = useCallback(async () => {
    setBriefLoading(true);
    try {
      const r = await apiFetch<{ brief: string }>("/ai/ops-brief");
      setBrief(r.brief);
    } catch (e) {
      console.warn(e);
      setBrief(null);
    } finally {
      setBriefLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setBrief(null);
    load();
    loadBrief();
  }, [active?.company_id, load, loadBrief]);

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
          <View style={styles.roleStrip} testID="dashboard-role-strip">
            <Text style={styles.roleStripLabel}>
              {(() => {
                const r = user?.active_role ?? "owner";
                if (r === "owner") return "👑 OWNER DASHBOARD";
                if (r === "manager") return "🧑‍💼 MANAGER DASHBOARD";
                if (r === "employee") return "👷 EMPLOYEE DASHBOARD";
                return "🛒 CUSTOMER DASHBOARD";
              })()}
            </Text>
            <Pressable
              onPress={() => router.push("/workspaces")}
              testID="dashboard-switch-workspace"
              style={styles.roleStripBtn}
            >
              <Feather name="shuffle" size={11} color={theme.colors.brand} />
              <Text style={styles.roleStripBtnTxt}>SWITCH</Text>
            </Pressable>
          </View>
          {user?.active_role === "customer" ? (
            <CustomerSections />
          ) : user?.active_role === "employee" ? (
            <EmployeeSections />
          ) : (
            <ManagementSections data={data} active={active} brief={brief} briefLoading={briefLoading} loadBrief={loadBrief} router={router} />
          )}
          <View style={{ height: 80 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

// ----- Role-aware section components -----

function ManagementSections({
  data,
  active,
  brief,
  briefLoading,
  loadBrief,
  router,
}: {
  data: { kpis: Kpis; feed: FeedItem[] } | null;
  active: { name?: string } | null;
  brief: string | null;
  briefLoading: boolean;
  loadBrief: () => void;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <>
      <Text style={styles.sectionLabel}>OPERATIONAL KPIS</Text>
      <View style={styles.grid}>
        <KpiCard label="REVENUE MTD" value={fmtMoney(data?.kpis.revenue_mtd ?? 0)} delta="+8.4% vs last" icon="trending-up" accent testID="kpi-revenue" />
        <KpiCard label="PAYROLL MTD" value={fmtMoney(data?.kpis.payroll_mtd ?? 0)} delta="On budget" icon="credit-card" testID="kpi-payroll" />
        <KpiCard label="PIPELINE" value={fmtMoney(data?.kpis.pipeline ?? 0)} delta="42 deals" icon="git-branch" testID="kpi-pipeline" />
        <KpiCard label="EMPLOYEES" value={`${data?.kpis.employees_active ?? 0} / ${data?.kpis.employees_total ?? 0}`} delta="Active / total" icon="users" testID="kpi-employees" />
        <KpiCard label="OPEN TICKETS" value={String(data?.kpis.open_tickets ?? 0)} delta={`${data?.kpis.high_priority_tickets ?? 0} high pri`} icon="clipboard" accent={(data?.kpis.high_priority_tickets ?? 0) > 0} testID="kpi-tickets" />
        <KpiCard label="CUSTOMERS" value={String(data?.kpis.customers ?? 0)} delta="+3 this week" icon="user-check" testID="kpi-customers" />
      </View>

      <View style={styles.aiCard} testID="ai-quick-action">
        <View style={styles.aiHead}>
          <Feather name="cpu" size={16} color={theme.colors.brand} />
          <Text style={styles.aiTitle}>AI DAILY OPS BRIEF</Text>
          <View style={{ flex: 1 }} />
          <Pressable testID="ops-brief-refresh" onPress={loadBrief} disabled={briefLoading} style={styles.briefRefresh}>
            {briefLoading ? <ActivityIndicator size="small" color={theme.colors.brand} /> : <Feather name="refresh-cw" size={12} color={theme.colors.brand} />}
          </Pressable>
        </View>
        {briefLoading && !brief ? (
          <Text style={styles.aiBody}>Generating brief from live ops data…</Text>
        ) : brief ? (
          <Text style={styles.aiBody} testID="ai-ops-brief-text">{brief}</Text>
        ) : (
          <Text style={styles.aiBody}>Tap refresh to generate today's brief.</Text>
        )}
        <Pressable testID="open-ai-cta" style={styles.aiCta} onPress={() => router.push("/(tabs)/ai")}>
          <Text style={styles.aiCtaTxt}>Ask AI Command Center</Text>
          <Feather name="arrow-right" size={14} color={theme.colors.brand} />
        </Pressable>
      </View>

      <Text style={styles.sectionLabel}>LIVE OPERATIONS FEED · {active?.name?.toUpperCase() ?? ""}</Text>
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
                    f.priority === "high" ? theme.colors.brand : f.priority === "medium" ? theme.colors.warning : theme.colors.success,
                },
              ]}
            />
            <View style={{ flex: 1 }}>
              <Text style={styles.feedTitle} numberOfLines={1}>{f.title}</Text>
              <Text style={styles.feedMeta}>{f.assignee} · {f.status.toUpperCase()}</Text>
            </View>
            <Feather name="chevron-right" size={16} color={theme.colors.onSurfaceSecondary} />
          </Pressable>
        ))}
      </View>
    </>
  );
}

function EmployeeSections() {
  const router = useRouter();
  const [punchData, setPunchData] = useState<{
    open_punch: { punch_id: string; clock_in: string } | null;
    minutes_today: number;
  } | null>(null);
  const [punching, setPunching] = useState(false);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{
        open_punch: { punch_id: string; clock_in: string } | null;
        minutes_today: number;
        punches: unknown[];
      }>("/timeclock/me");
      setPunchData(r);
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => setTick((c) => c + 1), 30000);
    return () => clearInterval(t);
  }, [load]);

  const isClockedIn = !!punchData?.open_punch;
  const runningMinutes = (() => {
    if (!isClockedIn) return punchData?.minutes_today ?? 0;
    const start = new Date(punchData!.open_punch!.clock_in).getTime();
    const delta = Math.max(0, Math.floor((Date.now() - start) / 60000));
    return (punchData!.minutes_today ?? 0);
  })();
  void tick; // re-render every 30s
  const hh = Math.floor(runningMinutes / 60);
  const mm = runningMinutes % 60;

  const punch = async () => {
    if (punching) return;
    setPunching(true);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    try {
      await apiFetch("/timeclock/punch", { method: "POST", body: JSON.stringify({}) });
      await load();
    } finally {
      setPunching(false);
    }
  };

  const tiles: { label: string; icon: keyof typeof Feather.glyphMap; route?: string }[] = [
    { label: "My Schedule", icon: "calendar", route: "/module/schedule" },
    { label: "My Pay Stubs", icon: "credit-card", route: "/module/payroll" },
    { label: "My Tasks", icon: "check-square", route: "/module/tickets" },
    { label: "Training", icon: "book-open", route: "/module/training" },
    { label: "Messages", icon: "message-circle", route: "/module/chat" },
    { label: "Time Sheet", icon: "clock", route: "/module/schedule" },
  ];
  return (
    <>
      <View
        style={[
          styles.clockCard,
          { borderColor: isClockedIn ? theme.colors.success : theme.colors.borderStrong },
        ]}
        testID="employee-clock-card"
      >
        <View style={{ flex: 1 }}>
          <Text style={[styles.clockLabel, { color: isClockedIn ? theme.colors.success : theme.colors.brand }]}>
            {isClockedIn ? "ON THE CLOCK" : "NOT CLOCKED IN"}
          </Text>
          <Text style={styles.clockTime}>
            {String(hh).padStart(2, "0")}:{String(mm).padStart(2, "0")}
          </Text>
          <Text style={styles.clockMeta}>
            {isClockedIn ? "Live · today's hours" : "Today's total · last punch closed"}
          </Text>
        </View>
        <Pressable
          testID={isClockedIn ? "employee-clock-out" : "employee-clock-in"}
          disabled={punching}
          onPress={punch}
          style={[styles.clockBtn, isClockedIn && { backgroundColor: theme.colors.error }]}
        >
          {punching ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Feather name={isClockedIn ? "square" : "play"} size={18} color="#fff" />
              <Text style={styles.clockBtnTxt}>{isClockedIn ? "CLOCK OUT" : "CLOCK IN"}</Text>
            </>
          )}
        </Pressable>
      </View>
      <Text style={styles.sectionLabel}>QUICK ACTIONS</Text>
      <View style={styles.grid}>
        {tiles.map((t) => (
          <Pressable
            key={t.label}
            testID={`emp-tile-${t.label}`}
            onPress={() => t.route && router.push(t.route as never)}
            style={styles.empTile}
          >
            <Feather name={t.icon} size={20} color={theme.colors.onSurface} />
            <Text style={styles.empTileLabel}>{t.label}</Text>
          </Pressable>
        ))}
      </View>
    </>
  );
}

function CustomerSections() {
  const router = useRouter();
  const tiles: { label: string; icon: keyof typeof Feather.glyphMap; route?: string; sub?: string }[] = [
    { label: "My Orders", icon: "shopping-bag", route: "/customer/orders", sub: "Recent purchases" },
    { label: "Appointments", icon: "calendar", route: "/customer/appointments", sub: "Upcoming visits" },
    { label: "Invoices & Payments", icon: "credit-card", route: "/customer/invoices", sub: "Paid & due" },
    { label: "Support Tickets", icon: "life-buoy", sub: "0 open" },
    { label: "Documents", icon: "folder", sub: "Contracts" },
    { label: "Loyalty Rewards", icon: "award", sub: "1,240 pts" },
  ];
  return (
    <>
      <View style={styles.custBanner} testID="customer-banner">
        <Feather name="gift" size={20} color={theme.colors.brand} />
        <View style={{ flex: 1 }}>
          <Text style={styles.custBannerTitle}>You have 1,240 loyalty points</Text>
          <Text style={styles.custBannerSub}>Redeem on your next invoice — saves $24.80</Text>
        </View>
      </View>
      <Text style={styles.sectionLabel}>YOUR ACCOUNT</Text>
      <View style={styles.grid}>
        {tiles.map((t) => (
          <Pressable
            key={t.label}
            testID={`cust-tile-${t.label}`}
            onPress={() => t.route && router.push(t.route as never)}
            style={styles.custTile}
          >
            <Feather name={t.icon} size={18} color={theme.colors.brand} />
            <Text style={styles.custTileLabel}>{t.label}</Text>
            <Text style={styles.custTileSub}>{t.sub}</Text>
          </Pressable>
        ))}
      </View>
      <Pressable
        testID="customer-marketplace-cta"
        style={styles.marketplaceCta}
        onPress={() => router.push("/customer/marketplace" as never)}
      >
        <View style={styles.marketplaceIcon}>
          <Feather name="grid" size={20} color={theme.colors.brand} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.marketplaceTitle}>Discover other Aidou businesses</Text>
          <Text style={styles.marketplaceSub}>Hire services across the entire network · 1 identity</Text>
        </View>
        <Feather name="arrow-right" size={18} color={theme.colors.brand} />
      </Pressable>
      <Pressable
        testID="customer-chat-support"
        style={styles.supportBtn}
        onPress={() => router.push("/(tabs)/ai")}
      >
        <Feather name="message-circle" size={16} color="#fff" />
        <Text style={styles.supportBtnTxt}>Chat with support</Text>
      </Pressable>
    </>
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
  briefRefresh: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
  },
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
  roleStrip: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: 10,
    marginBottom: theme.spacing.md,
  },
  roleStripLabel: { color: theme.colors.onSurface, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  roleStripBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.brand,
  },
  roleStripBtnTxt: { color: theme.colors.brand, fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  clockCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  clockLabel: { color: theme.colors.brand, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  clockTime: { color: theme.colors.onSurface, fontSize: 30, fontWeight: "800", letterSpacing: -1, marginTop: 4 },
  clockMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 4 },
  clockBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: theme.colors.brand,
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderRadius: theme.radius.md,
  },
  clockBtnTxt: { color: "#fff", fontWeight: "800", letterSpacing: 1 },
  empTile: {
    width: "48.5%",
    aspectRatio: 1.4,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    justifyContent: "space-between",
  },
  empTileLabel: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  custBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.brandTertiary,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.md,
  },
  custBannerTitle: { color: theme.colors.brand, fontSize: 14, fontWeight: "800" },
  custBannerSub: { color: theme.colors.onBrandTertiary, fontSize: 12, marginTop: 2 },
  custTile: {
    width: "48.5%",
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    gap: 8,
  },
  custTileLabel: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  custTileSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11 },
  supportBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: theme.colors.brand,
    padding: 14,
    borderRadius: theme.radius.lg,
    marginTop: theme.spacing.lg,
  },
  supportBtnTxt: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
  marketplaceCta: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    marginTop: theme.spacing.lg,
  },
  marketplaceIcon: {
    width: 40,
    height: 40,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: theme.colors.brand,
  },
  marketplaceTitle: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800" },
  marketplaceSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
});
