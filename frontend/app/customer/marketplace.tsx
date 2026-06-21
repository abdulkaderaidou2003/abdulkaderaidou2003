import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator, Pressable, StyleSheet } from "react-native";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { apiFetch } from "@/src/api/client";
import { CustomerHeader, customerStyles as s, SafeAreaView } from "@/src/components/CustomerScreen";
import { theme } from "@/src/theme";

interface TrustBadge {
  company_id: string;
  company_name: string;
  industry: string;
  score: number;
  band: string;
  verified: boolean;
  issued_at: string;
  signature: string;
}

interface Business {
  company_id: string;
  name: string;
  industry: string;
  logo_color: string;
  rating: number;
  specialty: string;
  min_price: string;
  is_member?: boolean;
  recommended?: boolean;
  match_reason?: string;
  score?: number;
  trust_badge?: TrustBadge;
}

export default function CustomerMarketplace() {
  const [items, setItems] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [referring, setReferring] = useState<string | null>(null);
  const [referred, setReferred] = useState<Set<string>>(new Set());
  const [showAll, setShowAll] = useState(false);
  const [hiddenCount, setHiddenCount] = useState(0);

  useEffect(() => {
    setLoading(true);
    const qs = showAll ? "?include_unverified=true" : "";
    apiFetch<{ businesses: Business[]; hidden_count: number }>(`/marketplace/businesses${qs}`)
      .then((r) => {
        setItems(r.businesses);
        setHiddenCount(r.hidden_count || 0);
      })
      .finally(() => setLoading(false));
  }, [showAll]);

  const refer = async (b: Business) => {
    setReferring(b.company_id);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    try {
      await apiFetch("/marketplace/referrals", {
        method: "POST",
        body: JSON.stringify({ target_company_id: b.company_id, note: "Customer-initiated booking" }),
      });
      setReferred((prev) => new Set(prev).add(b.company_id));
    } finally {
      setReferring(null);
    }
  };

  return (
    <SafeAreaView style={s.root} edges={["top"]} testID="marketplace-screen">
      <CustomerHeader title="Aidou Marketplace" sub="Hire any Aidou business · 1 identity · 5% revenue share" />
      <View style={styles.toggleRow}>
        <Pressable
          testID="toggle-show-all"
          onPress={() => setShowAll((s) => !s)}
          style={[styles.toggleBtn, showAll && styles.toggleBtnActive]}
        >
          <Feather name={showAll ? "check-square" : "square"} size={13} color={showAll ? theme.colors.brand : theme.colors.onSurfaceSecondary} />
          <Text style={[styles.toggleTxt, showAll && { color: theme.colors.brand }]}>
            Show unverified
          </Text>
        </Pressable>
        {!showAll && hiddenCount > 0 ? (
          <Text style={styles.hiddenNote}>{hiddenCount} hidden · score &lt; 600</Text>
        ) : null}
      </View>
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(b) => b.company_id}
          contentContainerStyle={s.list}
          ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
          renderItem={({ item }) => {
            const done = referred.has(item.company_id);
            const busy = referring === item.company_id;
            return (
              <View
                style={[
                  s.card,
                  { borderLeftWidth: 3, borderLeftColor: item.logo_color },
                ]}
                testID={`mp-${item.company_id}`}
              >
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                      <Text style={s.rowName}>{item.name}</Text>
                      {item.recommended ? (
                        <View style={styles.recBadge}>
                          <Feather name="zap" size={10} color={theme.colors.brand} />
                          <Text style={styles.recBadgeTxt}>RECOMMENDED</Text>
                        </View>
                      ) : null}
                    </View>
                    <Text style={s.rowMeta}>
                      {item.specialty} · {item.industry}
                    </Text>
                    {item.trust_badge ? (
                      <View
                        style={[
                          styles.trustBadge,
                          item.trust_badge.verified ? styles.trustBadgeVerified : styles.trustBadgeUnverified,
                        ]}
                        testID={`trust-${item.company_id}`}
                      >
                        <Feather
                          name={item.trust_badge.verified ? "shield" : "alert-circle"}
                          size={10}
                          color={item.trust_badge.verified ? theme.colors.success : theme.colors.warning}
                        />
                        <Text
                          style={[
                            styles.trustBadgeTxt,
                            { color: item.trust_badge.verified ? theme.colors.success : theme.colors.warning },
                          ]}
                        >
                          {item.trust_badge.verified ? "VERIFIED" : "BUILDING"} ·{" "}
                          {item.trust_badge.score} TRUST
                        </Text>
                      </View>
                    ) : null}
                    {item.match_reason ? (
                      <Text style={styles.matchReason}>{item.match_reason}</Text>
                    ) : null}
                  </View>
                  <View style={styles.rating}>
                    <Feather name="star" size={11} color={theme.colors.warning} />
                    <Text style={styles.ratingTxt}>{item.rating.toFixed(1)}</Text>
                  </View>
                </View>
                <View style={styles.footer}>
                  <Text style={styles.price}>{item.min_price}</Text>
                  <Pressable
                    testID={`refer-${item.company_id}`}
                    disabled={busy || done}
                    onPress={() => refer(item)}
                    style={[
                      styles.cta,
                      done && { backgroundColor: theme.colors.success },
                      busy && { opacity: 0.6 },
                    ]}
                  >
                    {busy ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <>
                        <Feather name={done ? "check" : "arrow-up-right"} size={13} color="#fff" />
                        <Text style={styles.ctaTxt}>{done ? "BOOKED" : item.is_member ? "OPEN" : "BOOK"}</Text>
                      </>
                    )}
                  </Pressable>
                </View>
              </View>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  rating: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceTertiary,
  },
  ratingTxt: { color: theme.colors.onSurface, fontSize: 11, fontWeight: "800" },
  footer: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 10 },
  price: { color: theme.colors.brand, fontSize: 13, fontWeight: "800" },
  cta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: theme.colors.brand,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: theme.radius.md,
  },
  ctaTxt: { color: "#fff", fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  recBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    backgroundColor: theme.colors.brandTertiary,
  },
  recBadgeTxt: { color: theme.colors.brand, fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  matchReason: { color: theme.colors.brand, fontSize: 11, marginTop: 4, fontWeight: "600" },
  trustBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    alignSelf: "flex-start",
    marginTop: 6,
  },
  trustBadgeVerified: {
    borderColor: theme.colors.success,
    backgroundColor: "rgba(16, 185, 129, 0.08)",
  },
  trustBadgeUnverified: {
    borderColor: theme.colors.warning,
    backgroundColor: "rgba(245, 158, 11, 0.06)",
  },
  trustBadgeTxt: { fontSize: 9, fontWeight: "800", letterSpacing: 0.5 },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
  },
  toggleBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  toggleBtnActive: { borderColor: theme.colors.brand, backgroundColor: theme.colors.brandTertiary },
  toggleTxt: { color: theme.colors.onSurfaceSecondary, fontSize: 11, fontWeight: "700", letterSpacing: 0.3 },
  hiddenNote: { color: theme.colors.onSurfaceSecondary, fontSize: 11, fontStyle: "italic" },
});
