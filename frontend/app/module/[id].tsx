import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  FlatList,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { apiFetch } from "@/src/api/client";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { theme } from "@/src/theme";

type Employee = {
  employee_id: string;
  name: string;
  role: string;
  department: string;
  status: string;
};
type Ticket = {
  ticket_id: string;
  title: string;
  priority: string;
  status: string;
  assignee: string;
  sla_hours: number;
};
type Shift = {
  shift_id: string;
  employee: string;
  department: string;
  start: string;
  end: string;
  date: string;
};
type Customer = {
  customer_id: string;
  name: string;
  contact: string;
  stage: string;
  value: number;
};

const MODULE_NAMES: Record<string, string> = {
  hr: "Human Resources",
  tickets: "Job Tickets",
  schedule: "Workforce Schedule",
  crm: "CRM",
};

export default function ModuleDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { active } = useCompanies();
  const moduleId = id as string;
  const live = ["hr", "tickets", "schedule", "crm"].includes(moduleId);

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID={`module-${moduleId}`}>
      <View style={styles.header}>
        <Pressable testID="back-btn" onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="chevron-left" size={20} color={theme.colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>
            {MODULE_NAMES[moduleId] ?? moduleId.toUpperCase()}
          </Text>
          <Text style={styles.sub}>{active?.name ?? "—"}</Text>
        </View>
        <View style={[styles.statusPill, { borderColor: live ? theme.colors.brand : theme.colors.border }]}>
          <Text style={[styles.statusPillTxt, { color: live ? theme.colors.brand : theme.colors.onSurfaceSecondary }]}>
            {live ? "LIVE" : "PREVIEW"}
          </Text>
        </View>
      </View>

      {moduleId === "hr" ? <HRView /> : null}
      {moduleId === "tickets" ? <TicketsView /> : null}
      {moduleId === "schedule" ? <ScheduleView /> : null}
      {moduleId === "crm" ? <CrmView /> : null}
      {!live ? <ComingSoon name={MODULE_NAMES[moduleId] ?? moduleId} /> : null}
    </SafeAreaView>
  );
}

