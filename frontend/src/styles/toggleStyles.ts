/** Shared toggle button styles used by MetricBubbles, PriceChart, etc. */

import { CSSProperties } from "react";

export const toggleGroupStyle: CSSProperties = {
  display: "flex",
  background: "var(--bg-sunken)",
  borderRadius: "6px",
  overflow: "hidden",
  border: "1px solid var(--border-light)",
};

export const toggleBtnBase: CSSProperties = {
  padding: "3px 10px",
  fontSize: "0.6rem",
  fontWeight: 600,
  cursor: "pointer",
  border: "none",
  background: "transparent",
  color: "var(--text-muted)",
  letterSpacing: "0.03em",
  fontFamily: "var(--font-display)",
};

export const toggleBtnActive: CSSProperties = {
  ...toggleBtnBase,
  background: "var(--color-navy)",
  color: "white",
};
