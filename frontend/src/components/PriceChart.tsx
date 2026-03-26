import { useEffect, useRef } from "react";
import { CSSProperties } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
} from "lightweight-charts";
import { usePriceData } from "../api/hooks";
import { colors } from "../styles/theme";

const containerStyle: CSSProperties = {
  marginTop: "12px",
  borderRadius: "12px",
  overflow: "hidden",
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  padding: "8px",
  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.06)",
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

    const candleSeries = chart.addCandlestickSeries({
      upColor: colors.money,
      downColor: colors.red,
      wickUpColor: colors.money,
      wickDownColor: colors.red,
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
            ? `${colors.money}33`
            : `${colors.red}33`,
      })),
    );

    // Post marker
    if (data.post_date_index != null && data.candles[data.post_date_index]) {
      const postCandle = data.candles[data.post_date_index];
      candleSeries.setMarkers([
        {
          time: postCandle.date,
          position: "aboveBar",
          color: colors.red,
          shape: "arrowDown",
          text: "POST",
        },
      ]);
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
