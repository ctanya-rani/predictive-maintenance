import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AlertTriangle, ChevronRight, Gauge, TrainFront, Waves } from "lucide-react";

import { Shell } from "@/components/trainwatch/Shell";
import { SensorChart } from "@/components/trainwatch/SensorChart";
import { SENSORS, SENSOR_KEYS, type SensorKey } from "@/lib/trainwatch/config";
import { getFleetSimulation } from "@/lib/trainwatch/simulation";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Fleet console · TrainWatch" },
      {
        name: "description",
        content:
          "Predictive maintenance fleet console: health scores, anomaly-flagged sensor charts and alert feed for 8 synthetic trains.",
      },
      { property: "og:title", content: "Fleet console · TrainWatch" },
      {
        property: "og:description",
        content:
          "Fleet health, anomaly-flagged sensor charts and alert feed for 8 synthetic trains.",
      },
    ],
  }),
  component: FleetConsole,
});

const RANGE_OPTIONS = [
  { label: "24h", days: 1 },
  { label: "3d", days: 3 },
  { label: "7d", days: 7 },
  { label: "14d", days: 14 },
] as const;

function statusStyles(status: "ok" | "watch" | "critical") {
  if (status === "critical")
    return {
      dot: "bg-critical",
      text: "text-critical",
      ring: "border-critical/40 bg-critical/10",
      label: "CRITICAL",
    };
  if (status === "watch")
    return {
      dot: "bg-watch",
      text: "text-watch",
      ring: "border-watch/40 bg-watch/10",
      label: "WATCH",
    };
  return {
    dot: "bg-ok",
    text: "text-ok",
    ring: "border-ok/40 bg-ok/10",
    label: "NOMINAL",
  };
}

