import { useEffect, useRef } from "react";

/**
 * Call `callback` immediately and then every `intervalMs` milliseconds.
 * Pass `enabled: false` to pause (e.g. once a game is finished).
 */
export function usePolling(callback: () => void, intervalMs: number, enabled = true): void {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (!enabled) return;
    saved.current();
    const id = window.setInterval(() => saved.current(), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
}
