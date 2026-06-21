import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, Pressable, ActivityIndicator, ScrollView, TextInput } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { apiFetch } from "@/src/api/client";
import { theme } from "@/src/theme";

interface Offer {
  eligible: boolean;
  max_advance: number;
  rate_first_1k: number;
  rate_above_1k: number;
  underwriting_signals: {
    pos_revenue_lifetime: number;
    payroll_lifetime: number;
    referral_inflow_lifetime: number;
    projected_payouts_30d: number;
  };
  open_advance: { advance_id: string; amount: number; status: string; total_repayable: number } | null;
  tagline: string;
}

export default function CashAdvance() {
  const router = useRouter();
  const [offer, setOffer] = useState<Offer | null>(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("1000");
  const [requesting, setRequesting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch<Offer>("/cash-advance/offer");
      setOffer(r);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const amt = Math.max(0, parseFloat(amount) || 0);
  const fee = amt <= 1000 ? 0 : (amt - 1000) * 0.045;

  const submit = async () => {
    if (!offer || amt <= 0 || amt > offer.max_advance || requesting) return;
    setRequesting(true);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    try {
      const r = await apiFetch<{ advance: { advance_id: string; amount: number } }>("/cash-advance/request", {
        method: "POST", body: JSON.stringify({ amount: amt }),
      });
      setSuccess(`Approved · $${r.advance.amount.toFixed(2)} in 24h`);
      load();
    } finally {
      setRequesting(false);
    }
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="cash-advance-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backBtn} testID="ca-back">
          <Feather name="chevron-left" size={20} color={theme.colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Aidou Cash Advance</Text>
          <Text style={styles.sub}>Borrow against future referral payouts</Text>
        </View>
      </View>
      {loading || !offer ? (
        <View style={styles.center}><ActivityIndicator color={theme.colors.brand} /></View>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.heroCard}>
            <Text style={styles.heroLabel}>APPROVED · BASED ON YOUR LIVE OPS DATA</Text>
            <Text style={styles.heroAmount}>${offer.max_advance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</Text>
            <Text style={styles.heroSub}>{offer.tagline}</Text>
          </View>

          {offer.open_advance ? (
            <View style={styles.outstanding} testID="ca-outstanding">
              <Feather name="alert-circle" size={16} color={theme.colors.warning} />
              <Text style={styles.outstandingTxt}>
                Outstanding advance · ${offer.open_advance.amount.toFixed(2)} · total repayable ${offer.open_advance.total_repayable.toFixed(2)}
              </Text>
            </View>
          ) : (
            <>
              <Text style={styles.sectionLabel}>HOW MUCH DO YOU NEED?</Text>
              <View style={styles.amountBox}>
                <Text style={styles.dollar}>$</Text>
                <TextInput
                  testID="ca-amount"
                  value={amount}
                  onChangeText={setAmount}
                  keyboardType="numeric"
                  style={styles.amountInput}
                />
              </View>
              <Text style={styles.feeLine}>
                Fee: <Text style={{ color: fee === 0 ? theme.colors.success : theme.colors.onSurface, fontWeight: "800" }}>${fee.toFixed(2)}</Text>
                {fee === 0 ? "  · within free $1k" : `  · 4.5% on amount above $1k`}
              </Text>
              <Pressable
                testID="ca-submit"
                disabled={requesting || amt <= 0 || amt > offer.max_advance}
                onPress={submit}
                style={[styles.cta, (requesting || amt <= 0 || amt > offer.max_advance) && { opacity: 0.5 }]}
              >
                {requesting ? <ActivityIndicator color="#fff" /> : (
                  <>
                    <Feather name="zap" size={16} color="#fff" />
                    <Text style={styles.ctaTxt}>REQUEST ${amt.toFixed(0)}</Text>
                  </>
                )}
              </Pressable>
              {success ? <Text style={styles.success} testID="ca-success">{success}</Text> : null}
            </>
          )}

          <Text style={[styles.sectionLabel, { marginTop: 24 }]}>UNDERWRITING SIGNALS</Text>
          <View style={styles.signalGrid}>
            <Signal label="POS revenue" value={`$${offer.underwriting_signals.pos_revenue_lifetime.toLocaleString()}`} />
            <Signal label="Payroll YTD" value={`$${offer.underwriting_signals.payroll_lifetime.toLocaleString()}`} />
            <Signal label="Referral inflow" value={`$${offer.underwriting_signals.referral_inflow_lifetime.toFixed(2)}`} />
            <Signal label="30d projection" value={`$${offer.underwriting_signals.projected_payouts_30d.toFixed(2)}`} />
          </View>
          <Text style={styles.disclaimer}>MOCKED — banking rails not yet integrated. Once Stripe Treasury / Modern Treasury is wired, funds will land within 24h.</Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function Signal({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.signal}>
      <Text style={styles.signalLabel}>{label.toUpperCase()}</Text>
      <Text style={styles.signalVal}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 },
  backBtn: {
    width: 36, height: 36, borderRadius: 6,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1, borderColor: theme.colors.border,
    alignItems: "center", justifyContent: "center",
  },
  title: { color: theme.colors.onSurface, fontSize: 18, fontWeight: "800" },
  sub: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 2 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  scroll: { padding: 16, paddingBottom: 80 },
  heroCard: {
    backgroundColor: theme.colors.brandTertiary,
    borderWidth: 1, borderColor: theme.colors.brand,
    borderRadius: 12, padding: 20,
  },
  heroLabel: { color: theme.colors.brand, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  heroAmount: { color: theme.colors.onSurface, fontSize: 40, fontWeight: "800", letterSpacing: -1, marginTop: 8 },
  heroSub: { color: theme.colors.onBrandTertiary, fontSize: 12, marginTop: 6, lineHeight: 18 },
  sectionLabel: { color: theme.colors.onSurfaceSecondary, fontSize: 10, fontWeight: "700", letterSpacing: 2, marginTop: 24, marginBottom: 8 },
  amountBox: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1, borderColor: theme.colors.borderStrong,
    borderRadius: 8, paddingHorizontal: 16,
  },
  dollar: { color: theme.colors.brand, fontSize: 24, fontWeight: "800" },
  amountInput: { flex: 1, color: theme.colors.onSurface, fontSize: 28, fontWeight: "800", paddingVertical: 14, marginLeft: 6 },
  feeLine: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 8 },
  cta: {
    marginTop: 16, flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 8, backgroundColor: theme.colors.brand, padding: 16, borderRadius: 8,
  },
  ctaTxt: { color: "#fff", fontWeight: "800", letterSpacing: 1 },
  success: { color: theme.colors.success, fontSize: 12, marginTop: 12, textAlign: "center", fontWeight: "700" },
  outstanding: {
    flexDirection: "row", alignItems: "center", gap: 10, marginTop: 16,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1, borderColor: theme.colors.warning,
    borderRadius: 8, padding: 12,
  },
  outstandingTxt: { color: theme.colors.onSurface, fontSize: 12, flex: 1 },
  signalGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  signal: {
    width: "48.5%", backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 8, padding: 12,
  },
  signalLabel: { color: theme.colors.onSurfaceSecondary, fontSize: 9, letterSpacing: 1.2, fontWeight: "700" },
  signalVal: { color: theme.colors.onSurface, fontSize: 16, fontWeight: "800", marginTop: 4 },
  disclaimer: { color: theme.colors.onSurfaceSecondary, fontSize: 10, fontStyle: "italic", marginTop: 16, lineHeight: 14 },
});
