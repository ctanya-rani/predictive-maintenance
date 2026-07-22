import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ComposedChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SENSORS, type SensorKey } from "@/lib/trainwatch/config";
import type { SamplePoint } from "@/lib/trainwatch/simulation";

interface Props {
  sensor: SensorKey;
  points: SamplePoint[];
  historyEndMs: number;
  windowDays: number;
}

const dayMs = 24 * 60 * 60 * 1000;

function formatTs(ms: number, historyEndMs: number) {
  const daysAgo = (historyEndMs - ms) / dayMs;
  if (daysAgo < 1) return `-${(daysAgo * 24).toFixed(0)}h`;
  return `-${daysAgo.toFixed(1)}d`;
}

export function SensorChart({ sensor, points, historyEndMs, windowDays }: Props) {
  const spec = SENSORS[sensor];
  const cutoff = historyEndMs - windowDays * dayMs;
  const windowed = points.filter((p) => p.t >= cutoff);

  // decimate for performance if window is long
  const step = Math.max(1, Math.floor(windowed.length / 400));
  const chartData = windowed
    .filter((_, i) => i % step === 0)
    .map((p) => ({
      t: p.t,
      value: p.value,
      warn: p.anomaly === "warn" ? p.value : null,
      crit: p.anomaly === "crit" ? p.value : null,
    }));

  const anomalies = windowed.filter((p) => p.anomaly);
  const critCount = anomalies.filter((a) => a.anomaly === "crit").length;

  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{spec.label}</div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {spec.key} · {spec.unit}
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <Badge tone="watch">{anomalies.length - critCount} warn</Badge>
          <Badge tone="crit">{critCount} crit</Badge>
        </div>
      </div>
      <div className="h-56 w-full">
        <ResponsiveContainer>
          <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid stroke="var(--grid)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={[cutoff, historyEndMs]}
              tickFormatter={(v) => formatTs(v as number, historyEndMs)}
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
            />
            <YAxis
              domain={[spec.axisMin, spec.axisMax]}
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
              width={44}
            />
            {spec.warnHigh !== null && (
              <ReferenceLine y={spec.warnHigh} stroke="var(--watch)" strokeDasharray="4 4" />
            )}
            {spec.critHigh !== null && (
              <ReferenceLine y={spec.critHigh} stroke="var(--critical)" strokeDasharray="4 4" />
            )}
            {spec.warnLow !== null && (
              <ReferenceLine y={spec.warnLow} stroke="var(--watch)" strokeDasharray="4 4" />
            )}
            {spec.critLow !== null && (
              <ReferenceLine y={spec.critLow} stroke="var(--critical)" strokeDasharray="4 4" />
            )}
            <Tooltip
              contentStyle={{
                background: "var(--panel)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 12,
              }}
              labelFormatter={(v) => formatTs(v as number, historyEndMs)}
              formatter={(v: number) => [`${v.toFixed(2)} ${spec.unit}`, spec.label]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--primary)"
              strokeWidth={1.4}
              dot={false}
              isAnimationActive={false}
            />
            <Scatter dataKey="warn" fill="var(--watch)" shape="circle" />
            <Scatter dataKey="crit" fill="var(--critical)" shape="circle" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Badge({ tone, children }: { tone: "watch" | "crit"; children: React.ReactNode }) {
  const cls =
    tone === "crit"
      ? "border-critical/40 text-critical bg-critical/10"
      : "border-watch/40 text-watch bg-watch/10";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${cls}`}
    >
      {children}
    </span>
  );
}
