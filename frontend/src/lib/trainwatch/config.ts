// Mirrors trainwatch/config.py from ctanya-rani/predictive-maintenance.
// Fleet, sensor specs, fault narratives, detector tuning.

export type SensorKey =
  | "axle_bearing_temp_c"
  | "vibration_rms_mm_s"
  | "brake_pressure_bar"
  | "traction_motor_current_a";

export interface SensorSpec {
  key: SensorKey;
  label: string;
  short: string;
  unit: string;
  baseline: number;
  dailyAmplitude: number;
  noiseSd: number;
  warnLow: number | null;
  warnHigh: number | null;
  critLow: number | null;
  critHigh: number | null;
  axisMin: number;
  axisMax: number;
}

export const SENSORS: Record<SensorKey, SensorSpec> = {
  axle_bearing_temp_c: {
    key: "axle_bearing_temp_c",
    label: "Axle bearing temperature",
    short: "Axle temp",
    unit: "°C",
    baseline: 56,
    dailyAmplitude: 9,
    noiseSd: 1.1,
    warnLow: null,
    warnHigh: 85,
    critLow: null,
    critHigh: 95,
    axisMin: 30,
    axisMax: 110,
  },
  vibration_rms_mm_s: {
    key: "vibration_rms_mm_s",
    label: "Bogie vibration (RMS)",
    short: "Vibration",
    unit: "mm/s",
    baseline: 2.1,
    dailyAmplitude: 0.7,
    noiseSd: 0.18,
    warnLow: null,
    warnHigh: 5.5,
    critLow: null,
    critHigh: 8.0,
    axisMin: 0,
    axisMax: 12,
  },
  brake_pressure_bar: {
    key: "brake_pressure_bar",
    label: "Brake pipe pressure",
    short: "Brake press.",
    unit: "bar",
    baseline: 8.6,
    dailyAmplitude: 0.15,
    noiseSd: 0.05,
    warnLow: 7.8,
    warnHigh: null,
    critLow: 7.2,
    critHigh: null,
    axisMin: 6,
    axisMax: 10,
  },
  traction_motor_current_a: {
    key: "traction_motor_current_a",
    label: "Traction motor current",
    short: "Motor current",
    unit: "A",
    baseline: 310,
    dailyAmplitude: 70,
    noiseSd: 12,
    warnLow: null,
    warnHigh: 520,
    critLow: null,
    critHigh: 600,
    axisMin: 100,
    axisMax: 650,
  },
};

export const SENSOR_KEYS: SensorKey[] = [
  "axle_bearing_temp_c",
  "vibration_rms_mm_s",
  "brake_pressure_bar",
  "traction_motor_current_a",
];

export const TRAIN_IDS: string[] = Array.from({ length: 8 }, (_, i) => `T-${101 + i}`);

export const SAMPLE_MINUTES = 30;
export const DAYS = 14;
export const RANDOM_SEED = 20260717;

export interface FaultSpec {
  trainId: string;
  sensor: SensorKey;
  kind: "drift" | "spikes" | "stuck";
  startDay: number;
  magnitude: number;
  description: string;
}

export const FAULTS: FaultSpec[] = [
  {
    trainId: "T-103",
    sensor: "axle_bearing_temp_c",
    kind: "drift",
    startDay: 8.0,
    magnitude: 42.0,
    description:
      "Progressive axle bearing wear — temperature ramps toward the critical limit.",
  },
  {
    trainId: "T-105",
    sensor: "vibration_rms_mm_s",
    kind: "spikes",
    startDay: 10.5,
    magnitude: 7.5,
    description:
      "Wheel flat developing — intermittent high-energy vibration bursts.",
  },
  {
    trainId: "T-102",
    sensor: "brake_pressure_bar",
    kind: "drift",
    startDay: 9.0,
    magnitude: -1.6,
    description:
      "Slow brake pipe air leak — pressure decays below the warning limit.",
  },
  {
    trainId: "T-107",
    sensor: "traction_motor_current_a",
    kind: "stuck",
    startDay: 12.0,
    magnitude: 0.0,
    description:
      "Current transducer failure — the channel flatlines while the train keeps running.",
  },
];

export const RECOMMENDATIONS: Record<string, string> = {
  "axle_bearing_temp_c:drift":
    "Schedule bearing inspection; monitor temp trend, plan replacement within 48h.",
  "vibration_rms_mm_s:spikes":
    "Wheel lathe inspection recommended — check for wheel flat or bogie damage.",
  "brake_pressure_bar:drift":
    "Isolate train and pressure-test the brake pipe for leaks before next revenue service.",
  "traction_motor_current_a:stuck":
    "Replace or recalibrate the current transducer — traction telemetry is unreliable.",
};
