"""Synthetic train telemetry generator.

Produces a tidy DataFrame with columns:
    timestamp, train_id, sensor, value

Healthy behaviour is a daily duty cycle (trains work harder in peak service
hours) plus per-train character offsets and gaussian noise. Faults from
``config.FAULTS`` are then layered on top:

* ``drift``  — a slow ramp that accelerates quadratically, the signature of
  progressive wear (bearing heating up, air leak worsening).
* ``spikes`` — intermittent short bursts, the signature of a wheel flat or
  loose component; burst probability grows as the fault ages.
* ``stuck``  — the channel freezes at its last healthy value: sensor failure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DAYS, FAULTS, RANDOM_SEED, SAMPLE_MINUTES, SENSORS, TRAIN_IDS, FaultSpec

SAMPLES_PER_DAY = 24 * 60 // SAMPLE_MINUTES


def _duty_cycle(hours: np.ndarray) -> np.ndarray:
    """Load factor in [0, 1]: overnight lull, morning and evening peaks."""
    morning = np.exp(-0.5 * ((hours % 24 - 8.0) / 2.2) ** 2)
    evening = np.exp(-0.5 * ((hours % 24 - 17.5) / 2.6) ** 2)
    base = 0.25 + 0.75 * np.clip(morning + evening, 0.0, 1.0)
    return base


def _healthy_channel(
    rng: np.random.Generator, spec_key: str, hours: np.ndarray, train_offset: float
) -> np.ndarray:
    spec = SENSORS[spec_key]
    load = _duty_cycle(hours)
    values = spec.baseline + train_offset + spec.daily_amplitude * (load - 0.5)
    values += rng.normal(0.0, spec.noise_sd, size=hours.shape)
    return values


def _apply_fault(
    rng: np.random.Generator, values: np.ndarray, hours: np.ndarray, fault: FaultSpec
) -> np.ndarray:
    start_h = fault.start_day * 24.0
    total_h = hours[-1]
    active = hours >= start_h
    if not active.any():
        return values
    # age in [0, 1] over the faulty tail of the history
    age = np.zeros_like(hours)
    age[active] = (hours[active] - start_h) / max(total_h - start_h, 1e-9)

    out = values.copy()
    if fault.kind == "drift":
        out += fault.magnitude * age**2  # wear accelerates
    elif fault.kind == "spikes":
        p_burst = 0.02 + 0.10 * age  # bursts get more frequent as the flat grows
        bursts = active & (rng.random(hours.shape) < p_burst)
        amplitudes = fault.magnitude * (0.4 + 0.6 * rng.random(hours.shape)) * (0.5 + 0.5 * age)
        out[bursts] += amplitudes[bursts]
    elif fault.kind == "stuck":
        first = int(np.argmax(active))
        out[first:] = out[first]
    else:  # pragma: no cover - config error
        raise ValueError(f"unknown fault kind: {fault.kind}")
    return out


def generate_fleet_data(
    days: int = DAYS,
    train_ids: list[str] | None = None,
    seed: int = RANDOM_SEED,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Generate the full synthetic telemetry history for the fleet."""
    train_ids = train_ids if train_ids is not None else TRAIN_IDS
    rng = np.random.default_rng(seed)

    n = days * SAMPLES_PER_DAY
    end = end if end is not None else pd.Timestamp.now().floor(f"{SAMPLE_MINUTES}min")
    timestamps = pd.date_range(end=end, periods=n, freq=f"{SAMPLE_MINUTES}min")
    hours = ((timestamps - timestamps[0]).total_seconds() / 3600.0).to_numpy()

    faults_by_channel = {(f.train_id, f.sensor): f for f in FAULTS}

    frames: list[pd.DataFrame] = []
    for train_id in train_ids:
        for sensor_key, spec in SENSORS.items():
            # each train has its own stable character (slightly hotter, noisier...)
            train_offset = rng.normal(0.0, spec.noise_sd * 1.5)
            values = _healthy_channel(rng, sensor_key, hours, train_offset)
            fault = faults_by_channel.get((train_id, sensor_key))
            if fault is not None:
                values = _apply_fault(rng, values, hours, fault)
            frames.append(
                pd.DataFrame(
                    {
                        "timestamp": timestamps,
                        "train_id": train_id,
                        "sensor": sensor_key,
                        "value": values,
                    }
                )
            )

    data = pd.concat(frames, ignore_index=True)
    return data.sort_values(["train_id", "sensor", "timestamp"], ignore_index=True)
