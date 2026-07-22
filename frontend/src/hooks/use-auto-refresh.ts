import { useEffect, useState } from "react";

/**
 * Hook to auto-refresh data at configurable intervals.
 * Respects user's motion preferences.
 */
export function useAutoRefresh(
  onRefresh: () => void,
  intervalMs: number = 30000,
  enabled: boolean = true
) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    if (!enabled) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    const effectiveInterval = prefersReducedMotion ? intervalMs * 2 : intervalMs;

    const interval = setInterval(() => {
      setIsRefreshing(true);
      onRefresh();
      setTimeout(() => setIsRefreshing(false), 500);
    }, effectiveInterval);

    return () => clearInterval(interval);
  }, [onRefresh, intervalMs, enabled]);

  return { isRefreshing };
}
