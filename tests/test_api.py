"""Tests for the Flask API server."""

import json
import pytest
from api import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """GET /health should return ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_fleet_endpoint_exists(client):
    """GET /api/fleet should return fleet data."""
    response = client.get("/api/fleet")
    assert response.status_code == 200


def test_fleet_data_structure(client):
    """Verify /api/fleet returns expected JSON shape."""
    response = client.get("/api/fleet")
    data = response.json

    # Top-level keys
    assert "historyEndMs" in data
    assert "health" in data
    assert "alerts" in data
    assert "series" in data
    assert "totalSamples" in data

    # historyEndMs is a timestamp
    assert isinstance(data["historyEndMs"], int)
    assert data["historyEndMs"] > 0

    # health is a list of train records
    assert isinstance(data["health"], list)
    assert len(data["health"]) == 8

    # Check health record structure
    for train in data["health"]:
        assert "trainId" in train
        assert "score" in train
        assert "status" in train
        assert "activeAlerts" in train
        assert train["status"] in ("ok", "watch", "critical")
        assert 0 <= train["score"] <= 100

    # alerts is a list
    assert isinstance(data["alerts"], list)
    if data["alerts"]:
        alert = data["alerts"][0]
        assert "trainId" in alert
        assert "sensor" in alert
        assert "severity" in alert
        assert "detector" in alert
        assert "peak" in alert
        assert "recommendation" in alert

    # series is a dict of train IDs to sensor data
    assert isinstance(data["series"], dict)
    for train_id, sensors in data["series"].items():
        assert isinstance(sensors, dict)
        for sensor_key, points in sensors.items():
            assert "t0" in points
            assert "dt" in points
            assert "mean" in points
            assert "sev" in points
            assert "anom" in points
            assert len(points["mean"]) == len(points["sev"]) == len(points["anom"])


def test_fleet_health_sorted_by_score(client):
    """Health list should be sorted worst-first."""
    response = client.get("/api/fleet")
    health = response.json["health"]
    scores = [h["score"] for h in health]
    assert scores == sorted(scores)  # ascending = worst first


def test_fleet_alerts_sorted(client):
    """Alerts are ordered most-urgent-first: active, then critical, then recent."""
    response = client.get("/api/fleet")
    alerts = response.json["alerts"]
    assert len(alerts) > 1, "fixture should produce several alerts to order"

    # The emitted order must match the documented ranking exactly.
    def rank(a):
        return (not a["active"], {"crit": 0, "warn": 1}[a["severity"]], -a["endTs"])

    assert [rank(a) for a in alerts] == sorted(rank(a) for a in alerts)

    # Guard the specific regression: every active alert precedes every
    # resolved one, so resolved noise can never push live faults down.
    last_active = max(i for i, a in enumerate(alerts) if a["active"])
    first_resolved = min(i for i, a in enumerate(alerts) if not a["active"])
    assert last_active < first_resolved


def test_active_criticals_lead_the_feed(client):
    """Active critical alerts must land in the window the dashboard renders.

    The console shows only the first 12 alerts, so an ordering bug that pushes
    live critical faults past that cutoff hides exactly what the tool exists to
    surface.
    """
    response = client.get("/api/fleet")
    alerts = response.json["alerts"]

    active_crits = [a for a in alerts if a["active"] and a["severity"] == "crit"]
    assert active_crits, "seeded faults should leave active critical alerts"

    visible = alerts[:12]
    for alert in active_crits:
        assert alert in visible, (
            f"active critical {alert['trainId']}/{alert['sensor']} fell outside "
            "the 12 alerts the dashboard renders"
        )

    # They should also be at the very front of the list.
    assert all(a["active"] and a["severity"] == "crit" for a in alerts[: len(active_crits)])


def test_fleet_endpoint_caching(client):
    """Multiple calls should return same data."""
    resp1 = client.get("/api/fleet")
    resp2 = client.get("/api/fleet")
    assert resp1.json == resp2.json


def test_api_cors_headers(client):
    """API should include CORS headers."""
    response = client.get("/api/fleet")
    # Flask-CORS automatically adds these
    assert "Access-Control-Allow-Origin" in response.headers


def test_fleet_data_has_faults(client):
    """Synthetic data should include the seeded faults."""
    response = client.get("/api/fleet")
    data = response.json

    # T-103 should have bearing temperature alerts
    t103_alerts = [a for a in data["alerts"] if a["trainId"] == "T-103"]
    assert any("axle_bearing" in a["sensor"] for a in t103_alerts)

    # T-105 should have vibration alerts
    t105_alerts = [a for a in data["alerts"] if a["trainId"] == "T-105"]
    assert any("vibration" in a["sensor"] for a in t105_alerts)

    # T-102 should have brake pressure alerts
    t102_alerts = [a for a in data["alerts"] if a["trainId"] == "T-102"]
    assert any("brake" in a["sensor"] for a in t102_alerts)


def test_fleet_recommendations_populated(client):
    """Alerts should include maintenance recommendations."""
    response = client.get("/api/fleet")
    alerts = response.json["alerts"]

    for alert in alerts:
        assert alert["recommendation"]
        assert len(alert["recommendation"]) > 20
        # Recommendations should be actionable (contain verbs)
        verbs = ["check", "inspect", "schedule", "investigate", "monitor", "replace"]
        assert any(verb in alert["recommendation"].lower() for verb in verbs)
