import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator } from "react-native";
import { Feather } from "@expo/vector-icons";
import { apiFetch } from "@/src/api/client";
import { CustomerHeader, customerStyles as s, SafeAreaView } from "@/src/components/CustomerScreen";
import { theme } from "@/src/theme";

interface Order {
  sale_id: string;
  company_name: string;
  total: number;
  hst: number;
  items: { name: string; qty: number; price: number }[];
  created_at: string;
}

export default function CustomerOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ orders: Order[] }>("/customer/orders")
      .then((r) => setOrders(r.orders))
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={s.root} edges={["top"]} testID="customer-orders-screen">
      <CustomerHeader title="My Orders" sub={`${orders.length} purchases across Aidou businesses`} />
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : orders.length === 0 ? (
        <View style={s.empty}>
          <Feather name="shopping-bag" size={28} color={theme.colors.onSurfaceSecondary} />
          <Text style={s.emptyTitle}>No orders yet</Text>
          <Text style={s.emptyDesc}>Your purchases across all Aidou-powered businesses will show up here.</Text>
        </View>
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(o) => o.sale_id}
          contentContainerStyle={s.list}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          renderItem={({ item }) => (
            <View style={s.card} testID={`order-${item.sale_id}`}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Text style={s.rowName}>{item.company_name}</Text>
                <Text style={s.amount}>${item.total.toFixed(2)}</Text>
              </View>
              <Text style={s.rowMeta}>
                {item.items.length} items · HST ${item.hst.toFixed(2)} · {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}
