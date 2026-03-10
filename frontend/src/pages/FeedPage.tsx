import { useState, useCallback, CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useFeedPost, usePrefetchAdjacentPosts } from "../api/hooks";
import { useKeyboardNav } from "../hooks/useKeyboardNav";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { ShitpostCard } from "../components/ShitpostCard";
import { PredictionPanel } from "../components/PredictionPanel";
import { TickerSelector } from "../components/TickerSelector";
import { MetricBubbles } from "../components/MetricBubbles";
import { TimeframeToggle, timeframeToDays, type Timeframe } from "../components/TimeframeToggle";
import { PriceChart } from "../components/PriceChart";
import { NavigationArrows } from "../components/NavigationArrows";

const mainStyle: CSSProperties = {
  maxWidth: "640px",
  margin: "0 auto",
  padding: "0 16px 24px",
};

const loadingStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "60vh",
  color: "var(--text-muted)",
  gap: "12px",
};

const errorStyle: CSSProperties = {
  ...loadingStyle,
  color: "var(--color-red)",
};

const counterStyle: CSSProperties = {
  textAlign: "center",
  fontSize: "0.7rem",
  color: "var(--text-muted)",
  fontFamily: "var(--font-mono)",
  marginTop: "16px",
};

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 200 : -200,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -200 : 200,
    opacity: 0,
  }),
};

export function FeedPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const offset = parseInt(searchParams.get("offset") ?? "0", 10);
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [timeframe, setTimeframe] = useState<Timeframe>("7d");
  const [direction, setDirection] = useState(0);

  const { data, isLoading, error } = useFeedPost(offset);

  // Prefetch adjacent posts
  usePrefetchAdjacentPosts(
    offset,
    data?.navigation.has_newer ?? false,
    data?.navigation.has_older ?? false,
  );

  const navigateNewer = useCallback(() => {
    if (offset > 0) {
      setDirection(-1);
      setSelectedTicker("");
      setSearchParams({ offset: String(offset - 1) });
    }
  }, [offset, setSearchParams]);

  const navigateOlder = useCallback(() => {
    setDirection(1);
    setSelectedTicker("");
    setSearchParams({ offset: String(offset + 1) });
  }, [offset, setSearchParams]);

  useKeyboardNav(
    navigateNewer,
    navigateOlder,
    data?.navigation.has_newer ?? false,
    data?.navigation.has_older ?? false,
  );

  if (isLoading) {
    return (
      <>
        <Header />
        <div style={loadingStyle}>
          <div className="pulse" style={{ fontSize: "2rem" }}>&#x1F1FA;&#x1F1F8;</div>
          <span>Retrieving intelligence...</span>
        </div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <Header />
        <div style={errorStyle}>
          <div style={{ fontSize: "1.5rem" }}>&#x26A0;</div>
          <span>No intelligence to report, soldier. Stand by.</span>
        </div>
      </>
    );
  }

  // Default to first ticker
  const activeTicker = selectedTicker || data.prediction.assets[0] || "";
  const activeOutcome = data.outcomes.find((o) => o.symbol === activeTicker);

  return (
    <>
      <Header />
      <NavigationArrows
        hasNewer={data.navigation.has_newer}
        hasOlder={data.navigation.has_older}
        onNewer={navigateNewer}
        onOlder={navigateOlder}
      />

      <main style={mainStyle}>
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={data.post.shitpost_id}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            <ShitpostCard post={data.post} />
            <PredictionPanel prediction={data.prediction} />

            {data.prediction.assets.length > 0 && (
              <>
                <TickerSelector
                  tickers={data.prediction.assets}
                  impacts={data.prediction.market_impact}
                  selectedTicker={activeTicker}
                  onSelect={setSelectedTicker}
                />

                <MetricBubbles outcome={activeOutcome} />

                <TimeframeToggle selected={timeframe} onSelect={setTimeframe} />

                {activeTicker && (
                  <PriceChart
                    symbol={activeTicker}
                    days={timeframeToDays[timeframe]}
                    postTimestamp={data.post.timestamp}
                  />
                )}
              </>
            )}
          </motion.div>
        </AnimatePresence>

        <div style={counterStyle}>
          Dispatch {data.navigation.current_offset + 1} of{" "}
          {data.navigation.total_posts}
        </div>
      </main>

      <Footer />
    </>
  );
}
