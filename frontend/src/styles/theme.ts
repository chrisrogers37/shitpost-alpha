/** Design tokens — Clean American light theme. */

export const colors = {
  bgPage: "#F1F5F9",
  bgCard: "#FFFFFF",
  bgSunken: "#F8FAFC",
  money: "#16A34A",
  red: "#DC2626",
  navy: "#1E3A5F",
  blue: "#2563EB",
  textPrimary: "#0F172A",
  textSecondary: "#334155",
  textMuted: "#64748B",
  textFaint: "#94A3B8",
  border: "#CBD5E1",
  borderLight: "#E2E8F0",
  gridLine: "#F1F5F9",
} as const;

export const fonts = {
  display: "'Oswald', 'Bebas Neue', sans-serif",
  body: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', monospace",
} as const;

export const sentimentColors: Record<string, string> = {
  bullish: colors.money,
  bearish: colors.red,
  neutral: colors.textMuted,
};
