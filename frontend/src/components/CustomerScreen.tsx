import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { theme } from "@/src/theme";

export function CustomerHeader({
  title,
  sub,
  testID,
}: {
  title: string;
  sub?: string;
  testID?: string;
}) {
  const router = useRouter();
  return (
    <View style={styles.header} testID={testID}>
      <Pressable testID="cust-back" onPress={() => router.back()} style={styles.backBtn}>
        <Feather name="chevron-left" size={20} color={theme.colors.onSurface} />
      </Pressable>
      <View style={{ flex: 1 }}>
        <Text style={styles.title}>{title}</Text>
        {sub ? <Text style={styles.sub}>{sub}</Text> : null}
      </View>
    </View>
  );
}

export const customerStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  list: { padding: theme.spacing.lg, paddingBottom: 80 },
  card: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { padding: 40, alignItems: "center", gap: 14 },
  emptyTitle: { color: theme.colors.onSurface, fontSize: 16, fontWeight: "800" },
  emptyDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 12, textAlign: "center", maxWidth: 280 },
  rowName: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800" },
  rowMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 4 },
  amount: { color: theme.colors.brand, fontSize: 16, fontWeight: "800" },
  statusPaid: { color: theme.colors.success, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  statusDue: { color: theme.colors.warning, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  statusOverdue: { color: theme.colors.error, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
});

const styles = StyleSheet.create({
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
});

export { SafeAreaView };
