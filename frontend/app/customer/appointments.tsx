import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator } from "react-native";
import { Feather } from "@expo/vector-icons";
import { apiFetch } from "@/src/api/client";
import { CustomerHeader, customerStyles as s, SafeAreaView } from "@/src/components/CustomerScreen";
import { theme } from "@/src/theme";

interface Appointment {
  appointment_id: string;
  company_name: string;
  title: string;
  when: string;
  location?: string;
  status: string;
}

export default function CustomerAppointments() {
  const [items, setItems] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ appointments: Appointment[] }>("/customer/appointments")
      .then((r) => setItems(r.appointments))
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={s.root} edges={["top"]} testID="customer-appointments-screen">
      <CustomerHeader title="Appointments" sub={`${items.length} scheduled`} />
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : items.length === 0 ? (
        <View style={s.empty}>
          <Feather name="calendar" size={28} color={theme.colors.onSurfaceSecondary} />
          <Text style={s.emptyTitle}>No upcoming appointments</Text>
          <Text style={s.emptyDesc}>Bookings with Aidou businesses will appear here.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(a) => a.appointment_id}
          contentContainerStyle={s.list}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          renderItem={({ item }) => {
            const when = new Date(item.when);
            return (
              <View style={s.card} testID={`apt-${item.appointment_id}`}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                  <Text style={s.rowName}>{item.title}</Text>
                  <Text style={item.status === "confirmed" ? s.statusPaid : s.statusDue}>
                    {item.status.toUpperCase()}
                  </Text>
                </View>
                <Text style={s.rowMeta}>
                  {item.company_name} · {when.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} ·{" "}
                  {when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                  {item.location ? ` · ${item.location}` : ""}
                </Text>
              </View>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}
