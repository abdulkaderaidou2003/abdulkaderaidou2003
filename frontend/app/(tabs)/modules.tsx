import React, { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";

import { apiFetch } from "@/src/api/client";
import { theme } from "@/src/theme";

interface Module {
  id: string;
  name: string;
  icon: keyof typeof Feather.glyphMap;
  desc: string;
}
interface CatalogGroup {
  category: string;
  modules: Module[];
}

export default function ModuleHub() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<CatalogGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiFetch<{ catalog: CatalogGroup[] }>("/modules")
      .then((r) => setCatalog(r.catalog))
      .catch((e) => console.warn(e))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return catalog;
    return catalog
      .map((g) => ({
        ...g,
        modules: g.modules.filter(
          (m) => m.name.toLowerCase().includes(q) || m.desc.toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.modules.length > 0);
  }, [catalog, search]);

  const launchable = ["hr", "tickets", "schedule", "crm", "pos", "payroll", "fleet", "inventory"];

  return (
    <SafeAreaView style={styles.root} edges={["top"]} testID="modules-screen">
      <View style={styles.header}>
        <Text style={styles.title}>Module Hub</Text>
        <Text style={styles.sub}>Launch any of 60+ enterprise modules</Text>
      </View>
      <View style={styles.searchWrap}>
        <Feather name="search" size={16} color={theme.colors.onSurfaceSecondary} />
        <TextInput
          testID="module-search-input"
          placeholder="Search modules…"
          placeholderTextColor={theme.colors.onSurfaceSecondary}
          style={styles.search}
          value={search}
          onChangeText={setSearch}
        />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.brand} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll}>
          {filtered.map((g) => (
            <View key={g.category} style={{ marginBottom: theme.spacing.lg }}>
              <Text style={styles.catLabel}>{g.category.toUpperCase()}</Text>
              <View style={styles.grid}>
                {g.modules.map((m) => {
                  const live = launchable.includes(m.id);
                  return (
                    <Pressable
                      key={m.id}
                      testID={`module-tile-${m.id}`}
                      onPress={() => {
                        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                        router.push(`/module/${m.id}`);
                      }}
                      style={({ pressed }) => [
                        styles.tile,
                        pressed && { borderColor: theme.colors.brand },
                      ]}
                    >
                      <View style={styles.tileIcon}>
                        <Feather name={m.icon} size={20} color={theme.colors.onSurface} />
                      </View>
                      <Text style={styles.tileName} numberOfLines={1}>
                        {m.name}
                      </Text>
                      <Text style={styles.tileDesc} numberOfLines={1}>
                        {m.desc}
                      </Text>
                      {live ? (
                        <View style={styles.liveBadge}>
                          <Text style={styles.liveBadgeTxt}>LIVE</Text>
                        </View>
                      ) : null}
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}
          <View style={{ height: 80 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  header: { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.sm, paddingBottom: theme.spacing.md },
  title: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800" },
  sub: { color: theme.colors.onSurfaceSecondary, fontSize: 12, marginTop: 2 },
  searchWrap: {
    marginHorizontal: theme.spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.md,
  },
  search: { flex: 1, color: theme.colors.onSurface, paddingVertical: 12, fontSize: 14 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  scroll: { padding: theme.spacing.lg },
  catLabel: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: theme.spacing.sm,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: theme.spacing.sm },
  tile: {
    width: "31.7%",
    aspectRatio: 0.95,
    backgroundColor: theme.colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.sm,
    position: "relative",
  },
  tileIcon: {
    width: 32,
    height: 32,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.brandSecondary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: theme.spacing.sm,
  },
  tileName: { color: theme.colors.onSurface, fontSize: 12, fontWeight: "700" },
  tileDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 10, marginTop: 2 },
  liveBadge: {
    position: "absolute",
    top: 6,
    right: 6,
    backgroundColor: theme.colors.brandTertiary,
    borderWidth: 1,
    borderColor: theme.colors.brand,
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: theme.radius.sm,
  },
  liveBadgeTxt: { color: theme.colors.brand, fontSize: 8, fontWeight: "800", letterSpacing: 0.5 },
});
