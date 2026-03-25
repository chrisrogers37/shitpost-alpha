import { CSSProperties } from "react";
import type { Prediction } from "../types/api";
import { formatConfidence } from "../utils/format";

const panelStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderLeft: "4px solid var(--color-red)",
  borderRadius: "12px",
  padding: "20px",
  marginTop: "12px",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
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
  fontWeight: 700,
};

const thesisTextStyle: CSSProperties = {
  fontSize: "0.88rem",
  lineHeight: 1.7,
  color: "var(--text-secondary)",
  padding: "14px 16px",
  background: "var(--bg-sunken)",
  borderRadius: "8px",
  borderLeft: "3px solid var(--color-blue)",
};

interface Props {
  prediction: Prediction;
}

export function PredictionPanel({ prediction }: Props) {
  const confidence = prediction.confidence ?? 0;
  const confidenceColor =
    confidence >= 0.7 ? "var(--color-red)" : "var(--text-muted)";

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
