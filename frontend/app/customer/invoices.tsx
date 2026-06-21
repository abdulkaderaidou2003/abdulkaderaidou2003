import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator } from "react-native";
import { Feather } from "@expo/vector-icons";
import { apiFetch } from "@/src/api/client";
import { CustomerHeader, customerStyles as s, SafeAreaView } from "@/src/components/CustomerScreen";
import { theme } from "@/src/theme";

interface Invoice {
  invoice_id: string;
  company_name: string;
  amount: number;
  status: "paid" | "due" | "overdue";
  issued_at: string;
  items_count: number;
}

export default function CustomerInvoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ invoices: Invoice[] }>("/customer/invoices")
      .then((r) => setInvoices(r.invoices))
      .finally(() => setLoading(false));
  }, []);

  const due = invoices.filter((i) => i.status !== "paid").reduce((a, c) => a + c.amount, 0);
  const overdue = invoices.filter((i) => i.status === "overdue").length;

  return (
    <SafeAreaView style={s.root} edges={["top"]} testID="customer-invoices-screen">
      <CustomerHeader title="Invoices" sub={`$${due.toFixed(2)} due · ${overdue} overdue`} />
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : invoices.length === 0 ? (
        <View style={s.empty}>
          <Feather name="credit-card" size={28} color={theme.colors.onSurfaceSecondary} />
          <Text style={s.emptyTitle}>No invoices</Text>
          <Text style={s.emptyDesc}>Your billing history with Aidou businesses will show up here.</Text>
        </View>
      ) : (
        <FlatList
          data={invoices}
          keyExtractor={(i) => i.invoice_id}
          contentContainerStyle={s.list}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          renderItem={({ item }) => (
            <View
              style={[
                s.card,
                {
                  borderLeftWidth: 3,
                  borderLeftColor:
                    item.status === "paid"
                      ? theme.colors.success
                      : item.status === "overdue"
                      ? theme.colors.error
                      : theme.colors.warning,
                },
              ]}
              testID={`inv-${item.invoice_id}`}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Text style={s.rowName}>{item.company_name}</Text>
                <Text style={s.amount}>${item.amount.toFixed(2)}</Text>
              </View>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                <Text style={s.rowMeta}>
                  {item.items_count} items · {new Date(item.issued_at).toLocaleDateString()}
                </Text>
                <Text
                  style={
                    item.status === "paid" ? s.statusPaid : item.status === "overdue" ? s.statusOverdue : s.statusDue
                  }
                >
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}
