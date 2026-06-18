import React, { useState } from "react";
import { View, Text, StyleSheet, Pressable, Linking, Platform, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import * as Haptics from "expo-haptics";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";

import { apiFetch } from "@/src/api/client";
import { theme } from "@/src/theme";

export default function Scan() {
  const router = useRouter();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState<string | null>(null);
  const [lookupResult, setLookupResult] = useState<null | { found: boolean; item?: { name: string; location: string; stock: number }; product?: { name: string; price: number } }>(null);
  const [looking, setLooking] = useState(false);

  const handleBarCodeScanned = async ({ data }: BarcodeScanningResult) => {
    if (scanned) return;
    setScanned(data);
    if (Platform.OS !== "web") {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    }
    setLooking(true);
    try {
      const r = await apiFetch<{ found: boolean; item?: { name: string; location: string; stock: number }; product?: { name: string; price: number } }>(
        `/inventory/lookup?barcode=${encodeURIComponent(data)}`,
      );
      setLookupResult(r);
    } finally {
      setLooking(false);
    }
  };

  const close = () => {
    if (returnTo) router.replace(`/module/${returnTo}`);
    else router.back();
  };

  if (!permission) {
    return (
      <SafeAreaView style={styles.center} testID="scan-loading">
        <ActivityIndicator color={theme.colors.brand} />
      </SafeAreaView>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.gate} edges={["top", "bottom"]} testID="scan-permission-gate">
        <Pressable style={styles.closeBtn} onPress={close} testID="scan-close">
          <Feather name="x" size={20} color={theme.colors.onSurface} />
        </Pressable>
        <View style={styles.gateBody}>
          <Feather name="camera" size={32} color={theme.colors.brand} />
          <Text style={styles.gateTitle}>Camera access needed</Text>
          <Text style={styles.gateDesc}>
            Aidou Command uses your camera to scan product and inventory barcodes. We don't record
            video or upload images.
          </Text>
          {permission.canAskAgain ? (
            <Pressable
              testID="scan-permission-grant"
              style={styles.gateBtn}
              onPress={() => requestPermission()}
            >
              <Text style={styles.gateBtnTxt}>Allow camera</Text>
            </Pressable>
          ) : (
            <Pressable
              testID="scan-permission-settings"
              style={styles.gateBtn}
              onPress={() => Linking.openSettings()}
            >
              <Text style={styles.gateBtnTxt}>Open Settings</Text>
            </Pressable>
          )}
          <Pressable onPress={close} style={{ marginTop: 14 }} testID="scan-permission-cancel">
            <Text style={styles.gateSkip}>Use manual entry instead</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.root} testID="scan-screen">
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        onBarcodeScanned={handleBarCodeScanned}
        barcodeScannerSettings={{
          barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128", "code39", "qr"],
        }}
      />
      <View style={styles.overlay} pointerEvents="box-none">
        <SafeAreaView edges={["top"]} style={{ flexDirection: "row", padding: 16 }}>
          <Pressable style={styles.closeBtnOver} onPress={close} testID="scan-close-overlay">
            <Feather name="x" size={20} color="#fff" />
          </Pressable>
          <View style={{ flex: 1 }} />
        </SafeAreaView>
        <View style={styles.reticle} />
        <Text style={styles.hint}>Align the barcode within the frame</Text>

        {scanned ? (
          <SafeAreaView edges={["bottom"]} style={styles.resultWrap}>
            <View
              style={[
                styles.result,
                {
                  borderColor: lookupResult?.found
                    ? theme.colors.success
                    : looking
                    ? theme.colors.borderStrong
                    : theme.colors.error,
                },
              ]}
              testID="scan-screen-result"
            >
              {looking ? (
                <ActivityIndicator color={theme.colors.brand} />
              ) : lookupResult?.found ? (
                <Feather name="check-circle" size={20} color={theme.colors.success} />
              ) : (
                <Feather name="x-circle" size={20} color={theme.colors.error} />
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.resultTitle}>
                  {looking
                    ? "Looking up…"
                    : lookupResult?.found
                    ? lookupResult.item?.name ?? lookupResult.product?.name
                    : "Not found"}
                </Text>
                <Text style={styles.resultMeta}>
                  Barcode: {scanned}
                  {lookupResult?.item
                    ? ` · ${lookupResult.item.location} · stock ${lookupResult.item.stock}`
                    : lookupResult?.product
                    ? ` · POS $${lookupResult.product.price.toFixed(2)}`
                    : ""}
                </Text>
              </View>
            </View>
            <View style={styles.actionRow}>
              <Pressable
                style={styles.scanAgain}
                testID="scan-again"
                onPress={() => {
                  setScanned(null);
                  setLookupResult(null);
                }}
              >
                <Feather name="refresh-cw" size={14} color={theme.colors.onSurface} />
                <Text style={styles.scanAgainTxt}>Scan another</Text>
              </Pressable>
              <Pressable style={styles.doneBtn} onPress={close} testID="scan-done">
                <Text style={styles.doneTxt}>DONE</Text>
              </Pressable>
            </View>
          </SafeAreaView>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#000" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.surface },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: "space-between" },
  reticle: {
    alignSelf: "center",
    width: 240,
    height: 240,
    borderWidth: 2,
    borderColor: theme.colors.brand,
    borderRadius: theme.radius.lg,
  },
  hint: {
    color: "#fff",
    textAlign: "center",
    fontSize: 13,
    paddingHorizontal: 20,
    textShadowColor: "rgba(0,0,0,0.7)",
    textShadowRadius: 6,
  },
  closeBtnOver: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  resultWrap: { padding: 16, gap: theme.spacing.sm },
  result: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "rgba(9,10,12,0.94)",
    borderWidth: 1,
    borderRadius: theme.radius.lg,
    padding: 14,
  },
  resultTitle: { color: theme.colors.onSurface, fontSize: 14, fontWeight: "800" },
  resultMeta: { color: theme.colors.onSurfaceSecondary, fontSize: 11, marginTop: 4 },
  actionRow: { flexDirection: "row", gap: theme.spacing.sm },
  scanAgain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.1)",
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    paddingVertical: 12,
    borderRadius: theme.radius.md,
  },
  scanAgainTxt: { color: theme.colors.onSurface, fontWeight: "700", fontSize: 13 },
  doneBtn: {
    flex: 1,
    backgroundColor: theme.colors.brand,
    paddingVertical: 12,
    borderRadius: theme.radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  doneTxt: { color: "#fff", fontWeight: "800", letterSpacing: 1 },
  gate: { flex: 1, backgroundColor: theme.colors.surface, padding: 24 },
  closeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  gateBody: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16, paddingHorizontal: 8 },
  gateTitle: { color: theme.colors.onSurface, fontSize: 22, fontWeight: "800", textAlign: "center" },
  gateDesc: { color: theme.colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19, textAlign: "center", maxWidth: 320 },
  gateBtn: {
    marginTop: 8,
    backgroundColor: theme.colors.brand,
    paddingHorizontal: 22,
    paddingVertical: 14,
    borderRadius: theme.radius.lg,
  },
  gateBtnTxt: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
  gateSkip: { color: theme.colors.onSurfaceSecondary, fontSize: 12, textDecorationLine: "underline" },
});
