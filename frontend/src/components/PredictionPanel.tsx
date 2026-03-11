import { CSSProperties, useState } from "react";
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

const thesisToggle: CSSProperties = {
  background: "none",
  border: "none",
  color: "var(--text-muted)",
  fontSize: "0.8rem",
  cursor: "pointer",
  padding: "8px 0 0",
  textDecoration: "underline",
  textUnderlineOffset: "2px",
};

const thesisText: CSSProperties = {
  fontSize: "0.85rem",
  lineHeight: 1.6,
  color: "var(--text-muted)",
  marginTop: "8px",
  padding: "12px",
  background: "var(--bg-sunken)",
  borderRadius: "8px",
};

interface Props {
  prediction: Prediction;
}

export function PredictionPanel({ prediction }: Props) {
  const [showThesis, setShowThesis] = useState(false);

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
        <>
          <button
            style={thesisToggle}
            onClick={() => setShowThesis(!showThesis)}
          >
            {showThesis ? "Hide thesis" : "Read full thesis"}
          </button>
          {showThesis && <div style={thesisText}>{prediction.thesis}</div>}
        </>
      )}
    </div>
  );
}
