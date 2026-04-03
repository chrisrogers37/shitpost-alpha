import { useEffect, useRef, useState } from "react";
import { CSSProperties } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { PriceResponse, Outcome } from "../types/api";
import { colors } from "../styles/theme";
import { toggleGroupStyle, toggleBtnBase, toggleBtnActive } from "../styles/toggleStyles";

const containerStyle: CSSProperties = {
  marginTop: "12px",
  borderRadius: "12px",
  overflow: "hidden",
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "8px 12px",
  borderBottom: "1px solid var(--border-light)",
};

const loadingStyle: CSSProperties = {
  height: "300px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--text-muted)",
  fontSize: "0.85rem",
};

type ChartType = "candle" | "line";

interface Props {
  symbol: string;
  data: PriceResponse | undefined;
  isLoading: boolean;
  outcome?: Outcome;
}

export function PriceChart({ symbol, data, isLoading, outcome }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [chartType, setChartType] = useState<ChartType>("candle");

  useEffect(() => {
    if (!containerRef.current || !data || data.candles.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: colors.bgCard },
        textColor: colors.textMuted,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: colors.gridLine },
        horzLines: { color: colors.gridLine },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: colors.borderLight,
      },
      timeScale: {
        borderColor: colors.borderLight,
        timeVisible: false,
      },
    });

    // Build candle/line data
    const candleData = data.candles.map((c) => ({
      time: c.date as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    let mainSeries: ISeriesApi<"Candlestick"> | ISeriesApi<"Line">;

    if (chartType === "candle") {
      const series = chart.addCandlestickSeries({
        upColor: colors.money,
        downColor: colors.red,
        wickUpColor: colors.money,
        wickDownColor: colors.red,
        borderVisible: false,
      });
      series.setData(candleData);
      mainSeries = series;
    } else {
      const series = chart.addLineSeries({
        color: colors.blue,
        lineWidth: 2,
        crosshairMarkerVisible: true,
      });
      series.setData(
        data.candles.map((c) => ({
          time: c.date as Time,
          value: c.close,
        })),
      );
      mainSeries = series;
    }

    // Volume histogram
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    volumeSeries.setData(
      data.candles.map((c) => ({
        time: c.date as Time,
        value: c.volume,
        color:
          c.close >= c.open
            ? `${colors.money}33`
            : `${colors.red}33`,
      })),
    );

    // Build markers array
    const markers: SeriesMarker<Time>[] = [];

    // Post marker
    if (data.post_date_index != null && data.candles[data.post_date_index]) {
      const postCandle = data.candles[data.post_date_index];
      markers.push({
        time: postCandle.date as Time,
        position: "aboveBar",
        color: colors.red,
        shape: "arrowDown",
        text: "POST",
      });
    }

    // T+N outcome markers
    if (outcome?.marker_dates) {
      const markerConfig: { key: string; label: string; returnKey: keyof typeof outcome.returns }[] = [
        { key: "t1", label: "T+1", returnKey: "t1" },
        { key: "t3", label: "T+3", returnKey: "t3" },
        { key: "t7", label: "T+7", returnKey: "t7" },
        { key: "t30", label: "T+30", returnKey: "t30" },
      ];

      // Build a set of candle dates for quick lookup
      const candleDateSet = new Set(data.candles.map((c) => c.date));

      for (const { key, label, returnKey } of markerConfig) {
        const dateStr = outcome.marker_dates[key];
        const ret = outcome.returns[returnKey];
        if (!dateStr || ret == null) continue;
        // Only add marker if the date exists in the candle data
        if (!candleDateSet.has(dateStr)) continue;

        const sign = ret > 0 ? "+" : "";
        const markerColor = ret > 0 ? colors.money : colors.red;

        markers.push({
          time: dateStr as Time,
          position: "belowBar",
          color: markerColor,
          shape: "circle",
          text: `${label} ${sign}${ret.toFixed(1)}%`,
        });
      }
    }

    // Sort markers by time and apply
    markers.sort((a, b) => (a.time as string).localeCompare(b.time as string));
    if (markers.length > 0) {
      mainSeries.setMarkers(markers);
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, chartType, outcome]);

  if (isLoading) {
    return (
      <div style={{ ...containerStyle, ...loadingStyle }}>
        Loading chart data...
      </div>
    );
  }

  if (!data || data.candles.length === 0) {
    return (
      <div style={{ ...containerStyle, ...loadingStyle }}>
        No price data available for {symbol}
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={toolbarStyle}>
        <div style={toggleGroupStyle}>
          <button
            style={chartType === "candle" ? toggleBtnActive : toggleBtnBase}
            onClick={() => setChartType("candle")}
          >
            Candle
          </button>
          <button
            style={chartType === "line" ? toggleBtnActive : toggleBtnBase}
            onClick={() => setChartType("line")}
          >
            Line
          </button>
        </div>
        <span style={{ fontSize: "0.65rem", color: "var(--text-faint)", fontFamily: "var(--font-mono)" }}>
          {symbol}
        </span>
      </div>
      <div style={{ padding: "8px" }} ref={containerRef} />
    </div>
  );
}
