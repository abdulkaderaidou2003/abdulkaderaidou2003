import React from "react";
import { Tabs } from "expo-router";
import { Feather } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Platform } from "react-native";

import { theme } from "@/src/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenListeners={{
        tabPress: () => {
          if (Platform.OS !== "web") {
            Haptics.selectionAsync().catch(() => undefined);
          }
        },
      }}
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.brand,
        tabBarInactiveTintColor: theme.colors.onSurfaceSecondary,
        tabBarStyle: {
          backgroundColor: theme.colors.surfaceSecondary,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: 64,
          paddingTop: 6,
          paddingBottom: 8,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "600", letterSpacing: 0.4 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "DASHBOARD",
          tabBarIcon: ({ color }) => <Feather name="grid" size={20} color={color} />,
          tabBarTestID: "tab-dashboard",
        }}
      />
      <Tabs.Screen
        name="modules"
        options={{
          title: "MODULES",
          tabBarIcon: ({ color }) => <Feather name="layers" size={20} color={color} />,
          tabBarTestID: "tab-modules",
        }}
      />
      <Tabs.Screen
        name="ai"
        options={{
          title: "AI",
          tabBarIcon: ({ color }) => <Feather name="cpu" size={20} color={color} />,
          tabBarTestID: "tab-ai",
        }}
      />
      <Tabs.Screen
        name="alerts"
        options={{
          title: "ALERTS",
          tabBarIcon: ({ color }) => <Feather name="bell" size={20} color={color} />,
          tabBarTestID: "tab-alerts",
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "PROFILE",
          tabBarIcon: ({ color }) => <Feather name="user" size={20} color={color} />,
          tabBarTestID: "tab-profile",
        }}
      />
    </Tabs>
  );
}
