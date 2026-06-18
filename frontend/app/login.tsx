import React from "react";
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import { useAuth } from "@/src/contexts/AuthContext";
import { theme } from "@/src/theme";

export default function Login() {
  const { signIn } = useAuth();
  const [signing, setSigning] = React.useState(false);

  const handleSignIn = async () => {
    setSigning(true);
    try {
      await signIn();
    } finally {
      setSigning(false);
    }
  };

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <LinearGradient
        colors={["#0F0F12", "#090A0C"]}
        style={styles.gradient}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      >
        <View style={styles.topBlock}>
          <View style={styles.logoMark} testID="aidou-logo">
            <Feather name="command" size={28} color={theme.colors.brand} />
          </View>
          <Text style={styles.brandLabel}>AIDOU COMMAND</Text>
          <Text style={styles.brandSub}>ENTERPRISE ULTIMATE</Text>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroLine}>One platform.</Text>
          <Text style={styles.heroLine}>Any company.</Text>
          <Text style={[styles.heroLine, { color: theme.colors.brand }]}>Total command.</Text>
          <Text style={styles.heroDesc}>
            HR · Payroll · Finance · CRM · POS · Fleet · Inventory · Tickets · Compliance · AI ·
            and 50+ more modules in a single command center.
          </Text>
        </View>

        <View style={styles.bottom}>
          <Pressable
            testID="google-signin-button"
            onPress={handleSignIn}
            disabled={signing}
            style={({ pressed }) => [styles.signinBtn, pressed && { opacity: 0.85 }]}
          >
            {signing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Feather name="log-in" size={18} color="#fff" />
                <Text style={styles.signinTxt}>Sign in with Google</Text>
              </>
            )}
          </Pressable>
          <Text style={styles.footnote}>
            By continuing you agree to Aidou's Terms and Privacy Policy.
          </Text>
        </View>
      </LinearGradient>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.surface },
  gradient: { flex: 1, paddingHorizontal: theme.spacing.xl, justifyContent: "space-between", paddingVertical: theme.spacing.xl },
  topBlock: { alignItems: "flex-start" },
  logoMark: {
    width: 52,
    height: 52,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: theme.colors.brand,
    marginBottom: theme.spacing.lg,
  },
  brandLabel: {
    color: theme.colors.onSurface,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 2,
  },
  brandSub: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 11,
    letterSpacing: 4,
    marginTop: 2,
  },
  hero: { paddingVertical: theme.spacing.xl },
  heroLine: {
    color: theme.colors.onSurface,
    fontSize: 38,
    fontWeight: "800",
    letterSpacing: -1,
    lineHeight: 44,
  },
  heroDesc: {
    color: theme.colors.onSurfaceSecondary,
    fontSize: 14,
    marginTop: theme.spacing.lg,
    lineHeight: 20,
  },
  bottom: { gap: theme.spacing.md },
  signinBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.brand,
    paddingVertical: 16,
    borderRadius: theme.radius.lg,
  },
  signinTxt: { color: "#fff", fontWeight: "700", fontSize: 15, letterSpacing: 0.2 },
  footnote: { color: theme.colors.onSurfaceSecondary, fontSize: 11, textAlign: "center" },
});
