import { useEffect, useRef } from "react";
import { CSSProperties } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
} from "lightweight-charts";
import { usePriceData } from "../api/hooks";

const containerStyle: CSSProperties = {
  marginTop: "12px",
  borderRadius: "12px",
  overflow: "hidden",
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  padding: "8px",
};

const loadingStyle: CSSProperties = {
  height: "300px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--text-muted)",
  fontSize: "0.85rem",
};

interface Props {
  symbol: string;
  days: number;
  postTimestamp: string;
}

export function PriceChart({ symbol, days, postTimestamp }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const { data, isLoading } = usePriceData(symbol, days, postTimestamp);

  useEffect(() => {
    if (!containerRef.current || !data || data.candles.length === 0) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94A3B8",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 48, 80, 0.4)" },
        horzLines: { color: "rgba(30, 48, 80, 0.4)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: "rgba(30, 48, 80, 0.6)",
      },
      timeScale: {
        borderColor: "rgba(30, 48, 80, 0.6)",
        timeVisible: false,
      },
    });

    // Candlestick series — green up, red down
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22C55E",
      downColor: "#DC2626",
      wickUpColor: "#22C55E",
      wickDownColor: "#DC2626",
      borderVisible: false,
    });

    const candleData = data.candles.map((c) => ({
      time: c.date,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeries.setData(candleData);

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
        time: c.date,
        value: c.volume,
        color:
          c.close >= c.open
            ? "rgba(34, 197, 94, 0.25)"
            : "rgba(220, 38, 38, 0.25)",
      })),
    );

    // Post marker — gold arrow with "POST" label
    if (data.post_date_index != null && data.candles[data.post_date_index]) {
      const postCandle = data.candles[data.post_date_index];
      candleSeries.setMarkers([
        {
          time: postCandle.date,
          position: "aboveBar",
          color: "#FFD700",
          shape: "arrowDown",
          text: "POST",
        },
      ]);
    }

    chart.timeScale().fitContent();
    chartRef.current = chart;

    // Resize handler
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
  }, [data]);

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

  return <div style={containerStyle} ref={containerRef} />;
}
