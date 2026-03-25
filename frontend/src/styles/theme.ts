/** Design tokens — AMERICA FIRST finance theme. */

export const colors = {
  bgPage: "#0A0F1E",
  bgCard: "#0F1729",
  bgSunken: "#0A0E1A",
  money: "#22C55E",
  gold: "#FFD700",
  navy: "#1D4ED8",
  red: "#EF4444",
  blue: "#3B82F6",
  white: "#F8FAFC",
  textPrimary: "#F8FAFC",
  textMuted: "#93A8C4",
  border: "#1E3A6E",
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
