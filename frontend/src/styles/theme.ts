/** Design tokens — hyper-American patriotic finance theme. */

export const colors = {
  bgPage: "#0B1215",
  bgCard: "#141E22",
  bgSunken: "#0E1719",
  money: "#85BB65",
  gold: "#FFD700",
  navy: "#002868",
  red: "#B22234",
  textPrimary: "#F5F1E8",
  textMuted: "#8B9A7E",
  border: "#2A3A2E",
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
