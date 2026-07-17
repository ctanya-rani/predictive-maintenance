import pandas as pd
import pytest

from trainwatch.alerts import build_alerts, health_scores, health_status
from trainwatch.config import TRAIN_IDS
from trainwatch.dashboard import build_payload
from trainwatch.detect import detect_anomalies
from trainwatch.generate import generate_fleet_data

END = pd.Timestamp("2026-07-17 00:00:00")


@pytest.fixture(scope="module")
def scored():
    return detect_anomalies(generate_fleet_data(end=END))


@pytest.fixture(scope="module")
def alerts(scored):
    return build_alerts(scored)


def test_faulty_trains_have_alerts(alerts):
    trains_with_alerts = {a.train_id for a in alerts}
    assert {"T-102", "T-103", "T-105", "T-107"} <= trains_with_alerts


def test_alerts_are_episodes_not_point_spam(scored, alerts):
    # far fewer alerts than anomalous samples
    assert 0 < len(alerts) < int(scored["anomaly"].sum()) / 5


def test_active_faults_still_firing(alerts):
    active_trains = {a.train_id for a in alerts if a.active}
    assert "T-103" in active_trains  # drift keeps worsening to the end
    assert "T-107" in active_trains  # stuck channel never recovers


def test_alert_fields_populated(alerts):
    for a in alerts:
        assert a.severity in {"warning", "critical"}
        assert a.kind in {"spike", "drift", "stuck", "limit"}
        assert a.started <= a.ended
        assert a.message and a.recommendation


def test_health_scores_rank_faulty_below_healthy(alerts):
    health = health_scores(TRAIN_IDS, alerts)
    assert set(health) == set(TRAIN_IDS)
    healthy_floor = min(health[t] for t in ("T-101", "T-104", "T-106", "T-108"))
    faulty_ceiling = max(health[t] for t in ("T-103", "T-107"))
    assert faulty_ceiling < healthy_floor
    assert all(0 < s <= 100 for s in health.values())


def test_health_status_bands():
    assert health_status(95) == "good"
    assert health_status(70) == "watch"
    assert health_status(50) == "warning"
    assert health_status(10) == "critical"


def test_payload_shape(scored, alerts):
    health = health_scores(TRAIN_IDS, alerts)
    payload = build_payload(scored, alerts, health)
    assert {t["id"] for t in payload["trains"]} == set(TRAIN_IDS)
    for train_id in TRAIN_IDS:
        assert set(payload["series"][train_id]) == set(payload["sensors"])
        for series in payload["series"][train_id].values():
            assert len(series["mean"]) == len(series["sev"]) == len(series["anom"])
    assert len(payload["alerts"]) == len(alerts)
