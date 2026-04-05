import { CSSProperties } from "react";
import { formatPrice, formatDollar, formatPercent } from "../utils/format";

const cardStyle: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: "12px",
  padding: "16px 20px",
  marginTop: "12px",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
};

const rowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
};

const labelStyle: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "0.7rem",
  fontWeight: 600,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "var(--text-faint)",
  marginBottom: "4px",
};

const priceStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "1.3rem",
  fontWeight: 700,
  color: "var(--text-primary)",
};

const changeRowStyle: CSSProperties = {
  textAlign: "center",
  marginTop: "10px",
  paddingTop: "10px",
  borderTop: "1px solid var(--border-light)",
};

const liveDotStyle: CSSProperties = {
  display: "inline-block",
  width: "6px",
  height: "6px",
  borderRadius: "50%",
  backgroundColor: "var(--color-money)",
  marginRight: "5px",
  animation: "livePulse 2s ease-in-out infinite",
};

interface Props {
  priceAtPost: number | null;
  currentPrice: number | null;
  isLive?: boolean;
}

export function PriceKPIs({ priceAtPost, currentPrice, isLive }: Props) {
  if (priceAtPost == null && currentPrice == null) return null;

  const hasChange = priceAtPost != null && currentPrice != null && priceAtPost !== 0;
  const dollarChange = hasChange ? currentPrice - priceAtPost : null;
  const pctChange = hasChange ? ((currentPrice - priceAtPost) / priceAtPost) * 100 : null;

  const changeColor =
    dollarChange == null
      ? "var(--text-muted)"
      : dollarChange > 0
        ? "var(--color-money)"
        : dollarChange < 0
          ? "var(--color-red)"
          : "var(--text-muted)";

  return (
    <div style={cardStyle}>
      <style>{`@keyframes livePulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>Price at Post</div>
          <div style={priceStyle}>{formatPrice(priceAtPost)}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={labelStyle}>
            {isLive && <span style={liveDotStyle} />}
            Price Now
          </div>
          <div style={priceStyle}>{formatPrice(currentPrice)}</div>
        </div>
      </div>
      {hasChange && (
        <div style={changeRowStyle}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.85rem",
              fontWeight: 600,
              color: changeColor,
            }}
          >
            {formatDollar(dollarChange)} ({formatPercent(pctChange)})
          </span>
        </div>
      )}
    </div>
  );
}
