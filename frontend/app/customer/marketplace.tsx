import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator, Pressable, StyleSheet } from "react-native";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { apiFetch } from "@/src/api/client";
import { CustomerHeader, customerStyles as s, SafeAreaView } from "@/src/components/CustomerScreen";
import { theme } from "@/src/theme";

interface Business {
  company_id: string;
  name: string;
  industry: string;
  logo_color: string;
  rating: number;
  specialty: string;
  min_price: string;
  is_member?: boolean;
}

export default function CustomerMarketplace() {
  const [items, setItems] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [referring, setReferring] = useState<string | null>(null);
  const [referred, setReferred] = useState<Set<string>>(new Set());

  useEffect(() => {
    apiFetch<{ businesses: Business[] }>("/marketplace/businesses")
      .then((r) => setItems(r.businesses))
      .finally(() => setLoading(false));
  }, []);

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
                    <Text style={s.rowName}>{item.name}</Text>
                    <Text style={s.rowMeta}>
                      {item.specialty} · {item.industry}
                    </Text>
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
});
