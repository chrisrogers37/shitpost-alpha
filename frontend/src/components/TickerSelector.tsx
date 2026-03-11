import { CSSProperties } from "react";
import { sentimentColors } from "../styles/theme";

const rowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
  marginTop: "12px",
  justifyContent: "center",
};

interface Props {
  tickers: string[];
  impacts: Record<string, string>;
  selectedTicker: string;
  onSelect: (ticker: string) => void;
}

export function TickerSelector({ tickers, impacts, selectedTicker, onSelect }: Props) {
  return (
    <div style={rowStyle}>
      {tickers.map((ticker) => {
        const sentiment = impacts[ticker] ?? "neutral";
        const color = sentimentColors[sentiment] ?? "var(--text-muted)";
        const isActive = ticker === selectedTicker;

        const pillStyle: CSSProperties = {
          padding: "6px 14px",
          borderRadius: "20px",
          fontSize: "0.8rem",
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          cursor: "pointer",
          border: `1.5px solid ${color}`,
          background: isActive ? color : "transparent",
          color: isActive ? "var(--bg-page)" : color,
          transition: "all 0.15s ease",
          letterSpacing: "0.03em",
        };

        return (
          <button
            key={ticker}
            style={pillStyle}
            onClick={() => onSelect(ticker)}
            title={`${ticker} — ${sentiment}`}
          >
            {ticker}
            <span style={{ fontSize: "0.65rem", marginLeft: "4px", opacity: 0.8 }}>
              {sentiment === "bullish" ? "\u25B2" : sentiment === "bearish" ? "\u25BC" : "\u25CF"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
