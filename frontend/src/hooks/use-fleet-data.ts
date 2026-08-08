import { useEffect, useState } from "react";

export interface FleetData {
  historyEndMs: number;
  health: Array<{
    trainId: string;
    score: number;
    status: "ok" | "watch" | "critical";
    activeAlerts: number;
  }>;
  alerts: Array<{
    id: string;
    trainId: string;
    sensor: string;
    severity: "crit" | "warn";
    detector: string;
    startedTs: number;
    endTs: number;
    active: boolean;
    peak: number;
    recommendation: string;
  }>;
  series: Record<
    string,
    Record<
      string,
      {
        t0: number;
        dt: number;
        mean: number[];
        sev: number[];
        anom: number[];
      }
    >
  >;
  totalSamples: number;
}

export function useFleetData() {
  const [data, setData] = useState<FleetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async (isRefresh = false) => {
    if (!isRefresh) setLoading(true);
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:5000";
      const response = await fetch(`${apiUrl}/api/fleet`);
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const fleetData = (await response.json()) as FleetData;
      setData(fleetData);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch fleet data";
      setError(message);
      console.error("Fleet data fetch error:", err);
      // Fallback: try to use client-side simulation if API fails
      try {
        const { getFleetSimulation } = await import("@/lib/trainwatch/simulation");
        const sim = getFleetSimulation();
        setData(sim);
        setError(null);
      } catch {
        setError(`${message} (fallback also failed)`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return { data, loading, error, refetch: () => fetchData(true) };
}
