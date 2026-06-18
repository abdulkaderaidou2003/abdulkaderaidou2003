import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  FlatList,
  Modal,
  TextInput,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Haptics from "expo-haptics";

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
  pos: "Point of Sale",
  payroll: "Payroll & T4",
  fleet: "Fleet GPS",
  inventory: "Inventory",
};

export default function ModuleDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { active } = useCompanies();
  const moduleId = id as string;
  const live = ["hr", "tickets", "schedule", "crm", "pos", "payroll", "fleet", "inventory"].includes(moduleId);

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
      {moduleId === "pos" ? <PosView /> : null}
      {moduleId === "payroll" ? <PayrollView /> : null}
      {moduleId === "fleet" ? <FleetView /> : null}
      {moduleId === "inventory" ? <InventoryView /> : null}
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

// ---------- POS ----------
type Product = {
  product_id: string;
  name: string;
  category: string;
  price: number;
  sku: string;
  stock: number;
};

function PosView() {
  const { active } = useCompanies();
  const [prods, setProds] = useState<Product[]>([]);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [cat, setCat] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [receipt, setReceipt] = useState<null | { sale_id: string; total: number; subtotal: number; hst: number }>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ products: Product[] }>("/pos/products")
      .then((r) => setProds(r.products))
      .finally(() => setLoading(false));
  }, [active?.company_id]);

  const categories = useMemo(
    () => ["all", ...Array.from(new Set(prods.map((p) => p.category)))],
    [prods],
  );
  const visible = cat === "all" ? prods : prods.filter((p) => p.category === cat);

  const cartItems = useMemo(
    () =>
      Object.entries(cart)
        .map(([id, qty]) => {
          const p = prods.find((x) => x.product_id === id);
          return p ? { ...p, qty } : null;
        })
        .filter((v): v is Product & { qty: number } => v !== null),
    [cart, prods],
  );
  const subtotal = cartItems.reduce((a, c) => a + c.price * c.qty, 0);
  const hst = subtotal * 0.13;
  const total = subtotal + hst;

  const inc = (id: string) => {
    Haptics.selectionAsync();
    setCart((c) => ({ ...c, [id]: (c[id] ?? 0) + 1 }));
  };
  const dec = (id: string) =>
    setCart((c) => {
      const q = (c[id] ?? 0) - 1;
      const next = { ...c };
      if (q <= 0) delete next[id];
      else next[id] = q;
      return next;
    });

  const checkout = async () => {
    if (cartItems.length === 0 || paying) return;
    setPaying(true);
    try {
      const body = {
        items: cartItems.map((c) => ({ product_id: c.product_id, qty: c.qty })),
        tender: "card",
      };
      const r = await apiFetch<{ sale: { sale_id: string; total: number; subtotal: number; hst: number } }>(
        "/pos/sales",
        { method: "POST", body: JSON.stringify(body) },
      );
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setReceipt(r.sale);
      setCart({});
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ height: 56 }}
        contentContainerStyle={styles.chipsRow}
      >
        {categories.map((c) => {
          const a = c === cat;
          return (
            <Pressable
              key={c}
              testID={`pos-cat-${c}`}
              onPress={() => setCat(c)}
              style={[styles.chip, a && styles.chipActive]}
            >
              <Text style={[styles.chipTxt, a && { color: theme.colors.brand }]}>
                {c.toUpperCase()}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
      <FlatList
        data={visible}
        keyExtractor={(p) => p.product_id}
        contentContainerStyle={{ padding: theme.spacing.lg, paddingBottom: 220 }}
        ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
        renderItem={({ item }) => {
          const qty = cart[item.product_id] ?? 0;
          return (
            <View style={styles.posRow} testID={`pos-${item.product_id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.posName}>{item.name}</Text>
                <Text style={styles.posMeta}>
                  {item.sku} · stock {item.stock}
                </Text>
              </View>
              <Text style={styles.posPrice}>${item.price.toFixed(2)}</Text>
              {qty > 0 ? (
                <View style={styles.qtyControl}>
                  <Pressable onPress={() => dec(item.product_id)} style={styles.qtyBtn}>
                    <Feather name="minus" size={14} color={theme.colors.onSurface} />
                  </Pressable>
                  <Text style={styles.qtyTxt}>{qty}</Text>
                  <Pressable onPress={() => inc(item.product_id)} style={styles.qtyBtn}>
                    <Feather name="plus" size={14} color={theme.colors.onSurface} />
                  </Pressable>
                </View>
              ) : (
                <Pressable
                  testID={`pos-add-${item.product_id}`}
                  style={styles.posAdd}
                  onPress={() => inc(item.product_id)}
                >
                  <Feather name="plus" size={14} color={theme.colors.brand} />
                </Pressable>
              )}
            </View>
          );
        }}
      />
      {cartItems.length > 0 ? (
        <View style={styles.cartBar}>
          <View style={{ flex: 1 }}>
            <Text style={styles.cartLine}>
              {cartItems.length} items · ${subtotal.toFixed(2)} + ${hst.toFixed(2)} HST
            </Text>
            <Text style={styles.cartTotal}>${total.toFixed(2)}</Text>
          </View>
          <Pressable
            testID="pos-checkout"
            onPress={checkout}
            disabled={paying}
            style={[styles.checkoutBtn, paying && { opacity: 0.6 }]}
          >
            {paying ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Feather name="credit-card" size={16} color="#fff" />
                <Text style={styles.checkoutTxt}>CHARGE</Text>
              </>
            )}
          </Pressable>
        </View>
      ) : null}
      {receipt ? (
        <View style={styles.receipt} testID="pos-receipt">
          <Feather name="check-circle" size={20} color={theme.colors.success} />
          <View style={{ flex: 1 }}>
            <Text style={styles.receiptTxt}>Sale {receipt.sale_id.toUpperCase()} · ${receipt.total.toFixed(2)}</Text>
            <Text style={styles.receiptSub}>Paid by card · HST ${receipt.hst.toFixed(2)}</Text>
          </View>
          <Pressable onPress={() => setReceipt(null)} testID="pos-receipt-close">
            <Feather name="x" size={18} color={theme.colors.onSurfaceSecondary} />
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

// ---------- Payroll ----------
type PayRun = {
  run_id: string;
  period: string;
  pay_date: string;
  headcount: number;
  gross: number;
  tax: number;
  cpp_ei: number;
  net: number;
  status: string;
};

function PayrollView() {
  const { active } = useCompanies();
  const [runs, setRuns] = useState<PayRun[]>([]);
  const [emps, setEmps] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [t4, setT4] = useState<null | {
    employee: Employee;
    tax_year: number;
    boxes: Record<string, number>;
  }>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiFetch<{ runs: PayRun[] }>("/payroll/runs"),
      apiFetch<{ employees: Employee[] }>("/hr/employees"),
    ])
      .then(([a, b]) => {
        setRuns(a.runs);
        setEmps(b.employees);
      })
      .finally(() => setLoading(false));
  }, [active?.company_id]);

  const openT4 = async (e: Employee) => {
    const r = await apiFetch<{ employee: Employee; tax_year: number; boxes: Record<string, number> }>(
      `/payroll/t4/${e.employee_id}`,
    );
    setT4(r);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.list}>
      <Text style={styles.dayLabel}>RECENT PAY RUNS</Text>
      {runs.map((r) => (
        <View key={r.run_id} style={styles.runCard} testID={`run-${r.run_id}`}>
          <View style={styles.ticketHead}>
            <Text style={styles.ticketId}>{r.period}</Text>
            <View
              style={[
                styles.prio,
                {
                  borderColor:
                    r.status === "posted" ? theme.colors.success : theme.colors.warning,
                },
              ]}
            >
              <Text
                style={[
                  styles.prioTxt,
                  {
                    color:
                      r.status === "posted" ? theme.colors.success : theme.colors.warning,
                  },
                ]}
              >
                {r.status.toUpperCase()}
              </Text>
            </View>
          </View>
          <View style={styles.runGrid}>
            <View style={styles.runCol}>
              <Text style={styles.runColLabel}>GROSS</Text>
              <Text style={styles.runColVal}>${r.gross.toLocaleString()}</Text>
            </View>
            <View style={styles.runCol}>
              <Text style={styles.runColLabel}>TAX</Text>
              <Text style={styles.runColVal}>${r.tax.toLocaleString()}</Text>
            </View>
            <View style={styles.runCol}>
              <Text style={styles.runColLabel}>CPP/EI</Text>
              <Text style={styles.runColVal}>${r.cpp_ei.toLocaleString()}</Text>
            </View>
            <View style={styles.runCol}>
              <Text style={styles.runColLabel}>NET</Text>
              <Text style={[styles.runColVal, { color: theme.colors.brand }]}>
                ${r.net.toLocaleString()}
              </Text>
            </View>
          </View>
          <Text style={styles.runFoot}>{r.headcount} employees · paid {r.pay_date}</Text>
        </View>
      ))}

      <Text style={[styles.dayLabel, { marginTop: theme.spacing.xl }]}>
        T4 GENERATION · TAX YEAR 2025
      </Text>
      {emps.slice(0, 8).map((e) => (
        <Pressable
          key={e.employee_id}
          testID={`t4-${e.employee_id}`}
          style={styles.t4Row}
          onPress={() => openT4(e)}
        >
          <View style={styles.avatar}>
            <Text style={styles.avatarTxt}>
              {e.name.split(" ").map((s) => s[0]).join("").slice(0, 2)}
            </Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.listName}>{e.name}</Text>
            <Text style={styles.listMeta}>
              {e.role} · {e.department}
            </Text>
          </View>
          <Feather name="file-text" size={16} color={theme.colors.brand} />
        </Pressable>
      ))}

      <Modal visible={!!t4} transparent animationType="slide" onRequestClose={() => setT4(null)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setT4(null)}>
          <Pressable style={styles.t4Sheet} onPress={(e) => e.stopPropagation()}>
            {t4 ? (
              <>
                <View style={styles.t4Head}>
                  <Text style={styles.t4Year}>T4 · {t4.tax_year}</Text>
                  <Pressable onPress={() => setT4(null)} testID="t4-close">
                    <Feather name="x" size={20} color={theme.colors.onSurface} />
                  </Pressable>
                </View>
                <Text style={styles.t4Name}>{t4.employee.name}</Text>
                <Text style={styles.t4Meta}>
                  {t4.employee.role} · {t4.employee.department}
                </Text>
                <View style={styles.t4Boxes}>
                  {[
                    ["Box 14 — Employment income", "14_employment_income"],
                    ["Box 16 — CPP contributions", "16_cpp_contrib"],
                    ["Box 18 — EI premiums", "18_ei_premium"],
                    ["Box 22 — Income tax deducted", "22_income_tax"],
                  ].map(([label, key]) => (
                    <View key={key} style={styles.t4Box}>
                      <Text style={styles.t4BoxLabel}>{label}</Text>
                      <Text style={styles.t4BoxVal}>
                        ${(t4.boxes[key] ?? 0).toLocaleString()}
                      </Text>
                    </View>
                  ))}
                  <View style={[styles.t4Box, { borderColor: theme.colors.brand }]}>
                    <Text style={[styles.t4BoxLabel, { color: theme.colors.brand }]}>
                      Net deposited YTD
                    </Text>
                    <Text style={[styles.t4BoxVal, { color: theme.colors.brand, fontSize: 22 }]}>
                      ${(t4.boxes.net ?? 0).toLocaleString()}
                    </Text>
                  </View>
                </View>
                <Pressable style={styles.t4Action} testID="t4-download">
                  <Feather name="download" size={14} color="#fff" />
                  <Text style={styles.t4ActionTxt}>Download PDF (CRA-ready)</Text>
                </Pressable>
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </ScrollView>
  );
}

// ---------- Fleet ----------
type Vehicle = {
  vehicle_id: string;
  plate: string;
  model: string;
  driver: string;
  lat: number;
  lng: number;
  status: string;
  fuel_pct: number;
  mileage_km: number;
  next_inspection: string;
  speed_kmh: number;
  heading: number;
};

function FleetView() {
  const { active } = useCompanies();
  const [vehs, setVehs] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Vehicle | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<{ vehicles: Vehicle[] }>("/fleet/vehicles");
      setVehs(r.vehicles);
      setSelected((cur) =>
        cur ? r.vehicles.find((v) => v.vehicle_id === cur.vehicle_id) ?? null : null,
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
    const t = setInterval(load, 6000); // live GPS drift
    return () => clearInterval(t);
  }, [active?.company_id, load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }

  // Compute bounds for mini-map
  const lats = vehs.map((v) => v.lat);
  const lngs = vehs.map((v) => v.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const latSpan = Math.max(0.01, maxLat - minLat);
  const lngSpan = Math.max(0.01, maxLng - minLng);

  return (
    <ScrollView contentContainerStyle={styles.list}>
      <View style={styles.mapBox} testID="fleet-map">
        <View style={styles.mapGrid} />
        {vehs.map((v) => {
          const x = ((v.lng - minLng) / lngSpan) * 0.9 + 0.05;
          const y = 1 - (((v.lat - minLat) / latSpan) * 0.9 + 0.05);
          const c =
            v.status === "active"
              ? theme.colors.brand
              : v.status === "maintenance"
              ? theme.colors.error
              : theme.colors.warning;
          return (
            <Pressable
              key={v.vehicle_id}
              testID={`map-pin-${v.vehicle_id}`}
              onPress={() => setSelected(v)}
              style={[
                styles.mapPin,
                {
                  left: `${x * 100}%`,
                  top: `${y * 100}%`,
                  backgroundColor: c,
                  borderColor: selected?.vehicle_id === v.vehicle_id ? "#fff" : "transparent",
                },
              ]}
            />
          );
        })}
        <View style={styles.mapLegend}>
          <Text style={styles.mapLegendTxt}>LIVE · {vehs.length} VEHICLES</Text>
        </View>
      </View>

      {vehs.map((v) => {
        const ok = v.status === "active";
        return (
          <Pressable
            key={v.vehicle_id}
            testID={`veh-${v.vehicle_id}`}
            onPress={() => setSelected(v)}
            style={[
              styles.vehCard,
              selected?.vehicle_id === v.vehicle_id && { borderColor: theme.colors.brand },
            ]}
          >
            <View style={styles.vehHead}>
              <Text style={styles.vehPlate}>{v.plate}</Text>
              <View
                style={[
                  styles.statusChip,
                  {
                    backgroundColor: ok
                      ? theme.colors.brandSecondary
                      : theme.colors.surfaceTertiary,
                  },
                ]}
              >
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor: ok
                        ? theme.colors.success
                        : v.status === "maintenance"
                        ? theme.colors.error
                        : theme.colors.warning,
                    },
                  ]}
                />
                <Text style={styles.statusChipTxt}>{v.status.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={styles.vehModel}>
              {v.model} · {v.driver}
            </Text>
            <View style={styles.vehMetrics}>
              <View style={styles.vehMetric}>
                <Feather name="navigation" size={11} color={theme.colors.onSurfaceSecondary} />
                <Text style={styles.vehMetricTxt}>{v.speed_kmh} km/h</Text>
              </View>
              <View style={styles.vehMetric}>
                <Feather name="droplet" size={11} color={theme.colors.onSurfaceSecondary} />
                <Text style={styles.vehMetricTxt}>{v.fuel_pct}%</Text>
              </View>
              <View style={styles.vehMetric}>
                <Feather name="map-pin" size={11} color={theme.colors.onSurfaceSecondary} />
                <Text style={styles.vehMetricTxt}>
                  {v.lat.toFixed(4)}, {v.lng.toFixed(4)}
                </Text>
              </View>
            </View>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

// ---------- Inventory ----------
type InvItem = {
  item_id: string;
  name: string;
  category: string;
  location: string;
  stock: number;
  reorder_at: number;
  barcode: string;
};

function InventoryView() {
  const { active } = useCompanies();
  const router = useRouter();
  const [items, setItems] = useState<InvItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scan, setScan] = useState("");
  const [scanResult, setScanResult] = useState<null | { found: boolean; item?: InvItem; product?: Product }>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ items: InvItem[] }>("/inventory/items")
      .then((r) => setItems(r.items))
      .finally(() => setLoading(false));
  }, [active?.company_id]);

  const lookup = async () => {
    if (!scan.trim()) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      const r = await apiFetch<{ found: boolean; item?: InvItem; product?: Product }>(
        `/inventory/lookup?barcode=${encodeURIComponent(scan.trim())}`,
      );
      setScanResult(r);
      if (r.found) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      }
    } catch (e) {
      console.warn(e);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.brand} />
      </View>
    );
  }

  const lowStock = items.filter((i) => i.stock <= i.reorder_at).length;

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.scanBar}>
        <Feather name="maximize" size={16} color={theme.colors.brand} />
        <TextInput
          testID="barcode-input"
          value={scan}
          onChangeText={setScan}
          placeholder="Scan / enter barcode…"
          placeholderTextColor={theme.colors.onSurfaceSecondary}
          style={styles.scanInput}
          onSubmitEditing={lookup}
        />
        <Pressable
          testID="barcode-camera"
          onPress={() => router.push("/scan?returnTo=inventory")}
          style={[styles.scanBtn, { backgroundColor: theme.colors.brandSecondary, marginRight: 6 }]}
        >
          <Feather name="camera" size={14} color={theme.colors.brand} />
        </Pressable>
        <Pressable testID="barcode-lookup" onPress={lookup} style={styles.scanBtn}>
          <Text style={styles.scanBtnTxt}>LOOKUP</Text>
        </Pressable>
      </View>
      {scanResult ? (
        <View
          style={[
            styles.scanResult,
            { borderColor: scanResult.found ? theme.colors.success : theme.colors.error },
          ]}
          testID="scan-result"
        >
          {scanResult.found ? (
            <>
              <Feather name="check-circle" size={18} color={theme.colors.success} />
              <View style={{ flex: 1 }}>
                <Text style={styles.scanResultTitle}>
                  {scanResult.item?.name ?? scanResult.product?.name}
                </Text>
                <Text style={styles.scanResultMeta}>
                  {scanResult.item
                    ? `${scanResult.item.location} · stock ${scanResult.item.stock}`
                    : `POS · $${scanResult.product?.price?.toFixed(2)}`}
                </Text>
              </View>
            </>
          ) : (
            <>
              <Feather name="x-circle" size={18} color={theme.colors.error} />
              <Text style={styles.scanResultTitle}>Not found in catalog or inventory</Text>
            </>
          )}
          <Pressable onPress={() => setScanResult(null)} testID="scan-clear">
            <Feather name="x" size={16} color={theme.colors.onSurfaceSecondary} />
          </Pressable>
        </View>
      ) : null}
      <Text style={[styles.dayLabel, { paddingHorizontal: theme.spacing.lg, marginTop: theme.spacing.md }]}>
        {items.length} ITEMS · {lowStock} BELOW REORDER
      </Text>
      <FlatList
        data={items}
        keyExtractor={(i) => i.item_id}
        contentContainerStyle={{ paddingHorizontal: theme.spacing.lg, paddingBottom: 80 }}
        ItemSeparatorComponent={() => <View style={{ height: theme.spacing.sm }} />}
        renderItem={({ item }) => {
          const low = item.stock <= item.reorder_at;
          return (
            <View style={styles.invRow} testID={`inv-${item.item_id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.posName}>{item.name}</Text>
                <Text style={styles.posMeta}>
                  {item.category} · {item.location} · {item.barcode}
                </Text>
              </View>
              <View style={[styles.invStock, low && { borderColor: theme.colors.error }]}>
                <Text
                  style={[styles.invStockTxt, low && { color: theme.colors.error }]}
                >
                  {item.stock}
                </Text>
                <Text style={styles.invReorderTxt}>/{item.reorder_at}</Text>
              </View>
            </View>
          );
        }}
      />
    </View>
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

  // POS
  posRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  posName: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  posMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  posPrice: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800", marginRight: 4 },
  posAdd: {
    width: 32,
    height: 32,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    backgroundColor: theme.colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyControl: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.md,
    paddingHorizontal: 4,
  },
  qtyBtn: { width: 26, height: 26, alignItems: "center", justifyContent: "center" },
  qtyTxt: { color: theme.colors.onSurface, minWidth: 18, textAlign: "center", fontWeight: "800" },
  cartBar: {
    position: "absolute",
    left: theme.spacing.lg,
    right: theme.spacing.lg,
    bottom: theme.spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  cartLine: { color: theme.colors.onSurfaceSecondary, fontSize: 11, letterSpacing: 0.4 },
  cartTotal: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800", letterSpacing: -0.5 },
  checkoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: theme.colors.brand,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: theme.radius.md,
  },
  checkoutTxt: { color: "#fff", fontWeight: "800", letterSpacing: 1 },
  receipt: {
    position: "absolute",
    left: theme.spacing.lg,
    right: theme.spacing.lg,
    bottom: theme.spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.success,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  receiptTxt: { color: theme.colors.onSurface, fontWeight: "700", fontSize: 13 },
  receiptSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },

  // Payroll
  runCard: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  runGrid: { flexDirection: "row", marginTop: theme.spacing.md, gap: theme.spacing.sm },
  runCol: { flex: 1 },
  runColLabel: { color: theme.colors.onSurfaceSecondary, fontSize: 9, letterSpacing: 1, fontWeight: "700" },
  runColVal: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800", marginTop: 4 },
  runFoot: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: theme.spacing.sm },
  t4Row: {
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
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.75)",
    justifyContent: "flex-end",
  },
  t4Sheet: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderTopLeftRadius: theme.radius.lg,
    borderTopRightRadius: theme.radius.lg,
    padding: theme.spacing.xl,
    borderTopWidth: 1,
    borderColor: theme.colors.border,
  },
  t4Head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  t4Year: { color: theme.colors.brand, fontSize: 12, fontWeight: "800", letterSpacing: 2 },
  t4Name: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800", marginTop: theme.spacing.md },
  t4Meta: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },
  t4Boxes: { marginTop: theme.spacing.lg, gap: theme.spacing.sm },
  t4Box: {
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
  },
  t4BoxLabel: { color: theme.colors.onSurfaceSecondary, fontSize: 11, fontWeight: "600" },
  t4BoxVal: { color: theme.colors.onSurface, fontSize: 16, fontWeight: "800", marginTop: 4 },
  t4Action: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: theme.colors.brand,
    padding: 14,
    borderRadius: theme.radius.md,
    marginTop: theme.spacing.lg,
  },
  t4ActionTxt: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },

  // Fleet
  mapBox: {
    height: 220,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    marginBottom: theme.spacing.md,
    position: "relative",
    overflow: "hidden",
  },
  mapGrid: {
    position: "absolute",
    inset: 0,
    backgroundColor: theme.colors.surfaceTertiary,
    borderRadius: theme.radius.lg,
  },
  mapPin: {
    position: "absolute",
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
    marginLeft: -7,
    marginTop: -7,
  },
  mapLegend: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.sm,
  },
  mapLegendTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 1.5 },
  vehCard: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  vehHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  vehPlate: { color: theme.colors.onSurface, fontSize: 15, fontWeight: "800", letterSpacing: 0.5 },
  vehModel: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 4 },
  vehMetrics: { flexDirection: "row", gap: theme.spacing.md, marginTop: theme.spacing.sm, flexWrap: "wrap" },
  vehMetric: { flexDirection: "row", alignItems: "center", gap: 4 },
  vehMetricTxt: { color: theme.colors.onSurfaceTertiary, fontSize: 11 },

  // Inventory
  scanBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    marginHorizontal: theme.spacing.lg,
    paddingHorizontal: theme.spacing.md,
  },
  scanInput: { flex: 1, color: theme.colors.onSurface, paddingVertical: 12, fontSize: 14 },
  scanBtn: {
    backgroundColor: theme.colors.brand,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: theme.radius.md,
  },
  scanBtnTxt: { color: "#fff", fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  scanResult: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    marginHorizontal: theme.spacing.lg,
    marginTop: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
  },
  scanResultTitle: { color: theme.colors.onSurface, fontSize: 13, fontWeight: "700" },
  scanResultMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  invRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
  },
  invStock: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    flexDirection: "row",
    alignItems: "baseline",
  },
  invStockTxt: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800" },
  invReorderTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginLeft: 2 },
});
