import { CSSProperties } from "react";
import type { Outcome } from "../types/api";
import { formatPercent, formatPnl } from "../utils/format";

const containerStyle: CSSProperties = {
  display: "flex",
  gap: "8px",
  marginTop: "12px",
  justifyContent: "center",
  flexWrap: "wrap",
};

interface TimeframeKey {
  label: string;
  returnKey: "same_day" | "hour_1" | "t1" | "t3" | "t7" | "t30";
}

const timeframes: TimeframeKey[] = [
  { label: "1D", returnKey: "t1" },
  { label: "3D", returnKey: "t3" },
  { label: "7D", returnKey: "t7" },
  { label: "30D", returnKey: "t30" },
];

interface Props {
  outcome: Outcome | undefined;
}

export function MetricBubbles({ outcome }: Props) {
  if (!outcome) return null;

  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "0.75rem",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--text-muted)",
          textAlign: "center",
          marginTop: "16px",
          marginBottom: "4px",
        }}
      >
        FREEDOM METRICS
      </div>
      <div style={containerStyle}>
        {timeframes.map(({ label, returnKey }) => {
          const ret = outcome.returns[returnKey];
          const correct = outcome.correct[returnKey];
          const pnl = outcome.pnl[returnKey];
          const isPositive = ret != null && ret > 0;
          const isPending = ret == null;

          const bgColor = isPending
            ? "var(--bg-sunken)"
            : isPositive
              ? "rgba(22, 163, 74, 0.08)"
              : "rgba(220, 38, 38, 0.08)";

          const borderColor = isPending
            ? "var(--border-light)"
            : isPositive
              ? "rgba(22, 163, 74, 0.3)"
              : "rgba(220, 38, 38, 0.3)";

          const textColor = isPending
            ? "var(--text-faint)"
            : isPositive
              ? "var(--color-money)"
              : "var(--color-red)";

          const bubbleStyle: CSSProperties = {
            background: bgColor,
            border: `1px solid ${borderColor}`,
            borderRadius: "12px",
            padding: "10px 16px",
            minWidth: "80px",
            textAlign: "center",
            flex: "1 1 0",
          };

          return (
            <div key={label} style={bubbleStyle}>
              <div
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 600,
                  color: "var(--text-faint)",
                  letterSpacing: "0.05em",
                  marginBottom: "4px",
                }}
              >
                {label}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  color: textColor,
                }}
              >
                {formatPercent(ret)}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.7rem",
                  color: textColor,
                  opacity: 0.8,
                  marginTop: "2px",
                }}
              >
                {formatPnl(pnl)}
              </div>
              {correct != null && (
                <div
                  style={{
                    fontSize: "0.65rem",
                    marginTop: "4px",
                    color: correct ? "var(--color-money)" : "var(--color-red)",
                  }}
                >
                  {correct ? "\u2713 Correct" : "\u2717 Wrong"}
                </div>
              )}
              {isPending && (
                <div style={{ fontSize: "0.6rem", marginTop: "4px", color: "var(--color-blue)" }}>
                  Pending
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
