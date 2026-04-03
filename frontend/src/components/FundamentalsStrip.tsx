import { CSSProperties } from "react";
import type { Fundamentals } from "../types/api";
import { formatLargeNumber } from "../utils/format";

const stripStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: "10px",
  padding: "10px 14px",
  marginTop: "8px",
};

const headerRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: "8px",
  flexWrap: "wrap",
};

const companyNameStyle: CSSProperties = {
  fontWeight: 700,
  fontSize: "0.85rem",
  color: "var(--color-navy)",
};

const metaStyle: CSSProperties = {
  fontSize: "0.65rem",
  color: "var(--text-muted)",
};

const metricsRowStyle: CSSProperties = {
  display: "flex",
  gap: "14px",
  marginTop: "5px",
  flexWrap: "wrap",
};

const metricStyle: CSSProperties = {
  fontSize: "0.65rem",
};

const labelStyle: CSSProperties = {
  color: "var(--text-faint)",
  marginRight: "3px",
};

const valueStyle: CSSProperties = {
  fontWeight: 600,
  color: "var(--text-secondary)",
  fontFamily: "var(--font-mono)",
};

function formatRatio(value: number | null): string {
  if (value == null) return "—";
  return value.toFixed(1);
}

function formatPct(value: number | null): string {
  if (value == null) return "—";
  // dividend_yield is stored as a percentage (e.g., 0.91 = 0.91%)
  return `${value.toFixed(2)}%`;
}

interface Props {
  fundamentals: Fundamentals | null;
}

export function FundamentalsStrip({ fundamentals }: Props) {
  if (!fundamentals || !fundamentals.company_name) return null;

  const parts = [fundamentals.exchange, fundamentals.sector].filter(Boolean);

  return (
    <div style={stripStyle}>
      <div style={headerRowStyle}>
        <span style={companyNameStyle}>{fundamentals.company_name}</span>
        {parts.length > 0 && (
          <span style={metaStyle}>{parts.join(" · ")}</span>
        )}
      </div>
      <div style={metricsRowStyle}>
        <span style={metricStyle}>
          <span style={labelStyle}>Mkt Cap</span>
          <span style={valueStyle}>{formatLargeNumber(fundamentals.market_cap, "$")}</span>
        </span>
        <span style={metricStyle}>
          <span style={labelStyle}>P/E</span>
          <span style={valueStyle}>{formatRatio(fundamentals.pe_ratio)}</span>
        </span>
        <span style={metricStyle}>
          <span style={labelStyle}>Fwd P/E</span>
          <span style={valueStyle}>{formatRatio(fundamentals.forward_pe)}</span>
        </span>
        <span style={metricStyle}>
          <span style={labelStyle}>Beta</span>
          <span style={valueStyle}>{formatRatio(fundamentals.beta)}</span>
        </span>
        <span style={metricStyle}>
          <span style={labelStyle}>Div</span>
          <span style={valueStyle}>{formatPct(fundamentals.dividend_yield)}</span>
        </span>
      </div>
    </div>
  );
}
