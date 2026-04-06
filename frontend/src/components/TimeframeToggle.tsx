import { CSSProperties } from "react";

const containerStyle: CSSProperties = {
  display: "flex",
  gap: "4px",
  justifyContent: "center",
  marginTop: "16px",
  background: "var(--bg-sunken)",
  borderRadius: "8px",
  padding: "3px",
  width: "fit-content",
  margin: "16px auto 0",
};

export type Timeframe = "1d" | "7d" | "30d" | "90d";

const options: { label: string; value: Timeframe }[] = [
  { label: "1D", value: "1d" },
  { label: "7D", value: "7d" },
  { label: "30D", value: "30d" },
  { label: "90D", value: "90d" },
];

export const timeframeToDays: Record<Timeframe, number> = {
  "1d": 7,
  "7d": 30,
  "30d": 90,
  "90d": 180,
};

interface Props {
  selected: Timeframe;
  onSelect: (tf: Timeframe) => void;
}

export function TimeframeToggle({ selected, onSelect }: Props) {
  return (
    <div style={containerStyle} role="tablist" aria-label="Chart timeframe">
      {options.map(({ label, value }) => {
        const isActive = value === selected;
        const btnStyle: CSSProperties = {
          padding: "5px 16px",
          borderRadius: "6px",
          border: "none",
          fontSize: "0.75rem",
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          cursor: "pointer",
          background: isActive ? "var(--color-blue)" : "transparent",
          color: isActive ? "var(--bg-card)" : "var(--text-muted)",
          transition: "all 0.15s ease",
        };

        return (
          <button key={value} style={btnStyle} onClick={() => onSelect(value)} role="tab" aria-selected={isActive}>
            {label}
          </button>
        );
      })}
    </div>
  );
}
