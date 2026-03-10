/** Keyboard navigation hook — ArrowLeft/ArrowRight to navigate posts. */

import { useEffect } from "react";

export function useKeyboardNav(
  onNewer: () => void,
  onOlder: () => void,
  hasNewer: boolean,
  hasOlder: boolean,
) {
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" && hasNewer) {
        e.preventDefault();
        onNewer();
      }
      if (e.key === "ArrowRight" && hasOlder) {
        e.preventDefault();
        onOlder();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onNewer, onOlder, hasNewer, hasOlder]);
}
