// Client-side synthetic telemetry + anomaly detection + alerts.
// Mirrors the spirit of trainwatch/{generate,detect,alerts}.py.
// Deterministic — same seed always produces the same fleet.

import {
  DAYS,
  FAULTS,
  RANDOM_SEED,
  RECOMMENDATIONS,
  SAMPLE_MINUTES,
  SENSOR_KEYS,
  SENSORS,
  TRAIN_IDS,
  type SensorKey,
} from "./config";

// -------- deterministic PRNG (mulberry32) --------

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Box-Muller normal draw from a uniform rng
function normal(rng: () => number, mean = 0, sd = 1) {
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// -------- data shapes --------

export interface SamplePoint {
  t: number; // ms since epoch (relative)
  hour: number; // hour-of-day 0..24
  value: number;
  anomaly: null | "warn" | "crit";
  detector: null | "spike" | "drift" | "stuck" | "limit";
}

export interface TrainSensorSeries {
  trainId: string;
  sensor: SensorKey;
  points: SamplePoint[];
}

export interface AlertEpisode {
  id: string;
  trainId: string;
  sensor: SensorKey;
  detector: "spike" | "drift" | "stuck" | "limit";
  severity: "warn" | "crit";
  startTs: number;
  endTs: number;
  peak: number;
  recommendation: string;
}

export interface TrainHealth {
  trainId: string;
  score: number; // 0..100
  status: "ok" | "watch" | "critical";
  activeAlerts: number;
  worstSensor: SensorKey | null;
}

export interface FleetSimulation {
  generatedAtIso: string;
  historyStartMs: number;
  historyEndMs: number;
  series: Map<string, TrainSensorSeries>; // key: `${trainId}:${sensor}`
  alerts: AlertEpisode[];
  health: TrainHealth[];
  totalSamples: number;
}

// -------- generator --------

function dutyCycle(hour: number): number {
  // Morning + evening peaks approximated with two gaussians on hour-of-day.
  const morning = Math.exp(-((hour - 8) ** 2) / (2 * 1.6 ** 2));
  const evening = Math.exp(-((hour - 18) ** 2) / (2 * 1.8 ** 2));
  return Math.max(0, morning + evening * 0.9 - 0.05);
}

function generateSeries(
  trainId: string,
  sensor: SensorKey,
  rng: () => number,
): SamplePoint[] {
  const spec = SENSORS[sensor];
  const totalSamples = (DAYS * 24 * 60) / SAMPLE_MINUTES;
  const dtMs = SAMPLE_MINUTES * 60 * 1000;
  const trainOffset = (parseInt(trainId.slice(2), 10) - 101 - 3.5) * spec.noiseSd * 0.9;

  const fault = FAULTS.find((f) => f.trainId === trainId && f.sensor === sensor);
  const points: SamplePoint[] = [];
  let stuckValue: number | null = null;
  let spikeCooldown = 0;

  for (let i = 0; i < totalSamples; i++) {
    const t = i * dtMs;
    const day = i / (totalSamples / DAYS);
    const hour = (day - Math.floor(day)) * 24;
    const duty = dutyCycle(hour);
    let value = spec.baseline + trainOffset + duty * spec.dailyAmplitude + normal(rng, 0, spec.noiseSd);

    if (fault) {
      const daysSince = day - fault.startDay;
      if (daysSince > 0) {
        if (fault.kind === "drift") {
          const totalDays = DAYS - fault.startDay;
          const frac = Math.min(1, daysSince / totalDays);
          value += fault.magnitude * Math.pow(frac, 1.2);
        } else if (fault.kind === "spikes") {
          spikeCooldown -= 1;
          if (spikeCooldown <= 0 && rng() < 0.09) {
            value += fault.magnitude * (0.7 + rng() * 0.6);
            spikeCooldown = 3 + Math.floor(rng() * 6);
          }
        } else if (fault.kind === "stuck") {
          if (stuckValue === null) stuckValue = value;
          value = stuckValue;
        }
      }
    }

    points.push({ t, hour, value, anomaly: null, detector: null });
  }
  return points;
}

// -------- detection --------

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) return 0;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

function detectSeries(points: SamplePoint[], sensor: SensorKey): void {
  const spec = SENSORS[sensor];
  const baselineSamples = Math.floor((5 / DAYS) * points.length); // ~5 days
  const baselineSlice = points.slice(0, baselineSamples).map((p) => p.value);
  const baseMedian = median(baselineSlice);
  const baseMad =
    median(baselineSlice.map((v) => Math.abs(v - baseMedian))) * 1.4826 || spec.noiseSd;

  // hourly medians for seasonal z-score
  const byHour: Record<number, number[]> = {};
  points.slice(0, baselineSamples).forEach((p) => {
    const hb = Math.floor(p.hour);
    (byHour[hb] ??= []).push(p.value);
  });
  const hourMed: Record<number, number> = {};
  for (let h = 0; h < 24; h++) hourMed[h] = median(byHour[h] ?? baselineSlice);

  // EWMA drift tracker
  let ewma = baseMedian;
  const alpha = 0.05;

  // stuck-channel rolling variance
  const stuckWindow = 8;
  const recent: number[] = [];

  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    const hb = Math.floor(p.hour);
    const seasonalDelta = p.value - hourMed[hb];
    const z = Math.abs(seasonalDelta) / baseMad;

    ewma = alpha * p.value + (1 - alpha) * ewma;
    const drift = Math.abs(ewma - baseMedian) / baseMad;

    recent.push(p.value);
    if (recent.length > stuckWindow) recent.shift();
    const meanR = recent.reduce((s, v) => s + v, 0) / recent.length;
    const varR = recent.reduce((s, v) => s + (v - meanR) ** 2, 0) / recent.length;
    const stuck = i >= stuckWindow && varR < 1e-6;

    // engineering limits
    let limitHit: "warn" | "crit" | null = null;
    if (spec.critHigh !== null && p.value >= spec.critHigh) limitHit = "crit";
    else if (spec.critLow !== null && p.value <= spec.critLow) limitHit = "crit";
    else if (spec.warnHigh !== null && p.value >= spec.warnHigh) limitHit = "warn";
    else if (spec.warnLow !== null && p.value <= spec.warnLow) limitHit = "warn";

    if (stuck) {
      p.anomaly = "crit";
      p.detector = "stuck";
    } else if (limitHit === "crit") {
      p.anomaly = "crit";
      p.detector = "limit";
    } else if (z >= 7) {
      p.anomaly = "crit";
      p.detector = "spike";
    } else if (drift >= 8) {
      p.anomaly = "crit";
      p.detector = "drift";
    } else if (limitHit === "warn") {
      p.anomaly = "warn";
      p.detector = "limit";
    } else if (z >= 4) {
      p.anomaly = "warn";
      p.detector = "spike";
    } else if (drift >= 4) {
      p.anomaly = "warn";
      p.detector = "drift";
    }
  }
}

