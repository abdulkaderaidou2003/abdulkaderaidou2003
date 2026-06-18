import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { AuthProvider, useAuth } from "@/src/contexts/AuthContext";
import { CompanyProvider } from "@/src/contexts/CompanyContext";
import { theme } from "@/src/theme";
import Login from "./login";

// Keep the native splash visible from cold start until icon fonts register.
SplashScreen.preventAutoHideAsync();

function StackRoot() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={styles.boot} testID="boot-loader">
        <ActivityIndicator size="large" color={theme.colors.brand} />
      </View>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.surface } }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="module/[id]" />
      <Stack.Screen name="login" options={{ presentation: "modal" }} />
    </Stack>
  );
}

export default function RootLayout() {
  const [loaded, error] = useIconFonts();

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: theme.colors.surface }}>
      <SafeAreaProvider>
        <AuthProvider>
          <CompanyProvider>
            <StatusBar style="light" />
            <StackRoot />
          </CompanyProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.surface,
  },
});
