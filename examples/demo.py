#!/usr/bin/env python3
"""
Quick demo: generate data, detect anomalies, show alerts.

Run this to see the full pipeline in action without the web UI.
"""

from trainwatch.alerts import build_alerts, health_scores, health_status
from trainwatch.config import TRAIN_IDS
from trainwatch.detect import detect_anomalies
from trainwatch.generate import generate_fleet_data


def demo():
    """Run the predictive maintenance pipeline and print results."""
    print("=" * 80)
    print("TrainWatch Predictive Maintenance Demo")
    print("=" * 80)

    # Step 1: Generate synthetic telemetry
    print("\n📊 Generating synthetic fleet data...")
    data = generate_fleet_data()
    print(f"   Generated {len(data):,} samples across {data.groupby(['train_id', 'sensor']).ngroups} channels")
    print(f"   Time range: {data['timestamp'].min()} to {data['timestamp'].max()}")

    # Step 2: Detect anomalies
    print("\n🔍 Detecting anomalies...")
    scored = detect_anomalies(data)
    n_anom = int(scored["anomaly"].sum())
    print(f"   Found {n_anom:,} anomalous samples ({n_anom / len(scored) * 100:.2f}%)")

    # Step 3: Build alerts
    print("\n⚠️  Building alert episodes...")
    alerts = build_alerts(scored)
    active = [a for a in alerts if a.active]
    print(f"   Created {len(alerts)} alert episodes ({len(active)} active)")

    # Step 4: Score fleet health
    print("\n💚 Computing fleet health scores...")
    health = health_scores(sorted(data["train_id"].unique()), alerts)

    # Print results
    print("\n" + "=" * 80)
    print("FLEET HEALTH REPORT")
    print("=" * 80)

    for train_id in sorted(health.keys()):
        score = health[train_id]
        status = health_status(score)
        status_emoji = {"good": "✓", "watch": "◐", "warning": "▲", "critical": "◆"}[status]
        train_alerts = [a for a in alerts if a.train_id == train_id]
        active_alerts = sum(1 for a in train_alerts if a.active)
        print(f"{status_emoji} {train_id}  score: {score:5.1f}  status: {status:8}  active alerts: {active_alerts}")

    print("\n" + "=" * 80)
    print("TOP ACTIVE ALERTS")
    print("=" * 80)

    for i, alert in enumerate(active[:5], 1):
        print(f"\n{i}. {alert.train_id} - {alert.sensor}")
        print(f"   Severity: {alert.severity.upper()}")
        print(f"   Detector: {alert.kind}")
        print(f"   Peak value: {alert.peak_value:.1f} {alert.sensor.split('_')[-1]}")
        print(f"   Duration: {(alert.ended - alert.started).total_seconds() / 3600:.1f} hours")
        print(f"   Recommendation: {alert.recommendation}")

    if not active:
        print("\n✓ No active alerts — fleet is healthy!")

    print("\n" + "=" * 80)
    print(f"Tip: Run 'python api.py' and open http://localhost:5173 to see the dashboard")
    print("=" * 80)


if __name__ == "__main__":
    demo()