// -------- alert episode merging --------

function buildAlerts(series: TrainSensorSeries[]): AlertEpisode[] {
  const alerts: AlertEpisode[] = [];
  const dtMs = SAMPLE_MINUTES * 60 * 1000;
  for (const s of series) {
    let active: AlertEpisode | null = null;
    let gap = 0;
    const rec =
      RECOMMENDATIONS[`${s.sensor}:${s.points.find((p) => p.detector)?.detector ?? ""}`] ??
      "Review sensor readings and cross-check with maintenance history.";
    for (const p of s.points) {
      if (p.anomaly) {
        if (!active) {
          active = {
            id: `${s.trainId}-${s.sensor}-${p.t}`,
            trainId: s.trainId,
            sensor: s.sensor,
            detector: p.detector!,
            severity: p.anomaly,
            startTs: p.t,
            endTs: p.t,
            peak: p.value,
            recommendation:
              RECOMMENDATIONS[`${s.sensor}:${p.detector}`] ?? rec,
          };
        } else {
          active.endTs = p.t;
          if (p.anomaly === "crit") active.severity = "crit";
          if (Math.abs(p.value - SENSORS[s.sensor].baseline) > Math.abs(active.peak - SENSORS[s.sensor].baseline))
            active.peak = p.value;
        }
        gap = 0;
      } else if (active) {
        gap += dtMs;
        // flicker-bridge: allow up to 90 min gap
        if (gap > 90 * 60 * 1000) {
          alerts.push(active);
          active = null;
          gap = 0;
        }
      }
    }
    if (active) alerts.push(active);
  }
  return alerts.sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === "crit" ? -1 : 1;
    return b.startTs - a.startTs;
  });
}

function computeHealth(alerts: AlertEpisode[], historyEnd: number): TrainHealth[] {
  const byTrain: Record<string, AlertEpisode[]> = {};
  for (const id of TRAIN_IDS) byTrain[id] = [];
  for (const a of alerts) byTrain[a.trainId].push(a);

  return TRAIN_IDS.map((trainId) => {
    const list = byTrain[trainId];
    let score = 100;
    let worst: SensorKey | null = null;
    let worstPenalty = 0;
    const sensorCounts: Record<string, number> = {};
    for (const a of list) {
      const recent = historyEnd - a.endTs < 24 * 60 * 60 * 1000;
      const base = a.severity === "crit" ? (recent ? 32 : 14) : recent ? 10 : 4;
      const rep = sensorCounts[a.sensor] ?? 0;
      const penalty = base * Math.pow(0.65, rep);
      score -= penalty;
      if (penalty > worstPenalty) {
        worstPenalty = penalty;
        worst = a.sensor;
      }
      sensorCounts[a.sensor] = rep + 1;
    }
    score = Math.max(0, Math.round(score));
    const status: TrainHealth["status"] =
      score < 55 ? "critical" : score < 82 ? "watch" : "ok";
    return {
      trainId,
      score,
      status,
      activeAlerts: list.filter((a) => historyEnd - a.endTs < 24 * 60 * 60 * 1000).length,
      worstSensor: worst,
    };
  }).sort((a, b) => a.score - b.score);
}

// -------- top-level --------

let cached: FleetSimulation | null = null;

export function getFleetSimulation(): FleetSimulation {
  if (cached) return cached;

  const rng = mulberry32(RANDOM_SEED);
  const series = new Map<string, TrainSensorSeries>();
  let total = 0;

  for (const trainId of TRAIN_IDS) {
    for (const sensor of SENSOR_KEYS) {
      const points = generateSeries(trainId, sensor, rng);
      detectSeries(points, sensor);
      const key = `${trainId}:${sensor}`;
      series.set(key, { trainId, sensor, points });
      total += points.length;
    }
  }

  const allSeries = Array.from(series.values());
  const alerts = buildAlerts(allSeries);
  const dtMs = SAMPLE_MINUTES * 60 * 1000;
  const totalPerSeries = allSeries[0]?.points.length ?? 0;
  const historyEndMs = totalPerSeries * dtMs;
  const health = computeHealth(alerts, historyEndMs);

  cached = {
    generatedAtIso: new Date().toISOString(),
    historyStartMs: 0,
    historyEndMs,
    series,
    alerts,
    health,
    totalSamples: total,
  };
  return cached;
}

export function getSeries(trainId: string, sensor: SensorKey): TrainSensorSeries {
  return getFleetSimulation().series.get(`${trainId}:${sensor}`)!;
}
