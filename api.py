"""Flask API server for TrainWatch.

Exposes the Python backend (generate + detect + alerts) as JSON endpoints.
Used by the React frontend instead of client-side simulation.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import logging
import time

from trainwatch.alerts import build_alerts, health_scores
from trainwatch.config import TRAIN_IDS, SENSORS
from trainwatch.detect import detect_anomalies
from trainwatch.generate import generate_fleet_data

app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    try:
        sim = _get_simulation()
        return jsonify(sim), 200
    except Exception as e:
        logger.error(f"Error fetching fleet data: {e}")
        return jsonify({"error": "Failed to fetch fleet data"}), 500


@app.route("/api/train/<train_id>", methods=["GET"])
def get_train(train_id: str):
    """Get data for a specific train."""
    if train_id not in TRAIN_IDS:
        return jsonify({"error": f"Unknown train: {train_id}"}), 404

    try:
        sim = _get_simulation()
        train_health = next((h for h in sim["health"] if h["trainId"] == train_id), None)
        train_alerts = [a for a in sim["alerts"] if a["trainId"] == train_id]
        train_series = sim["series"].get(train_id, {})

        return jsonify({
            "train": train_health,
            "alerts": train_alerts,
            "series": train_series,
        }), 200
    except Exception as e:
        logger.error(f"Error fetching train {train_id}: {e}")
        return jsonify({"error": "Failed to fetch train data"}), 500


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """Get alerts with optional filtering."""
    try:
        severity = request.args.get("severity")  # "crit", "warn", or None for all
        train_id = request.args.get("train_id")
        active_only = request.args.get("active") in ("true", "1", "yes")

        sim = _get_simulation()
        alerts = sim["alerts"]

        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        if train_id:
            alerts = [a for a in alerts if a["trainId"] == train_id]
        if active_only:
            alerts = [a for a in alerts if a["active"]]

        return jsonify({
            "total": len(alerts),
            "alerts": alerts,
        }), 200
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return jsonify({"error": "Failed to fetch alerts"}), 500


@app.route("/api/sensor/<train_id>/<sensor>", methods=["GET"])
def get_sensor(train_id: str, sensor: str):
    """Get time-series data for a specific sensor."""
    if train_id not in TRAIN_IDS:
        return jsonify({"error": f"Unknown train: {train_id}"}), 404
    if sensor not in SENSORS:
        return jsonify({"error": f"Unknown sensor: {sensor}"}), 404

    try:
        sim = _get_simulation()
        spec = SENSORS[sensor]
        series = sim["series"].get(train_id, {}).get(sensor)

        if not series:
            return jsonify({"error": "No data for this train/sensor"}), 404

        return jsonify({
            "sensor": sensor,
            "label": spec["label"],
            "unit": spec["unit"],
            "series": series,
        }), 200
    except Exception as e:
        logger.error(f"Error fetching sensor {train_id}/{sensor}: {e}")
        return jsonify({"error": "Failed to fetch sensor data"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/info", methods=["GET"])
def api_info():
    """API info & version."""
    return jsonify({
        "service": "TrainWatch",
        "version": "0.2.0",
        "endpoints": {
            "GET /health": "health check",
            "GET /api/fleet": "complete fleet data",
            "GET /api/train/<id>": "specific train data",
            "GET /api/alerts?severity=crit&train_id=T-101&active=true": "filtered alerts",
            "GET /api/sensor/<train>/<sensor>": "time-series for one channel",
        },
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404s."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500s."""
    logger.error(f"Server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info("Starting TrainWatch API on http://localhost:5000")
    logger.info("Endpoints:")
    logger.info("  GET /health              — health check")
    logger.info("  GET /api/info            — API info & available endpoints")
    logger.info("  GET /api/fleet           — complete fleet data")
    logger.info("  GET /api/train/<id>      — specific train")
    logger.info("  GET /api/alerts          — filtered alerts")
    logger.info("  GET /api/sensor/<>/<>    — time-series data")
    logger.info("Generating initial simulation...")
    _get_simulation()
    logger.info("Ready to serve requests")
    app.run(debug=False, port=5000, host="0.0.0.0")
