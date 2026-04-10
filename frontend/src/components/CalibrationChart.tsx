import { useEffect, useState, type CSSProperties } from "react";
import { fetchCalibrationCurve } from "../api/client";
import type { CalibrationCurveData } from "../types/api";
import { colors } from "../styles/theme";

const containerStyle: CSSProperties = {
  marginTop: "12px",
  borderRadius: "12px",
  overflow: "hidden",
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
  padding: "16px",
};

const titleStyle: CSSProperties = {
  fontSize: "13px",
  fontWeight: 600,
  color: colors.navy,
  marginBottom: "12px",
};

const metaStyle: CSSProperties = {
  fontSize: "11px",
  color: colors.textMuted,
  marginTop: "8px",
};

const CHART_W = 300;
const CHART_H = 220;
const PAD = { top: 10, right: 20, bottom: 30, left: 40 };
const PLOT_W = CHART_W - PAD.left - PAD.right;
const PLOT_H = CHART_H - PAD.top - PAD.bottom;

export default function CalibrationChart() {
  const [data, setData] = useState<CalibrationCurveData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchCalibrationCurve("t7")
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error || !data) return null;

  const bins = data.bin_stats.filter((b) => b.accuracy !== null && b.n_total > 0);
  if (bins.length === 0) return null;

  const x = (v: number) => PAD.left + v * PLOT_W;
  const y = (v: number) => PAD.top + (1 - v) * PLOT_H;

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>Confidence Calibration (T+7)</div>
      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        width="100%"
        style={{ maxWidth: CHART_W }}
      >
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <line
            key={`h-${v}`}
            x1={PAD.left}
            x2={PAD.left + PLOT_W}
            y1={y(v)}
            y2={y(v)}
            stroke={colors.gridLine}
            strokeWidth={1}
          />
        ))}

        {/* Perfect calibration diagonal */}
        <line
          x1={x(0)}
          y1={y(0)}
          x2={x(1)}
          y2={y(1)}
          stroke={colors.borderLight}
          strokeWidth={1}
          strokeDasharray="4 4"
        />

        {/* Actual calibration points + line */}
        {bins.length > 1 && (
          <polyline
            points={bins
              .map((b) => `${x(b.bin_center)},${y(b.accuracy!)}`)
              .join(" ")}
            fill="none"
            stroke={colors.blue}
            strokeWidth={2}
          />
        )}
        {bins.map((b) => (
          <circle
            key={b.bin_label}
            cx={x(b.bin_center)}
            cy={y(b.accuracy!)}
            r={Math.min(6, Math.max(3, b.n_total / 20))}
            fill={colors.blue}
            opacity={0.85}
          >
            <title>
              {b.bin_label}: {(b.accuracy! * 100).toFixed(0)}% accurate (n=
              {b.n_total})
            </title>
          </circle>
        ))}

        {/* Y-axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <text
            key={`yl-${v}`}
            x={PAD.left - 4}
            y={y(v) + 3}
            textAnchor="end"
            fontSize={9}
            fill={colors.textMuted}
          >
            {(v * 100).toFixed(0)}%
          </text>
        ))}

        {/* X-axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <text
            key={`xl-${v}`}
            x={x(v)}
            y={PAD.top + PLOT_H + 14}
            textAnchor="middle"
            fontSize={9}
            fill={colors.textMuted}
          >
            {(v * 100).toFixed(0)}%
          </text>
        ))}

        {/* Axis labels */}
        <text
          x={x(0.5)}
          y={CHART_H - 2}
          textAnchor="middle"
          fontSize={10}
          fill={colors.textSecondary}
        >
          Raw Confidence
        </text>
        <text
          x={10}
          y={y(0.5)}
          textAnchor="middle"
          fontSize={10}
          fill={colors.textSecondary}
          transform={`rotate(-90, 10, ${y(0.5)})`}
        >
          Actual Accuracy
        </text>
      </svg>
      <div style={metaStyle}>
        {data.n_predictions} predictions &middot; Fitted{" "}
        {new Date(data.fitted_at).toLocaleDateString()}
      </div>
    </div>
  );
}
