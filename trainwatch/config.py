"""Fleet, sensor, and detection configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    """Physical behaviour and engineering limits of one sensor channel."""

    key: str
    label: str
    unit: str
    baseline: float          # healthy operating level
    daily_amplitude: float   # peak deviation from the duty cycle (peak service hours)
    noise_sd: float          # gaussian measurement noise
    warn_low: float | None
    warn_high: float | None
    crit_low: float | None
    crit_high: float | None
    # y-axis window for charts
    axis_min: float = 0.0
    axis_max: float = 100.0


SENSORS: dict[str, SensorSpec] = {
    spec.key: spec
    for spec in [
        SensorSpec(
            key="axle_bearing_temp_c",
            label="Axle bearing temperature",
            unit="°C",
            baseline=56.0,
            daily_amplitude=9.0,
            noise_sd=1.1,
            warn_low=None,
            warn_high=85.0,
            crit_low=None,
            crit_high=95.0,
            axis_min=30.0,
            axis_max=110.0,
        ),
        SensorSpec(
            key="vibration_rms_mm_s",
            label="Bogie vibration (RMS)",
            unit="mm/s",
            baseline=2.1,
            daily_amplitude=0.7,
            noise_sd=0.18,
            warn_low=None,
            warn_high=5.5,
            crit_low=None,
            crit_high=8.0,
            axis_min=0.0,
            axis_max=12.0,
        ),
        SensorSpec(
            key="brake_pressure_bar",
            label="Brake pipe pressure",
            unit="bar",
            baseline=8.6,
            daily_amplitude=0.15,
            noise_sd=0.05,
            warn_low=7.8,
            warn_high=None,
            crit_low=7.2,
            crit_high=None,
            axis_min=6.0,
            axis_max=10.0,
        ),
        SensorSpec(
            key="traction_motor_current_a",
            label="Traction motor current",
            unit="A",
            baseline=310.0,
            daily_amplitude=70.0,
            noise_sd=12.0,
            warn_low=None,
            warn_high=520.0,
            crit_low=None,
            crit_high=600.0,
            axis_min=100.0,
            axis_max=650.0,
        ),
    ]
}

TRAIN_IDS: list[str] = [f"T-{n}" for n in range(101, 109)]

SAMPLE_MINUTES = 10          # telemetry cadence
DAYS = 14                    # length of the synthetic history
RANDOM_SEED = 20260717


@dataclass(frozen=True)
class FaultSpec:
    """A fault pattern injected into one train/sensor channel."""

    train_id: str
    sensor: str
    kind: str        # "drift" | "spikes" | "stuck"
    start_day: float # day offset (0-based) when the fault begins
    magnitude: float # drift: total added by history end; spikes: peak amplitude
    description: str = ""


# The seeded failure narrative for the synthetic fleet.
FAULTS: list[FaultSpec] = [
    FaultSpec(
        train_id="T-103",
        sensor="axle_bearing_temp_c",
        kind="drift",
        start_day=8.0,
        magnitude=42.0,
        description="Progressive axle bearing wear — temperature ramps toward the critical limit.",
    ),
    FaultSpec(
        train_id="T-105",
        sensor="vibration_rms_mm_s",
        kind="spikes",
        start_day=10.5,
        magnitude=7.5,
        description="Wheel flat developing — intermittent high-energy vibration bursts.",
    ),
    FaultSpec(
        train_id="T-102",
        sensor="brake_pressure_bar",
        kind="drift",
        start_day=9.0,
        magnitude=-1.6,
        description="Slow brake pipe air leak — pressure decays below the warning limit.",
    ),
    FaultSpec(
        train_id="T-107",
        sensor="traction_motor_current_a",
        kind="stuck",
        start_day=12.0,
        magnitude=0.0,
        description="Current transducer failure — the channel flatlines while the train keeps running.",
    ),
]


@dataclass(frozen=True)
class DetectionConfig:
    """Tuning for the statistical detectors (see detect.py)."""

    baseline_days: float = 5.0     # leading window assumed healthy, used to fit baselines
    zscore_warn: float = 4.0       # robust |z| that flags a warning spike
    zscore_crit: float = 7.0
    ewma_alpha: float = 0.05       # smoothing for the drift tracker
    ewma_warn: float = 4.0         # EWMA deviation, in baseline sigmas
    ewma_crit: float = 8.0
    stuck_window: int = 18         # samples (3 h) over which zero variance means "stuck"
    stuck_tolerance: float = 1e-9


DETECTION = DetectionConfig()
