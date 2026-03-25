import { CSSProperties } from "react";

const containerStyle: CSSProperties = {
  display: "flex",
  gap: "4px",
  justifyContent: "center",
  marginTop: "16px",
  background: "#F1F5F9",
  borderRadius: "8px",
  padding: "3px",
  width: "fit-content",
  margin: "16px auto 0",
};

export type Timeframe = "1d" | "7d" | "30d";

const options: { label: string; value: Timeframe }[] = [
  { label: "1D", value: "1d" },
  { label: "7D", value: "7d" },
  { label: "30D", value: "30d" },
];

export const timeframeToDays: Record<Timeframe, number> = {
  "1d": 7,
  "7d": 30,
  "30d": 90,
};

interface Props {
  selected: Timeframe;
  onSelect: (tf: Timeframe) => void;
}

export function TimeframeToggle({ selected, onSelect }: Props) {
  return (
    <div style={containerStyle}>
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
          background: isActive ? "#2563EB" : "transparent",
          color: isActive ? "#FFFFFF" : "#64748B",
          transition: "all 0.15s ease",
        };

        return (
          <button key={value} style={btnStyle} onClick={() => onSelect(value)}>
            {label}
          </button>
        );
      })}
    </div>
  );
}
