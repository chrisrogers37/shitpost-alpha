import { useEffect, useState } from "react";
import { relativeTime } from "../utils/time";

/** Returns a ticking relative time string that updates every 30 seconds. */
export function useRelativeTime(timestamp: string): string {
  const [display, setDisplay] = useState(() => relativeTime(timestamp));

  useEffect(() => {
    setDisplay(relativeTime(timestamp));
    const interval = setInterval(() => setDisplay(relativeTime(timestamp)), 30_000);
    return () => clearInterval(interval);
  }, [timestamp]);

  return display;
}
