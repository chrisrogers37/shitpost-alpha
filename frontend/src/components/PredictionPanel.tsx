import { CSSProperties, useState } from "react";
import type { Prediction, EnsembleProviderResult } from "../types/api";
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
          {prediction.calibrated_confidence != null && (
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: 400,
                color: "var(--text-muted)",
                marginLeft: "6px",
              }}
            >
              ({Math.round(prediction.calibrated_confidence * 100)}% cal)
            </span>
          )}
        </span>
      </div>

      {prediction.thesis && (
        <div style={thesisTextStyle}>{prediction.thesis}</div>
      )}

      {prediction.ensemble_metadata && prediction.ensemble_results && (
        <EnsembleSection
          metadata={prediction.ensemble_metadata}
          results={prediction.ensemble_results.results}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Ensemble Model Comparison                                         */
/* ------------------------------------------------------------------ */

const agreementBadge: CSSProperties = {
  display: "inline-block",
  fontSize: "0.72rem",
  fontWeight: 600,
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  padding: "2px 8px",
  borderRadius: "4px",
  marginLeft: "8px",
};

const ensembleToggle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginTop: "14px",
  padding: "8px 12px",
  background: "var(--bg-sunken)",
  borderRadius: "8px",
  cursor: "pointer",
  userSelect: "none",
};

const providerRow: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "110px 1fr 60px",
  gap: "8px",
  padding: "6px 12px",
  fontSize: "0.8rem",
  borderBottom: "1px solid var(--border)",
  alignItems: "center",
};

function agreementColor(level: string): string {
  if (level === "unanimous") return "var(--color-green, #22c55e)";
  if (level === "majority") return "var(--color-blue, #3b82f6)";
  return "var(--color-red)";
}

function EnsembleSection({
  metadata,
  results,
}: {
  metadata: NonNullable<Prediction["ensemble_metadata"]>;
  results: EnsembleProviderResult[];
}) {
  const [expanded, setExpanded] = useState(false);
  const successfulResults = results.filter((r) => r.success);

  return (
    <div>
      <div style={ensembleToggle} onClick={() => setExpanded(!expanded)}>
        <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          {metadata.providers_succeeded}/{metadata.providers_queried} Models
          <span
            style={{
              ...agreementBadge,
              color: agreementColor(metadata.agreement_level),
              border: `1px solid ${agreementColor(metadata.agreement_level)}`,
            }}
          >
            {metadata.agreement_level}
          </span>
        </span>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {expanded && (
        <div
          style={{
            marginTop: "4px",
            background: "var(--bg-sunken)",
            borderRadius: "0 0 8px 8px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              ...providerRow,
              fontWeight: 600,
              fontSize: "0.72rem",
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              borderBottom: "2px solid var(--border)",
            }}
          >
            <span>Provider</span>
            <span>Assets & Sentiment</span>
            <span style={{ textAlign: "right" }}>Conf.</span>
          </div>

          {successfulResults.map((r) => (
            <div key={r.provider}>
              <div style={providerRow}>
                <span style={{ fontWeight: 500 }}>
                  {providerLabel(r.provider)}
                </span>
                <span style={{ color: "var(--text-secondary)" }}>
                  {Object.entries(r.market_impact)
                    .map(([sym, sent]) => `${sym} ${sent}`)
                    .join(", ") || "—"}
                </span>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                  }}
                >
                  {Math.round(r.confidence * 100)}%
                </span>
              </div>
              {r.thesis && (
                <div
                  style={{
                    padding: "4px 12px 8px",
                    fontSize: "0.75rem",
                    lineHeight: 1.5,
                    color: "var(--text-muted)",
                    fontStyle: "italic",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {r.thesis}
                </div>
              )}
            </div>
          ))}

          {results.filter((r) => !r.success).length > 0 && (
            <div
              style={{
                ...providerRow,
                color: "var(--text-muted)",
                fontStyle: "italic",
              }}
            >
              <span>
                {results
                  .filter((r) => !r.success)
                  .map((r) => providerLabel(r.provider))
                  .join(", ")}
              </span>
              <span>failed</span>
              <span />
            </div>
          )}

          <div
            style={{
              padding: "8px 12px",
              fontSize: "0.72rem",
              color: "var(--text-muted)",
              display: "flex",
              gap: "16px",
            }}
          >
            <span>
              Asset overlap:{" "}
              {Math.round(metadata.asset_agreement * 100)}%
            </span>
            <span>
              Sentiment match:{" "}
              {Math.round(metadata.sentiment_agreement * 100)}%
            </span>
            <span>
              Spread: {Math.round(metadata.confidence_spread * 100)}pp
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function providerLabel(id: string): string {
  const labels: Record<string, string> = {
    openai: "GPT-5.4",
    anthropic: "Opus 4.6",
    grok: "Grok 4",
  };
  return labels[id] ?? id;
}
