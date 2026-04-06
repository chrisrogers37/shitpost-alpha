import { CSSProperties, useEffect, useRef, useState } from "react";
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
  transition: "color 0.3s ease",
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

const updatedAgoStyle: CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.6rem",
  color: "var(--text-faint)",
  marginTop: "2px",
};

function useFlashColor(price: number | null): string | undefined {
  const prevPrice = useRef(price);
  const [flash, setFlash] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (price == null || prevPrice.current == null || price === prevPrice.current) {
      prevPrice.current = price;
      return;
    }
    const color = price > prevPrice.current ? "var(--color-money)" : "var(--color-red)";
    setFlash(color);
    prevPrice.current = price;
    const timer = setTimeout(() => setFlash(undefined), 800);
    return () => clearTimeout(timer);
  }, [price]);

  return flash;
}

function useUpdatedAgo(isLive: boolean, capturedAt: string | undefined): string {
  const [ago, setAgo] = useState("");

  useEffect(() => {
    if (!isLive || !capturedAt) {
      setAgo("");
      return;
    }
    const update = () => {
      const seconds = Math.floor((Date.now() - new Date(capturedAt).getTime()) / 1000);
      if (seconds < 5) setAgo("just now");
      else if (seconds < 60) setAgo(`${seconds}s ago`);
      else setAgo(`${Math.floor(seconds / 60)}m ago`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [isLive, capturedAt]);

  return ago;
}

interface Props {
  priceAtPost: number | null;
  currentPrice: number | null;
  isLive?: boolean;
  capturedAt?: string;
}

export function PriceKPIs({ priceAtPost, currentPrice, isLive, capturedAt }: Props) {
  if (priceAtPost == null && currentPrice == null) return null;

  const flashColor = useFlashColor(currentPrice);
  const updatedAgo = useUpdatedAgo(isLive ?? false, capturedAt);

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
      <style>{`
        @keyframes livePulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
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
          <div style={{ ...priceStyle, color: flashColor ?? priceStyle.color }}>
            {formatPrice(currentPrice)}
          </div>
          {updatedAgo && <div style={updatedAgoStyle}>{updatedAgo}</div>}
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
