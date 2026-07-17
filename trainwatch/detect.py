"""Statistical anomaly detection over the fleet telemetry.

Every (train, sensor) channel is scored independently against a baseline
fitted on the leading ``baseline_days`` of its own history (assumed healthy):

* **Seasonal robust z-score** — the baseline is a median per hour-of-day, so
  the daily duty cycle is not mistaken for a fault; the scale is a pooled
  MAD. Large |z| on a single sample flags a *spike*.
* **EWMA drift tracking** — an exponentially weighted mean of the residual
  with control limits in units of the EWMA's own sigma. Persistent one-sided
  deviation flags a *drift* long before any hard limit is crossed.
* **Stuck-channel check** — a rolling window with (near) zero variance flags
  a frozen transducer, which raw limits would never catch.
* **Engineering limits** — absolute warn/critical thresholds from the sensor
  spec, the conventional SCADA-style guard rails.

The result keeps one row per telemetry sample with its scores, the detectors
that fired (``kinds``) and the worst ``severity`` among them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DETECTION, SENSORS, DetectionConfig

SEVERITY_RANK = {"ok": 0, "warning": 1, "critical": 2}


def _fit_baseline(channel: pd.DataFrame, cfg: DetectionConfig) -> tuple[np.ndarray, float]:
    """Fit hour-of-day medians and a pooled robust sigma on the leading window."""
    t0 = channel["timestamp"].iloc[0]
    base = channel[channel["timestamp"] < t0 + pd.Timedelta(days=cfg.baseline_days)]
    hours = base["timestamp"].dt.hour
    med_by_hour = base.groupby(hours)["value"].median()
    # fall back to the global median for any hour missing from the window
    hourly = np.array([med_by_hour.get(h, base["value"].median()) for h in range(24)])
    residual = base["value"].to_numpy() - hourly[hours.to_numpy()]
    mad = np.median(np.abs(residual - np.median(residual)))
    sigma = max(1.4826 * mad, 1e-6)
    return hourly, sigma


def _ewma(residual: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty_like(residual)
    acc = 0.0
    for i, r in enumerate(residual):
        acc = alpha * r + (1.0 - alpha) * acc
        out[i] = acc
    return out


def _score_channel(channel: pd.DataFrame, cfg: DetectionConfig) -> pd.DataFrame:
    spec = SENSORS[channel["sensor"].iloc[0]]
    values = channel["value"].to_numpy()
    hourly, sigma = _fit_baseline(channel, cfg)
    expected = hourly[channel["timestamp"].dt.hour.to_numpy()]
    residual = values - expected

    zscore = residual / sigma
    ewma = _ewma(residual, cfg.ewma_alpha)
    ewma_sigma = sigma * np.sqrt(cfg.ewma_alpha / (2.0 - cfg.ewma_alpha))
    ewma_score = ewma / ewma_sigma

    n = len(values)
    severity = np.zeros(n, dtype=int)
    kinds: list[set[str]] = [set() for _ in range(n)]

    def raise_to(mask: np.ndarray, level: int, kind: str) -> None:
        severity[mask] = np.maximum(severity[mask], level)
        for i in np.flatnonzero(mask):
            kinds[i].add(kind)

    # stuck channel: rolling variance collapses to zero
    rolled = pd.Series(values).rolling(cfg.stuck_window, min_periods=cfg.stuck_window).std()
    stuck = (rolled <= cfg.stuck_tolerance).to_numpy()
    raise_to(stuck, SEVERITY_RANK["critical"], "stuck")
    live = ~stuck  # a frozen value should not double-report as spike/drift

    raise_to(live & (np.abs(zscore) >= cfg.zscore_warn), SEVERITY_RANK["warning"], "spike")
    raise_to(live & (np.abs(zscore) >= cfg.zscore_crit), SEVERITY_RANK["critical"], "spike")
    raise_to(live & (np.abs(ewma_score) >= cfg.ewma_warn), SEVERITY_RANK["warning"], "drift")
    raise_to(live & (np.abs(ewma_score) >= cfg.ewma_crit), SEVERITY_RANK["critical"], "drift")

    if spec.warn_high is not None:
        raise_to(live & (values >= spec.warn_high), SEVERITY_RANK["warning"], "limit")
    if spec.crit_high is not None:
        raise_to(live & (values >= spec.crit_high), SEVERITY_RANK["critical"], "limit")
    if spec.warn_low is not None:
        raise_to(live & (values <= spec.warn_low), SEVERITY_RANK["warning"], "limit")
    if spec.crit_low is not None:
        raise_to(live & (values <= spec.crit_low), SEVERITY_RANK["critical"], "limit")

    rank_to_name = {v: k for k, v in SEVERITY_RANK.items()}
    out = channel.copy()
    out["expected"] = expected
    out["sigma"] = sigma
    out["zscore"] = zscore
    out["ewma_score"] = ewma_score
    out["severity"] = [rank_to_name[s] for s in severity]
    out["kinds"] = [",".join(sorted(k)) for k in kinds]
    out["anomaly"] = severity > 0
    return out


def detect_anomalies(data: pd.DataFrame, cfg: DetectionConfig = DETECTION) -> pd.DataFrame:
    """Score every channel in the tidy telemetry frame. Returns per-sample results."""
    scored = [
        _score_channel(channel.reset_index(drop=True), cfg)
        for _, channel in data.groupby(["train_id", "sensor"], sort=True)
    ]
    return pd.concat(scored, ignore_index=True)
