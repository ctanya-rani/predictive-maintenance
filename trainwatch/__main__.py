"""Run the full pipeline: generate -> detect -> alerts -> dashboard.

Usage:
    python -m trainwatch [--days N] [--seed N] [--out DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .alerts import build_alerts, health_scores, health_status
from .config import DAYS, RANDOM_SEED, TRAIN_IDS
from .dashboard import render_dashboard
from .detect import detect_anomalies
from .generate import generate_fleet_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trainwatch", description=__doc__)
    parser.add_argument("--days", type=int, default=DAYS, help="history length in days")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="random seed")
    parser.add_argument("--out", type=Path, default=Path("output"), help="output directory")
    args = parser.parse_args(argv)

    print(f"Generating {args.days} days of telemetry for {len(TRAIN_IDS)} trains ...")
    data = generate_fleet_data(days=args.days, seed=args.seed)
    print(f"  {len(data):,} samples across {data.groupby(['train_id', 'sensor']).ngroups} channels")

    print("Scoring channels (robust z-score, EWMA drift, stuck-channel, limits) ...")
    scored = detect_anomalies(data)
    n_anom = int(scored["anomaly"].sum())
    print(f"  {n_anom:,} anomalous samples ({n_anom / len(scored):.2%})")

    alerts = build_alerts(scored)
    health = health_scores(sorted(data["train_id"].unique()), alerts)
    active = [a for a in alerts if a.active]
    print(f"  {len(alerts)} alert episodes, {len(active)} active")

    args.out.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.out / "telemetry.csv", index=False)
    scored[scored["anomaly"]].to_csv(args.out / "anomalies.csv", index=False)
    import pandas as pd

    pd.DataFrame([vars(a) for a in alerts]).to_csv(args.out / "alerts.csv", index=False)
    dashboard = render_dashboard(scored, alerts, health, args.out / "dashboard.html")

    print("\nFleet health:")
    for train_id, score in sorted(health.items(), key=lambda kv: kv[1]):
        marker = {"good": " ", "watch": "•", "warning": "▲", "critical": "◆"}[health_status(score)]
        print(f"  {marker} {train_id}: {score:5.1f}  ({health_status(score)})")

    print(f"\nDashboard: {dashboard.resolve()}")
    print(f"Data:      {args.out.resolve()}/telemetry.csv, anomalies.csv, alerts.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
