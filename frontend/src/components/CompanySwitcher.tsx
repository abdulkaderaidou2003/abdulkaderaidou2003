import React, { useState } from "react";
import { View, Text, Pressable, Modal, StyleSheet, ScrollView } from "react-native";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useCompanies } from "@/src/contexts/CompanyContext";
import { theme } from "@/src/theme";

export function CompanySwitcher() {
  const { companies, active, switchTo } = useCompanies();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Pressable
        testID="company-switcher-trigger"
        onPress={() => setOpen(true)}
        style={styles.trigger}
      >
        <View
          style={[
            styles.dot,
            { backgroundColor: active?.logo_color ?? theme.colors.brand },
          ]}
        />
        <View style={styles.triggerCenter}>
          <Text style={styles.triggerLabel} numberOfLines={1}>
            {active?.name ?? "Select company"}
          </Text>
          <Text style={styles.triggerSub} numberOfLines={1}>
            {active?.industry ?? "—"}
          </Text>
        </View>
        <Feather name="chevron-down" size={16} color={theme.colors.onSurfaceSecondary} />
      </Pressable>
      <Modal
        visible={open}
        animationType="fade"
        transparent
        onRequestClose={() => setOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Switch company</Text>
            <ScrollView>
              {companies.map((c) => {
                const isActive = c.company_id === active?.company_id;
                return (
                  <Pressable
                    key={c.company_id}
                    testID={`company-option-${c.company_id}`}
                    onPress={async () => {
                      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
                      await switchTo(c.company_id);
                      setOpen(false);
                    }}
                    style={[styles.row, isActive && styles.rowActive]}
                  >
                    <View style={[styles.dot, { backgroundColor: c.logo_color }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.rowName}>{c.name}</Text>
                      <Text style={styles.rowSub}>{c.industry}</Text>
                    </View>
                    {isActive && (
                      <Feather name="check" size={18} color={theme.colors.brand} />
                    )}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    borderRadius: theme.radius.lg,
  },
  triggerCenter: { flex: 1 },
  triggerLabel: { color: theme.colors.onSurface, fontWeight: "700", fontSize: 13 },
  triggerSub: { color: theme.colors.onSurfaceSecondary, fontSize: 11 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.7)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: theme.colors.surfaceSecondary,
    borderTopLeftRadius: theme.radius.lg,
    borderTopRightRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.xxl,
    maxHeight: "70%",
    borderTopWidth: 1,
    borderColor: theme.colors.border,
  },
  sheetTitle: {
    color: theme.colors.onSurface,
    fontSize: 18,
    fontWeight: "800",
    marginBottom: theme.spacing.lg,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    paddingVertical: theme.spacing.md,
    paddingHorizontal: theme.spacing.md,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: "transparent",
    marginBottom: theme.spacing.sm,
  },
  rowActive: {
    backgroundColor: theme.colors.brandTertiary,
    borderColor: theme.colors.brand,
  },
  rowName: { color: theme.colors.onSurface, fontWeight: "700", fontSize: 14 },
  rowSub: { color: theme.colors.onSurfaceSecondary, fontSize: 12 },
});