function ComingSoon({ name }: { name: string }) {
  return (
    <View style={styles.coming}>
      <Feather name="layers" size={28} color={theme.colors.brand} />
      <Text style={styles.comingTitle}>{name} module</Text>
      <Text style={styles.comingTxt}>
        Add this module to your subscription to unlock full functionality. Your onboarding team will
        configure data, roles and integrations within 48 hours.
      </Text>
      <View style={styles.comingPills}>
        {["Records", "Workflows", "Reports", "AI", "API"].map((p) => (
          <View key={p} style={styles.comingPill}>
            <Text style={styles.comingPillTxt}>{p}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function HRView() {
  const { active } = useCompanies();
  const [emps, setEmps] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [dept, setDept] = useState<string>("All");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ employees: Employee[] }>("/hr/employees");
      setEmps(r.employees);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [active?.company_id, load]);

  const depts = useMemo(
    () => ["All", ...Array.from(new Set(emps.map((e) => e.department))).sort()],
    [emps],
  );
  const visible = dept === "All" ? emps : emps.filter((e) => e.department === dept);

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ height: 56 }}
        contentContainerStyle={styles.chipsRow}
      >
        {depts.map((d) => {
          const a = d === dept;
          return (
            <Pressable
              key={d}
              testID={`dept-chip-${d}`}
              onPress={() => setDept(d)}
              style={[styles.chip, a && styles.chipActive]}
            >
              <Text style={[styles.chipTxt, a && { color: theme.colors.brand }]}>{d}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <FlatList
          data={visible}
          keyExtractor={(e) => e.employee_id}
          contentContainerStyle={styles.list}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: theme.colors.divider }} />}
          renderItem={({ item }) => {
            const initials = item.name.split(" ").map((s) => s[0]).join("").slice(0, 2);
            const ok = item.status === "active";
            return (
              <View style={styles.listRow} testID={`emp-${item.employee_id}`}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarTxt}>{initials}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.listName}>{item.name}</Text>
                  <Text style={styles.listMeta}>
                    {item.role} · {item.department}
                  </Text>
                </View>
                <View
                  style={[
                    styles.statusChip,
                    { backgroundColor: ok ? theme.colors.brandSecondary : theme.colors.surfaceTertiary },
                  ]}
                >
                  <View
                    style={[
                      styles.statusDot,
                      { backgroundColor: ok ? theme.colors.success : theme.colors.warning },
                    ]}
                  />
                  <Text style={styles.statusChipTxt}>{item.status.replace("_", " ").toUpperCase()}</Text>
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

function TicketsView() {
  const { active } = useCompanies();
  const [tks, setTks] = useState<Ticket[]>([]);
  const [status, setStatus] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ tickets: Ticket[] }>(`/tickets?status=${status}`);
      setTks(r.tickets);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [active?.company_id, load]);

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.segment}>
        {["all", "open", "in_progress", "closed"].map((s) => {
          const a = s === status;
          return (
            <Pressable
              key={s}
              testID={`tk-seg-${s}`}
              onPress={() => setStatus(s)}
              style={[styles.segItem, a && styles.segItemActive]}
            >
              <Text style={[styles.segTxt, a && { color: theme.colors.onSurface }]}>
                {s.replace("_", " ").toUpperCase()}
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
          data={tks}
          keyExtractor={(t) => t.ticket_id}
          contentContainerStyle={styles.list}
          ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
          renderItem={({ item }) => {
            const pColor =
              item.priority === "high"
                ? theme.colors.brand
                : item.priority === "medium"
                ? theme.colors.warning
                : theme.colors.success;
            return (
              <View style={styles.ticketCard} testID={`tk-${item.ticket_id}`}>
                <View style={styles.ticketHead}>
                  <Text style={styles.ticketId}>{item.ticket_id.toUpperCase()}</Text>
                  <View style={[styles.prio, { borderColor: pColor }]}>
                    <Text style={[styles.prioTxt, { color: pColor }]}>
                      {item.priority.toUpperCase()}
                    </Text>
                  </View>
                </View>
                <Text style={styles.ticketTitle}>{item.title}</Text>
                <View style={styles.ticketFoot}>
                  <Text style={styles.ticketMeta}>
                    {item.assignee} · {item.status.replace("_", " ").toUpperCase()}
                  </Text>
                  <Text style={[styles.sla, { color: pColor }]}>SLA {item.sla_hours}h</Text>
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

function ScheduleView() {
  const { active } = useCompanies();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ shifts: Shift[] }>("/schedule")
      .then((r) => setShifts(r.shifts))
      .finally(() => setLoading(false));
  }, [active?.company_id]);

  const grouped = useMemo(() => {
    const map = new Map<string, Shift[]>();
    shifts.forEach((s) => {
      if (!map.has(s.date)) map.set(s.date, []);
      map.get(s.date)!.push(s);
    });
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [shifts]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.list}>
      {grouped.map(([date, shs]) => (
        <View key={date} style={{ marginBottom: theme.spacing.lg }}>
          <Text style={styles.dayLabel}>{date}</Text>
          {shs.map((s) => (
            <View key={s.shift_id} style={styles.shift} testID={`shift-${s.shift_id}`}>
              <View style={styles.shiftTime}>
                <Text style={styles.shiftTimeTxt}>{s.start}</Text>
                <View style={styles.shiftBar} />
                <Text style={styles.shiftTimeTxt}>{s.end}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.shiftName}>{s.employee}</Text>
                <Text style={styles.shiftDept}>{s.department}</Text>
              </View>
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

function CrmView() {
  const { active } = useCompanies();
  const [cs, setCs] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ customers: Customer[] }>("/crm/customers")
      .then((r) => setCs(r.customers))
      .finally(() => setLoading(false));
  }, [active?.company_id]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }
  const total = cs.reduce((acc, c) => acc + (c.value || 0), 0);
  return (
    <FlatList
      data={cs}
      keyExtractor={(c) => c.customer_id}
      contentContainerStyle={styles.list}
      ListHeaderComponent={
        <View style={styles.crmHead}>
          <Text style={styles.crmHeadLabel}>PIPELINE VALUE</Text>
          <Text style={styles.crmHeadVal}>${(total / 1000).toFixed(1)}K</Text>
          <Text style={styles.crmHeadSub}>{cs.length} accounts · {active?.name}</Text>
        </View>
      }
      ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
      renderItem={({ item }) => (
        <View style={styles.custCard} testID={`cust-${item.customer_id}`}>
          <View>
            <Text style={styles.custName}>{item.name}</Text>
            <Text style={styles.custMeta}>
              {item.contact} · {item.stage.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.custVal}>${(item.value / 1000).toFixed(0)}K</Text>
        </View>
      )}
    />
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
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
  },
  statusPillTxt: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  coming: { flex: 1, padding: theme.spacing.xl, alignItems: "center", justifyContent: "center", gap: theme.spacing.md },
  comingTitle: { color: theme.colors.onSurface, fontSize: 20, fontWeight: "800", textAlign: "center" },
  comingTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 13, textAlign: "center", lineHeight: 19, maxWidth: 320 },
  comingPills: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: theme.spacing.lg, justifyContent: "center" },
  comingPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceSecondary,
  },
  comingPillTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 11, fontWeight: "600" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  chipsRow: { paddingHorizontal: theme.spacing.lg, gap: theme.spacing.sm, alignItems: "center" },
  chip: {
    flexShrink: 0,
    paddingHorizontal: theme.spacing.md,
    height: 36,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: { borderColor: theme.colors.brand, backgroundColor: theme.colors.brandTertiary },
  chipTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700", letterSpacing: 0.3 },
  list: { padding: theme.spacing.lg, paddingBottom: 90 },
  listRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    paddingVertical: theme.spacing.md,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: theme.colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarTxt: { color: theme.colors.brand, fontSize: 12, fontWeight: "800" },
  listName: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  listMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  statusChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusChipTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  segment: {
    flexDirection: "row",
    marginHorizontal: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    backgroundColor: theme.colors.surfaceSecondary,
    borderRadius: theme.radius.md,
    padding: 3,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  segItem: { flex: 1, paddingVertical: 8, alignItems: "center", borderRadius: theme.radius.sm },
  segItemActive: { backgroundColor: theme.colors.surfaceTertiary },
  segTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 10, fontWeight: "800", letterSpacing: 0.4 },
  ticketCard: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  ticketHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  ticketId: { color: theme.colors.onSurfaceSecondary, fontSize: 10, fontWeight: "700", letterSpacing: 1 },
  prio: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: theme.radius.sm, borderWidth: 1 },
  prioTxt: { fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  ticketTitle: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "700", marginTop: 8 },
  ticketFoot: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8 },
  ticketMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11 },
  sla: { fontSize: 11, fontWeight: "800", letterSpacing: 0.5 },
  dayLabel: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 10,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: theme.spacing.sm,
  },
  shift: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: 6,
  },
  shiftTime: { alignItems: "center", width: 64 },
  shiftTimeTxt: { color: theme.colors.onSurface, fontSize: 12, fontWeight: "800" },
  shiftBar: { width: 2, height: 14, backgroundColor: theme.colors.brand, marginVertical: 2 },
  shiftName: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  shiftDept: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  crmHead: {
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  crmHeadLabel: { color: theme.colors.brand, fontSize: 10, letterSpacing: 2, fontWeight: "800" },
  crmHeadVal: { color: theme.colors.onSurface, fontSize: 36, fontWeight: "800", letterSpacing: -1, marginTop: 6 },
  crmHeadSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  custCard: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  custName: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  custMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  custVal: { color: theme.colors.brand, fontSize: 16, fontWeight: "800" },
});