function FleetConsole() {
  const sim = useMemo(() => getFleetSimulation(), []);
  const worst = sim.health[0];
  const [selectedId, setSelectedId] = useState<string>(worst?.trainId ?? "T-101");
  const [windowDays, setWindowDays] = useState<number>(3);

  const selectedHealth = sim.health.find((h) => h.trainId === selectedId)!;
  const selectedAlerts = sim.alerts.filter((a) => a.trainId === selectedId);

  const fleetStats = useMemo(() => {
    const criticals = sim.health.filter((h) => h.status === "critical").length;
    const watch = sim.health.filter((h) => h.status === "watch").length;
    const openAlerts = sim.alerts.filter(
      (a) => sim.historyEndMs - a.endTs < 24 * 60 * 60 * 1000,
    );
    const avg =
      sim.health.reduce((s, h) => s + h.score, 0) / (sim.health.length || 1);
    return {
      trains: sim.health.length,
      criticals,
      watch,
      openAlerts: openAlerts.length,
      criticalAlerts: openAlerts.filter((a) => a.severity === "crit").length,
      avgScore: Math.round(avg),
      samples: sim.totalSamples,
    };
  }, [sim]);

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Console · 8 trains · 14-day synthetic history
          </div>
          <h1 className="mt-1 text-2xl font-semibold">Fleet health</h1>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border bg-panel p-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              onClick={() => setWindowDays(opt.days)}
              className={`rounded px-3 py-1 font-mono text-xs uppercase tracking-wider transition ${
                windowDays === opt.days
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile
          icon={<TrainFront className="h-4 w-4" />}
          label="Fleet"
          value={`${fleetStats.trains}`}
          hint={`${fleetStats.samples.toLocaleString()} samples`}
        />
        <StatTile
          icon={<Gauge className="h-4 w-4" />}
          label="Avg health"
          value={`${fleetStats.avgScore}`}
          hint="0 – 100"
          tone={fleetStats.avgScore < 70 ? "watch" : "ok"}
        />
        <StatTile
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Open alerts"
          value={`${fleetStats.openAlerts}`}
          hint={`${fleetStats.criticalAlerts} critical`}
          tone={fleetStats.criticalAlerts > 0 ? "crit" : "watch"}
        />
        <StatTile
          icon={<Waves className="h-4 w-4" />}
          label="At risk"
          value={`${fleetStats.criticals + fleetStats.watch}`}
          hint={`${fleetStats.criticals} critical · ${fleetStats.watch} watch`}
          tone={fleetStats.criticals > 0 ? "crit" : "watch"}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Train list */}
        <aside className="rounded-lg border border-border bg-panel">
          <div className="border-b border-border px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Trains · worst first
            </div>
          </div>
          <ul>
            {sim.health.map((h) => {
              const s = statusStyles(h.status);
              const active = h.trainId === selectedId;
              return (
                <li key={h.trainId}>
                  <button
                    onClick={() => setSelectedId(h.trainId)}
                    className={`flex w-full items-center gap-3 border-b border-border px-4 py-3 text-left transition hover:bg-muted/40 ${
                      active ? "bg-muted/60" : ""
                    }`}
                  >
                    <span className={`inline-block h-2 w-2 rounded-full ${s.dot}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-sm font-semibold">
                          {h.trainId}
                        </span>
                        <span className={`font-mono text-xs ${s.text}`}>
                          {h.score}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span className="font-mono uppercase tracking-wider">
                          {s.label}
                        </span>
                        <span>
                          {h.activeAlerts > 0 ? `${h.activeAlerts} open` : "—"}
                        </span>
                      </div>
                      <div className="mt-1.5 h-1 overflow-hidden rounded bg-muted">
                        <div
                          className={`h-full ${
                            h.status === "critical"
                              ? "bg-critical"
                              : h.status === "watch"
                                ? "bg-watch"
                                : "bg-ok"
                          }`}
                          style={{ width: `${h.score}%` }}
                        />
                      </div>
                    </div>
                    <ChevronRight
                      className={`h-4 w-4 shrink-0 text-muted-foreground transition ${
                        active ? "translate-x-0.5 text-foreground" : ""
                      }`}
                    />
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        {/* Selected train detail */}
        <section>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Train detail
              </div>
              <h2 className="mt-1 flex items-baseline gap-3 text-xl font-semibold">
                <span className="font-mono">{selectedId}</span>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
                    statusStyles(selectedHealth.status).ring
                  } ${statusStyles(selectedHealth.status).text}`}
                >
                  {statusStyles(selectedHealth.status).label} · {selectedHealth.score}
                </span>
              </h2>
            </div>
            <div className="font-mono text-xs text-muted-foreground">
              {selectedAlerts.length} episodes · window {windowDays}d
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {SENSOR_KEYS.map((s) => (
              <SensorChart
                key={s}
                sensor={s}
                points={sim.series.get(`${selectedId}:${s}`)!.points}
                historyEndMs={sim.historyEndMs}
                windowDays={windowDays}
              />
            ))}
          </div>

          <div className="mt-6 rounded-lg border border-border bg-panel">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <div className="text-sm font-semibold">Alert feed</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  Fleet · sorted by severity
                </div>
              </div>
              <span className="font-mono text-xs text-muted-foreground">
                {sim.alerts.length} total
              </span>
            </div>
            <ul className="divide-y divide-border">
              {sim.alerts.slice(0, 12).map((a) => {
                const isSel = a.trainId === selectedId;
                return (
                  <li
                    key={a.id}
                    className={`px-4 py-3 text-sm ${isSel ? "bg-muted/40" : ""}`}
                  >
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
                          a.severity === "crit"
                            ? "border-critical/40 bg-critical/10 text-critical"
                            : "border-watch/40 bg-watch/10 text-watch"
                        }`}
                      >
                        {a.severity === "crit" ? "critical" : "warn"}
                      </span>
                      <span className="font-mono font-semibold">{a.trainId}</span>
                      <span className="text-muted-foreground">
                        {SENSORS[a.sensor].label}
                      </span>
                      <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                        detector: {a.detector}
                      </span>
                      <span className="ml-auto font-mono text-xs text-muted-foreground">
                        peak {a.peak.toFixed(2)} {SENSORS[a.sensor].unit}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      {a.recommendation}
                    </p>
                  </li>
                );
              })}
              {sim.alerts.length === 0 && (
                <li className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No anomalies detected across the fleet.
                </li>
              )}
            </ul>
          </div>
        </section>
      </div>
    </Shell>
  );
}

function StatTile({
  icon,
  label,
  value,
  hint,
  tone = "ok",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  tone?: "ok" | "watch" | "crit";
}) {
  const toneCls =
    tone === "crit" ? "text-critical" : tone === "watch" ? "text-watch" : "text-primary";
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className={`flex items-center gap-1.5 ${toneCls}`}>
        {icon}
        <span className="font-mono text-[10px] uppercase tracking-[0.2em]">
          {label}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold tabular">{value}</span>
        {hint && (
          <span className="font-mono text-[11px] text-muted-foreground">{hint}</span>
        )}
      </div>
    </div>
  );
}
