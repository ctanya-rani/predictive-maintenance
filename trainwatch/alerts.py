"""Turn per-sample anomaly flags into deduplicated alerts and health scores.

Consecutive anomalous samples on the same channel are merged into one
*episode* (gaps up to ``MERGE_GAP`` are bridged so a flickering detector does
not spam the feed). Each episode becomes a single alert carrying its worst
severity, dominant detector, time span, peak reading and a maintenance
recommendation. Alerts still firing at the end of the history are *active*.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import SENSORS
from .detect import SEVERITY_RANK

MERGE_GAP = pd.Timedelta(hours=1)   # bridge flicker shorter than this
ACTIVE_WINDOW = pd.Timedelta(hours=2)  # still firing this close to "now" = active

RECOMMENDATIONS = {
    ("axle_bearing_temp_c", "drift"): "Schedule bearing inspection; check lubrication and plan replacement before the critical limit.",
    ("axle_bearing_temp_c", "limit"): "Reduce speed and route to depot — bearing temperature beyond engineering limits.",
    ("vibration_rms_mm_s", "spike"): "Inspect wheelset for flats/out-of-roundness; schedule wheel lathe turning.",
    ("vibration_rms_mm_s", "limit"): "Withdraw for wheelset inspection — vibration beyond engineering limits.",
    ("brake_pressure_bar", "drift"): "Leak test the brake pipe and fittings; monitor compressor duty cycle.",
    ("brake_pressure_bar", "limit"): "Do not dispatch — brake pipe pressure below the safe limit.",
    ("traction_motor_current_a", "stuck"): "Replace current transducer / check wiring — channel frozen, traction monitoring is blind.",
    ("traction_motor_current_a", "drift"): "Check traction converter and motor load balance.",
}
DEFAULT_RECOMMENDATION = "Investigate channel; correlate with recent duty and depot logs."


@dataclass
class Alert:
    train_id: str
    sensor: str
    severity: str          # "warning" | "critical"
    kind: str              # dominant detector: spike | drift | stuck | limit
    started: pd.Timestamp
    ended: pd.Timestamp
    active: bool
    samples: int
    peak_value: float
    peak_zscore: float
    message: str
    recommendation: str


def _dominant_kind(kinds: pd.Series) -> str:
    counts: dict[str, int] = {}
    for cell in kinds:
        for kind in str(cell).split(","):
            if kind:
                counts[kind] = counts.get(kind, 0) + 1
    # stuck > limit > drift > spike when tied: prefer the more structural finding
    priority = {"stuck": 3, "limit": 2, "drift": 1, "spike": 0}
    return max(counts, key=lambda k: (counts[k], priority[k]))


def _episode_alert(episode: pd.DataFrame, now: pd.Timestamp) -> Alert:
    spec = SENSORS[episode["sensor"].iloc[0]]
    severity = max(episode["severity"], key=lambda s: SEVERITY_RANK[s])
    kind = _dominant_kind(episode["kinds"])
    peak_idx = episode["zscore"].abs().idxmax()
    peak_value = float(episode.loc[peak_idx, "value"])
    started, ended = episode["timestamp"].iloc[0], episode["timestamp"].iloc[-1]

    kind_text = {
        "spike": "intermittent spikes",
        "drift": "sustained drift from baseline",
        "stuck": "frozen signal (sensor fault)",
        "limit": "engineering limit exceeded",
    }[kind]
    message = f"{spec.label}: {kind_text} — peak {peak_value:.1f} {spec.unit}"

    return Alert(
        train_id=episode["train_id"].iloc[0],
        sensor=episode["sensor"].iloc[0],
        severity=severity,
        kind=kind,
        started=started,
        ended=ended,
        active=(now - ended) <= ACTIVE_WINDOW,
        samples=len(episode),
        peak_value=peak_value,
        peak_zscore=float(episode.loc[peak_idx, "zscore"]),
        message=message,
        recommendation=RECOMMENDATIONS.get((spec.key, kind), DEFAULT_RECOMMENDATION),
    )


def build_alerts(scored: pd.DataFrame) -> list[Alert]:
    """Merge anomalous samples into episode alerts, newest first."""
    now = scored["timestamp"].max()
    alerts: list[Alert] = []
    for _, channel in scored.groupby(["train_id", "sensor"], sort=True):
        anomalous = channel[channel["anomaly"]].sort_values("timestamp")
        if anomalous.empty:
            continue
        gaps = anomalous["timestamp"].diff() > MERGE_GAP
        for _, episode in anomalous.groupby(gaps.cumsum()):
            alerts.append(_episode_alert(episode, now))
    alerts.sort(key=lambda a: (a.active, SEVERITY_RANK[a.severity], a.ended), reverse=True)
    return alerts


# --- fleet health -----------------------------------------------------------

PENALTY = {
    ("critical", True): 45.0,
    ("critical", False): 12.0,
    ("warning", True): 18.0,
    ("warning", False): 3.0,
}
REPEAT_WEIGHT = 0.25       # 2nd+ episode on the same channel counts at 25%
CHANNEL_CAP = 45.0         # one bad channel can't sink the train below ~55 alone


def health_scores(train_ids: list[str], alerts: list[Alert]) -> dict[str, float]:
    """0–100 per train: 100 = clean history; active criticals dominate.

    Penalties diminish for repeat episodes on the same channel so a flapping
    detector reads as one problem, not ten, and are capped per channel.
    """
    by_channel: dict[tuple[str, str], list[float]] = {}
    for alert in alerts:
        by_channel.setdefault((alert.train_id, alert.sensor), []).append(
            PENALTY[(alert.severity, alert.active)]
        )

    scores = {t: 100.0 for t in train_ids}
    for (train_id, _sensor), penalties in by_channel.items():
        penalties.sort(reverse=True)
        total = penalties[0] + REPEAT_WEIGHT * sum(penalties[1:])
        scores[train_id] -= min(total, CHANNEL_CAP)
    return {t: max(5.0, round(s, 1)) for t, s in scores.items()}


def health_status(score: float) -> str:
    if score >= 85:
        return "good"
    if score >= 65:
        return "watch"
    if score >= 40:
        return "warning"
    return "critical"
