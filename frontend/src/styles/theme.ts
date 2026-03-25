/** Design tokens — Stars & Stripes American finance theme. */

export const colors = {
  bgPage: "#0A0E1A",
  bgCard: "#111827",
  bgSunken: "#0D1117",
  money: "#22C55E",
  gold: "#FFD700",
  navy: "#1E3A5F",
  red: "#DC2626",
  textPrimary: "#F8FAFC",
  textMuted: "#94A3B8",
  border: "#1E3050",
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
