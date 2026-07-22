"""Flask API server for TrainWatch.

Exposes the Python backend (generate + detect + alerts) as JSON endpoints.
Used by the React frontend instead of client-side simulation.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import json

from trainwatch.alerts import build_alerts, health_scores
from trainwatch.config import TRAIN_IDS, SENSORS
from trainwatch.detect import detect_anomalies
from trainwatch.generate import generate_fleet_data

app = Flask(__name__)
CORS(app)

# Cache the simulation in memory so it's not regenerated on every request
_simulation = None


def _get_simulation():
    """Lazy-load the fleet simulation."""
    global _simulation
    if _simulation is None:
        data = generate_fleet_data()
        scored = detect_anomalies(data)
        alerts = build_alerts(scored)
        health = health_scores(sorted(data["train_id"].unique()), alerts)

        # Aggregate to hourly buckets for API response
        frame = scored.copy()
        frame["bucket"] = frame["timestamp"].dt.floor("h")
        frame["sev_rank"] = frame["severity"].map({"ok": 0, "warning": 1, "critical": 2})

        series = {}
        grouped = frame.groupby(["train_id", "sensor", "bucket"], sort=True).agg(
            mean=("value", "mean"),
            sev=("sev_rank", "max"),
            anom=("anomaly", "sum"),
        )
        for (train_id, sensor), channel in grouped.groupby(level=[0, 1]):
            channel = channel.droplevel([0, 1])
            series.setdefault(train_id, {})[sensor] = {
                "t0": int(channel.index[0].timestamp()),
                "dt": 3600,
                "mean": [round(v, 2) for v in channel["mean"]],
                "sev": [int(s) for s in channel["sev"]],
                "anom": [int(a) for a in channel["anom"]],
            }

        # Format alerts
        alert_rows = []
        for alert in alerts:
            alert_rows.append(
                {
                    "id": f"{alert.train_id}:{alert.sensor}:{alert.started.isoformat()}",
                    "trainId": alert.train_id,
                    "sensor": alert.sensor,
                    "severity": "crit" if alert.severity == "critical" else "warn",
                    "detector": alert.kind,
                    "startedTs": int(alert.started.timestamp() * 1000),
                    "endTs": int(alert.ended.timestamp() * 1000),
                    "active": alert.active,
                    "peak": alert.peak_value,
                    "recommendation": alert.recommendation,
                }
            )

        # Format train health
        train_health = []
        for train_id in sorted(data["train_id"].unique()):
            train_alerts = [a for a in alerts if a.train_id == train_id]
            active_alerts = [a for a in train_alerts if a.active]
            status = (
                "critical"
                if health[train_id] < 40
                else "watch" if health[train_id] < 70 else "ok"
            )
            train_health.append(
                {
                    "trainId": train_id,
                    "score": round(health[train_id], 1),
                    "status": status,
                    "activeAlerts": len(active_alerts),
                }
            )

        _simulation = {
            "historyEndMs": int(scored["timestamp"].max().timestamp() * 1000),
            "health": sorted(train_health, key=lambda h: h["score"]),
            "alerts": sorted(
                alert_rows,
                key=lambda a: (not a["active"], {"crit": 0, "warn": 1}[a["severity"]], a["endTs"]),
                reverse=True,
            ),
            "series": series,
            "totalSamples": len(data),
        }

    return _simulation


@app.route("/api/fleet", methods=["GET"])
def get_fleet():
    """Get complete fleet simulation data."""
    sim = _get_simulation()
    return jsonify(sim)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("Starting TrainWatch API on http://localhost:5000")
    print("GET /api/fleet     — complete fleet data")
    print("GET /health        — health check")
    app.run(debug=False, port=5000, host="0.0.0.0")
