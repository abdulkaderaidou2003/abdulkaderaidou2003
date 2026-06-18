/**
 * Aidou Command theme tokens — pulled from design_guidelines.json
 * Dark-First Utility (command-center).
 */
export const theme = {
  colors: {
    surface: "#090A0C",
    onSurface: "#F8F9FA",
    surfaceSecondary: "#121418",
    onSurfaceSecondary: "#A1A1AA",
    surfaceTertiary: "#1C1F26",
    onSurfaceTertiary: "#D4D4D8",
    brand: "#E25822",
    brandSecondary: "#272A32",
    brandTertiary: "#2E1B15",
    onBrandTertiary: "#FFB89E",
    success: "#10B981",
    warning: "#F59E0B",
    error: "#EF4444",
    info: "#6B7280",
    border: "#272A32",
    borderStrong: "#3F434D",
    divider: "#1A1D24",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 4, md: 6, lg: 12, pill: 999 },
  font: {
    sm: 12,
    base: 14,
    lg: 16,
    xl: 20,
    xxl: 24,
    display: 36,
  },
} as const;

export type Theme = typeof theme;
