import numpy as np
import pandas as pd
import pytest

from trainwatch.detect import detect_anomalies
from trainwatch.generate import generate_fleet_data

END = pd.Timestamp("2026-07-17 00:00:00")


@pytest.fixture(scope="module")
def scored():
    return detect_anomalies(generate_fleet_data(end=END))


def channel(scored, train, sensor):
    return scored[(scored["train_id"] == train) & (scored["sensor"] == sensor)]


def test_healthy_channels_mostly_quiet(scored):
    healthy = channel(scored, "T-101", "axle_bearing_temp_c")
    assert healthy["anomaly"].mean() < 0.01


def test_bearing_drift_detected_before_critical_limit(scored):
    ch = channel(scored, "T-103", "axle_bearing_temp_c").reset_index(drop=True)
    drift_hits = ch[ch["kinds"].str.contains("drift")]
    assert not drift_hits.empty
    first_detection = drift_hits["timestamp"].iloc[0]
    limit_hits = ch[ch["kinds"].str.contains("limit")]
    assert not limit_hits.empty, "fault should eventually cross the engineering limit"
    # the point of predictive maintenance: drift flagged well before the hard limit
    assert first_detection < limit_hits["timestamp"].iloc[0] - pd.Timedelta(days=1)


def test_vibration_spikes_detected(scored):
    ch = channel(scored, "T-105", "vibration_rms_mm_s")
    assert ch["kinds"].str.contains("spike").any()


def test_brake_leak_detected_as_drift(scored):
    ch = channel(scored, "T-102", "brake_pressure_bar")
    hits = ch[ch["kinds"].str.contains("drift")]
    assert not hits.empty
    # drift is downward: EWMA score negative at detection
    assert hits["ewma_score"].iloc[0] < 0


def test_stuck_sensor_detected(scored):
    ch = channel(scored, "T-107", "traction_motor_current_a")
    stuck = ch[ch["kinds"].str.contains("stuck")]
    assert not stuck.empty
    assert (stuck["severity"] == "critical").all()


def test_no_stuck_false_positives_on_live_channels(scored):
    live = scored[~((scored["train_id"] == "T-107")
                    & (scored["sensor"] == "traction_motor_current_a"))]
    assert not live["kinds"].str.contains("stuck").any()


def test_severity_consistent_with_anomaly_flag(scored):
    assert (scored.loc[scored["anomaly"], "severity"] != "ok").all()
    assert (scored.loc[~scored["anomaly"], "severity"] == "ok").all()
