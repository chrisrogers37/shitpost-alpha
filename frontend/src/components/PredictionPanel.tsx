import { CSSProperties } from "react";
import type { Prediction } from "../types/api";
import { formatConfidence } from "../utils/format";

const panelStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: "12px",
  padding: "20px",
  marginTop: "12px",
};

const headerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "12px",
};

const labelStyle: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "0.85rem",
  fontWeight: 600,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: "var(--text-muted)",
};

const convictionStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "1.1rem",
  fontWeight: 600,
};

const thesisTextStyle: CSSProperties = {
  fontSize: "0.85rem",
  lineHeight: 1.6,
  color: "var(--text-primary)",
  marginTop: "4px",
  padding: "12px",
  background: "var(--bg-sunken)",
  borderRadius: "8px",
  borderLeft: "3px solid var(--color-gold)",
};

interface Props {
  prediction: Prediction;
}

export function PredictionPanel({ prediction }: Props) {
  const confidenceColor =
    (prediction.confidence ?? 0) >= 0.7
      ? "var(--color-gold)"
      : "var(--text-primary)";

  return (
    <div style={panelStyle}>
      <div style={headerRow}>
        <span style={labelStyle}>AI Intelligence Report</span>
        <span style={{ ...convictionStyle, color: confidenceColor }}>
          {formatConfidence(prediction.confidence)} CONVICTION
        </span>
      </div>

      {prediction.thesis && (
        <div style={thesisTextStyle}>{prediction.thesis}</div>
      )}
    </div>
  );
}
