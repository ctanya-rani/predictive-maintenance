"""Render the fleet dashboard as a single self-contained HTML file.

The Python side aggregates telemetry to hourly buckets and serializes one
JSON payload; everything visual (SVG line charts, crosshair tooltips, the
alert feed, filters, dark mode) is rendered client-side by the inline
script in ``TEMPLATE``. No external assets, works from file://.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from . import __version__
from .alerts import Alert, health_status
from .config import SENSORS
from .detect import SEVERITY_RANK


def _hourly_series(scored: pd.DataFrame) -> dict:
    """Aggregate each channel to hourly buckets: mean value, worst severity, anomaly count."""
    frame = scored.copy()
    frame["bucket"] = frame["timestamp"].dt.floor("h")
    frame["sev_rank"] = frame["severity"].map(SEVERITY_RANK)

    series: dict[str, dict[str, dict]] = {}
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
    return series


def _train_summaries(
    train_ids: list[str], alerts: list[Alert], health: dict[str, float]
) -> list[dict]:
    out = []
    for train_id in train_ids:
        active = [a for a in alerts if a.train_id == train_id and a.active]
        worst = max(active, key=lambda a: SEVERITY_RANK[a.severity], default=None)
        out.append(
            {
                "id": train_id,
                "health": health[train_id],
                "status": health_status(health[train_id]),
                "active_critical": sum(1 for a in active if a.severity == "critical"),
                "active_warning": sum(1 for a in active if a.severity == "warning"),
                "worst_channel": SENSORS[worst.sensor].label if worst else "",
            }
        )
    return out


def build_payload(scored: pd.DataFrame, alerts: list[Alert], health: dict[str, float]) -> dict:
    train_ids = sorted(scored["train_id"].unique())
    alert_rows = []
    for alert in alerts:
        row = asdict(alert)
        row["started"] = alert.started.isoformat()
        row["ended"] = alert.ended.isoformat()
        row["unit"] = SENSORS[alert.sensor].unit
        row["sensor_label"] = SENSORS[alert.sensor].label
        alert_rows.append(row)

    return {
        "version": __version__,
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
        "window": {
            "start": scored["timestamp"].min().isoformat(),
            "end": scored["timestamp"].max().isoformat(),
        },
        "sensors": {key: asdict(spec) for key, spec in SENSORS.items()},
        "trains": _train_summaries(train_ids, alerts, health),
        "series": _hourly_series(scored),
        "alerts": alert_rows,
    }


def render_dashboard(
    scored: pd.DataFrame,
    alerts: list[Alert],
    health: dict[str, float],
    out_path: str | Path,
) -> Path:
    payload = build_payload(scored, alerts, health)
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.replace("__PAYLOAD__", blob)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrainWatch — fleet predictive maintenance</title>
<style>
  .viz-root {
    color-scheme: light;
    --page:           #f9f9f7;
    --surface-1:      #fcfcfb;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --grid:           #e1e0d9;
    --axis:           #c3c2b7;
    --border:         rgba(11,11,11,0.10);
    --series-1:       #2a78d6;
    --status-good:    #0ca30c;
    --status-warning: #fab219;
    --status-serious: #ec835a;
    --status-critical:#d03b3b;
    --good-text:      #006300;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --page:           #0d0d0d;
      --surface-1:      #1a1a19;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --grid:           #2c2c2a;
      --axis:           #383835;
      --border:         rgba(255,255,255,0.10);
      --series-1:       #3987e5;
      --good-text:      #0ca30c;
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --page:           #0d0d0d;
    --surface-1:      #1a1a19;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --grid:           #2c2c2a;
    --axis:           #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --good-text:      #0ca30c;
  }

  * { box-sizing: border-box; margin: 0; }
  body.viz-root {
    background: var(--page);
    color: var(--text-primary);
    font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: 24px clamp(16px, 4vw, 48px) 64px;
  }
  h1 { font-size: 20px; font-weight: 650; }
  h2 { font-size: 15px; font-weight: 600; margin-bottom: 10px; }
  .sub { color: var(--text-secondary); font-size: 13px; margin-top: 2px; }
  .muted { color: var(--text-muted); }
  section { margin-top: 28px; }

  .card {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }

  /* stat tiles */
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  .tile .label { font-size: 13px; color: var(--text-secondary); }
  .tile .value { font-size: 30px; font-weight: 600; margin-top: 2px; }
  .tile .note  { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

  /* fleet table */
  table { border-collapse: collapse; width: 100%; }
  th { text-align: left; font-size: 12px; font-weight: 600; color: var(--text-muted);
       padding: 6px 10px; border-bottom: 1px solid var(--grid); }
  td { padding: 8px 10px; border-bottom: 1px solid var(--grid); font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .meter { width: 140px; height: 8px; border-radius: 4px; overflow: hidden; }
  .meter i { display: block; height: 100%; border-radius: 4px; }

  .chip-status { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; }
  .chip-status .icon { font-size: 11px; }

  /* filter row */
  .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px; }
  .filters .group { display: flex; gap: 4px; background: var(--surface-1);
    border: 1px solid var(--border); border-radius: 8px; padding: 3px; }
  .filters button {
    font: 500 13px/1 system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--text-secondary); background: none; border: 0; border-radius: 6px;
    padding: 7px 12px; cursor: pointer;
  }
  .filters button:hover { background: color-mix(in srgb, var(--text-primary) 6%, transparent); }
  .filters button[aria-pressed="true"] { background: color-mix(in srgb, var(--series-1) 14%, transparent);
    color: var(--text-primary); font-weight: 600; }
  .filters .spacer { flex: 1; }

  /* charts */
  .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; }
  .chart-card h3 { font-size: 13.5px; font-weight: 600; }
  .chart-card .unit { color: var(--text-muted); font-weight: 400; }
  .chart-wrap { position: relative; margin-top: 6px; }
  .chart-wrap svg { display: block; width: 100%; height: auto; }
  .gridline { stroke: var(--grid); stroke-width: 1; }
  .axisline { stroke: var(--axis); stroke-width: 1; }
  .ticklabel { fill: var(--text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
  .thresh { stroke-width: 1; opacity: 0.55; }
  .thresh-label { font-size: 10.5px; fill: var(--text-secondary); }
  .line { fill: none; stroke: var(--series-1); stroke-width: 2;
          stroke-linejoin: round; stroke-linecap: round; }
  .wash { fill: var(--series-1); opacity: 0.10; }
  .marker { stroke: var(--surface-1); stroke-width: 2; }
  .marker-warning { fill: var(--status-warning); }
  .marker-critical { fill: var(--status-critical); }
  .crosshair { stroke: var(--axis); stroke-width: 1; visibility: hidden; }

  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12.5px;
            color: var(--text-secondary); margin-bottom: 10px; }
  .legend .key { display: inline-flex; align-items: center; gap: 6px; }
  .legend svg { display: block; }

  .tooltip {
    position: absolute; pointer-events: none; visibility: hidden; z-index: 5;
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.14); padding: 8px 10px; min-width: 150px;
  }
  .tooltip .tt-time { font-size: 11.5px; color: var(--text-muted); }
  .tooltip .tt-row { display: flex; align-items: baseline; gap: 8px; margin-top: 3px; }
  .tooltip .tt-key { width: 14px; height: 0; border-top: 2px solid var(--series-1);
                     align-self: center; }
  .tooltip .tt-val { font-weight: 650; font-size: 14px; }
  .tooltip .tt-name { color: var(--text-secondary); font-size: 12px; }
  .tooltip .tt-status { font-size: 12px; margin-top: 3px; }

  details.tableview { margin-top: 8px; }
  details.tableview summary { cursor: pointer; font-size: 12.5px; color: var(--text-secondary); }
  details.tableview .scroll { max-height: 260px; overflow: auto; margin-top: 6px;
    border: 1px solid var(--grid); border-radius: 8px; }

  /* alert feed */
  .alert-list { display: flex; flex-direction: column; }
  .alert-row { display: flex; gap: 12px; padding: 12px 4px; border-bottom: 1px solid var(--grid);
               align-items: baseline; flex-wrap: wrap; }
  .alert-row:last-child { border-bottom: none; }
  .alert-when { color: var(--text-muted); font-size: 12px; min-width: 170px;
                font-variant-numeric: tabular-nums; }
  .alert-main { flex: 1 1 320px; }
  .alert-msg { font-weight: 550; }
  .alert-rec { color: var(--text-secondary); font-size: 12.5px; margin-top: 2px; }
  .badge { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600;
           border-radius: 999px; padding: 2px 9px; border: 1px solid var(--border); }
  .badge-resolved { color: var(--text-muted); }
  .empty { color: var(--text-muted); padding: 12px 4px; }

  footer { margin-top: 36px; font-size: 12px; color: var(--text-muted); }
</style>
</head>
<body class="viz-root">
<header>
  <h1>TrainWatch — fleet predictive maintenance</h1>
  <p class="sub" id="subline"></p>
</header>

<section aria-label="Fleet status">
  <div class="tiles" id="tiles"></div>
</section>

<section aria-label="Fleet health">
  <h2>Current train health</h2>
  <div class="card" style="padding:6px 8px">
    <table id="fleet-table">
      <thead><tr>
        <th>Train</th><th>Health</th><th class="num">Score</th><th>Status</th>
        <th class="num">Active alerts</th><th>Worst channel</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
</section>

<section aria-label="Sensor detail">
  <h2>Sensor telemetry &amp; anomalies</h2>
  <div class="filters" id="filters">
    <div class="group" id="range-group" role="group" aria-label="Time range"></div>
    <div class="group" id="train-group" role="group" aria-label="Train"></div>
    <div class="spacer"></div>
  </div>
  <div class="legend" id="legend"></div>
  <div class="charts" id="charts"></div>
</section>

<section aria-label="Alerts">
  <h2 id="alerts-title">Alerts</h2>
  <div class="card alert-list" id="alerts"></div>
</section>

<footer id="footer"></footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
"use strict";
const P = JSON.parse(document.getElementById("payload").textContent);

const SEV_NAME = ["ok", "warning", "critical"];
const STATUS_META = {
  good:     { icon: "✓", color: "var(--status-good)",     label: "Good" },
  watch:    { icon: "◐", color: "var(--status-warning)",  label: "Watch" },
  warning:  { icon: "▲", color: "var(--status-serious)",  label: "Warning" },
  critical: { icon: "◆", color: "var(--status-critical)", label: "Critical" },
};
const SEV_META = {
  warning:  { icon: "▲", color: "var(--status-warning)",  label: "Warning" },
  critical: { icon: "◆", color: "var(--status-critical)", label: "Critical" },
};

const state = { rangeH: null, train: null };

const fmtTime = ts => new Date(ts).toLocaleString(undefined,
  { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const fmtDay = ts => new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const svgEl = (tag, attrs) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  return node;
};

/* ---------- header, tiles, fleet table (current state; not range-scoped) --- */

document.getElementById("subline").textContent =
  `Synthetic fleet telemetry ${fmtDay(P.window.start)} – ${fmtDay(P.window.end)}` +
  ` · ${P.trains.length} trains · ${Object.keys(P.sensors).length} channels per train` +
  ` · generated ${fmtTime(P.generated)}`;
document.getElementById("footer").textContent =
  `TrainWatch v${P.version} · synthetic data — no real rolling stock was harmed · ` +
  `detectors: seasonal robust z-score, EWMA drift, stuck-channel, engineering limits`;

function statusChip(status) {
  const meta = STATUS_META[status];
  const chip = el("span", "chip-status");
  const icon = el("span", "icon", meta.icon);
  icon.style.color = meta.color;
  chip.append(icon, el("span", "", meta.label));
  return chip;
}

function renderTiles() {
  const tiles = document.getElementById("tiles");
  const avg = P.trains.reduce((s, t) => s + t.health, 0) / P.trains.length;
  const crit = P.trains.reduce((s, t) => s + t.active_critical, 0);
  const warn = P.trains.reduce((s, t) => s + t.active_warning, 0);
  const channels = P.trains.length * Object.keys(P.sensors).length;
  const healthy = P.trains.filter(t => t.status === "good").length;
  const items = [
    { label: "Fleet health", value: avg.toFixed(0), note: "mean of train scores (0–100)" },
    { label: "Active critical alerts", value: String(crit),
      note: crit ? "immediate action required" : "none firing" },
    { label: "Active warnings", value: String(warn),
      note: warn ? "plan maintenance" : "none firing" },
    { label: "Trains without findings", value: `${healthy} of ${P.trains.length}`,
      note: `${channels} sensor channels monitored` },
  ];
  for (const item of items) {
    const tile = el("div", "card tile");
    tile.append(el("div", "label", item.label), el("div", "value", item.value),
                el("div", "note", item.note));
    tiles.append(tile);
  }
}

function renderFleetTable() {
  const body = document.querySelector("#fleet-table tbody");
  const sorted = [...P.trains].sort((a, b) => a.health - b.health);
  for (const train of sorted) {
    const row = el("tr");
    row.append(el("td", "", train.id));

    const meterCell = el("td");
    const meta = STATUS_META[train.status];
    const meter = el("div", "meter");
    meter.style.background = `color-mix(in srgb, ${meta.color} 18%, var(--surface-1))`;
    const fill = el("i");
    fill.style.width = `${train.health}%`;
    fill.style.background = meta.color;
    meter.append(fill);
    meterCell.append(meter);
    row.append(meterCell);

    row.append(el("td", "num", train.health.toFixed(0)));
    const statusCell = el("td");
    statusCell.append(statusChip(train.status));
    row.append(statusCell);
    row.append(el("td", "num", String(train.active_critical + train.active_warning)));
    row.append(el("td", "muted", train.worst_channel || "—"));
    body.append(row);
  }
}

/* ---------- filters ---------- */

const RANGES = [
  { label: "24 h", hours: 24 }, { label: "3 d", hours: 72 },
  { label: "7 d", hours: 168 }, { label: "14 d", hours: null },
];

function buttonGroup(container, items, isActive, onPick) {
  container.replaceChildren();
  for (const item of items) {
    const btn = el("button", "", item.label);
    btn.setAttribute("aria-pressed", String(isActive(item)));
    btn.addEventListener("click", () => { onPick(item); });
    container.append(btn);
  }
}

function renderFilters() {
  buttonGroup(document.getElementById("range-group"), RANGES,
    item => item.hours === state.rangeH,
    item => { state.rangeH = item.hours; renderFilters(); renderScoped(); });
  buttonGroup(document.getElementById("train-group"),
    P.trains.map(t => ({ label: t.id, id: t.id })),
    item => item.id === state.train,
    item => { state.train = item.id; renderFilters(); renderScoped(); });
}

/* ---------- charts ---------- */

function niceTicks(lo, hi, count) {
  const span = hi - lo || 1;
  const step0 = span / Math.max(count - 1, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= count) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(v);
  return ticks;
}

function sliceSeries(series, rangeH) {
  const n = series.mean.length;
  const keep = rangeH === null ? n : Math.min(rangeH, n);
  const start = n - keep;
  return {
    t0: (series.t0 + start * series.dt) * 1000,
    dt: series.dt * 1000,
    mean: series.mean.slice(start),
    sev: series.sev.slice(start),
    anom: series.anom.slice(start),
  };
}

const M = { top: 10, right: 12, bottom: 26, left: 44 };
const W = 460, H = 190;

function renderChart(card, spec, series) {
  const data = sliceSeries(series, state.rangeH);
  const n = data.mean.length;
  const innerW = W - M.left - M.right, innerH = H - M.top - M.bottom;
  const x = i => M.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const lo = spec.axis_min, hi = spec.axis_max;
  const y = v => M.top + innerH * (1 - (Math.min(Math.max(v, lo), hi) - lo) / (hi - lo));

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `${spec.label} over time with anomaly markers` });

  for (const tick of niceTicks(lo, hi, 5)) {
    svg.append(svgEl("line", { x1: M.left, x2: W - M.right, y1: y(tick), y2: y(tick),
      class: "gridline" }));
    const label = svgEl("text", { x: M.left - 8, y: y(tick) + 3.5, "text-anchor": "end",
      class: "ticklabel" });
    label.textContent = tick >= 1000 ? tick.toLocaleString() : String(tick);
    svg.append(label);
  }
  svg.append(svgEl("line", { x1: M.left, x2: W - M.right, y1: M.top + innerH,
    y2: M.top + innerH, class: "axisline" }));

  const tickEvery = Math.max(1, Math.round(n / 5));
  for (let i = 0; i < n; i += tickEvery) {
    const ts = data.t0 + i * data.dt;
    const anchor = x(i) > W - 40 ? "end" : x(i) < M.left + 24 ? "start" : "middle";
    const label = svgEl("text", { x: x(i), y: H - 8, "text-anchor": anchor,
      class: "ticklabel" });
    label.textContent = state.rangeH === 24
      ? new Date(ts).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
      : fmtDay(ts);
    svg.append(label);
  }

  // engineering limits inside the visible window
  const thresholds = [
    { v: spec.warn_high, color: "var(--status-warning)", text: "warning limit" },
    { v: spec.crit_high, color: "var(--status-critical)", text: "critical limit" },
    { v: spec.warn_low, color: "var(--status-warning)", text: "warning limit" },
    { v: spec.crit_low, color: "var(--status-critical)", text: "critical limit" },
  ].filter(t => t.v !== null && t.v > lo && t.v < hi);
  for (const t of thresholds) {
    svg.append(svgEl("line", { x1: M.left, x2: W - M.right, y1: y(t.v), y2: y(t.v),
      class: "thresh", stroke: t.color }));
    // labels sit at the left — faults grow toward "now", so markers crowd the right
    const label = svgEl("text", { x: M.left + 4, y: y(t.v) - 4, "text-anchor": "start",
      class: "thresh-label" });
    label.textContent = t.text;
    svg.append(label);
  }

  const pts = data.mean.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  svg.append(svgEl("path", { class: "wash",
    d: `M${M.left},${M.top + innerH} L` + pts.join(" L") + ` L${x(n - 1)},${M.top + innerH} Z` }));
  svg.append(svgEl("path", { class: "line", d: "M" + pts.join(" L") }));

  for (let i = 0; i < n; i++) {
    if (data.sev[i] === 1) {
      const cx = x(i), cy = y(data.mean[i]);
      svg.append(svgEl("path", { class: "marker marker-warning",
        d: `M${cx},${cy - 5.5} L${cx + 5},${cy + 4} L${cx - 5},${cy + 4} Z` }));
    } else if (data.sev[i] === 2) {
      const cx = x(i), cy = y(data.mean[i]);
      svg.append(svgEl("path", { class: "marker marker-critical",
        d: `M${cx},${cy - 6} L${cx + 6},${cy} L${cx},${cy + 6} L${cx - 6},${cy} Z` }));
    }
  }

  const crosshair = svgEl("line", { class: "crosshair", y1: M.top, y2: M.top + innerH });
  svg.append(crosshair);

  const wrap = el("div", "chart-wrap");
  wrap.append(svg);
  const tooltip = el("div", "tooltip");
  const ttTime = el("div", "tt-time");
  const ttRow = el("div", "tt-row");
  const ttVal = el("span", "tt-val");
  const ttName = el("span", "tt-name", spec.unit);
  ttRow.append(el("span", "tt-key"), ttVal, ttName);
  const ttStatus = el("div", "tt-status");
  tooltip.append(ttTime, ttRow, ttStatus);
  wrap.append(tooltip);

  const hit = svgEl("rect", { x: M.left, y: M.top, width: innerW, height: innerH,
    fill: "transparent" });
  svg.append(hit);
  const show = evt => {
    const rect = svg.getBoundingClientRect();
    const px = ((evt.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - M.left) / innerW) * (n - 1));
    if (i < 0 || i >= n) return hide();
    crosshair.setAttribute("x1", x(i));
    crosshair.setAttribute("x2", x(i));
    crosshair.style.visibility = "visible";
    ttTime.textContent = fmtTime(data.t0 + i * data.dt);
    ttVal.textContent = data.mean[i].toLocaleString();
    const sev = data.sev[i];
    ttStatus.textContent = sev === 0 ? "normal"
      : `${SEV_NAME[sev]} · ${data.anom[i]} anomalous sample${data.anom[i] === 1 ? "" : "s"}`;
    ttStatus.style.color = sev === 2 ? "var(--status-critical)"
      : sev === 1 ? "var(--text-secondary)" : "var(--text-muted)";
    tooltip.style.visibility = "visible";
    const left = (x(i) / W) * rect.width;
    tooltip.style.left = Math.min(left + 12, rect.width - 165) + "px";
    tooltip.style.top = "8px";
  };
  const hide = () => { crosshair.style.visibility = "hidden"; tooltip.style.visibility = "hidden"; };
  hit.addEventListener("pointermove", show);
  hit.addEventListener("pointerleave", hide);

  card.append(wrap);

  // table view — same numbers without hovering
  const details = el("details", "tableview");
  details.append(el("summary", "", "Data table"));
  const scroll = el("div", "scroll");
  details.append(scroll);
  let filled = false;
  details.addEventListener("toggle", () => {
    if (!details.open || filled) return;
    filled = true;
    const table = el("table");
    const head = el("tr");
    for (const h of ["Time", `Mean (${spec.unit})`, "Status", "Anomalous samples"])
      head.append(el("th", "", h));
    table.append(head);
    for (let i = n - 1; i >= 0; i--) {
      const row = el("tr");
      row.append(el("td", "", fmtTime(data.t0 + i * data.dt)));
      row.append(el("td", "num", data.mean[i].toLocaleString()));
      row.append(el("td", "", SEV_NAME[data.sev[i]]));
      row.append(el("td", "num", String(data.anom[i])));
      table.append(row);
    }
    scroll.append(table);
  });
  card.append(details);
}

function renderLegend() {
  const legend = document.getElementById("legend");
  legend.replaceChildren();
  const lineKey = el("span", "key");
  const lineSvg = svgEl("svg", { width: 18, height: 6, viewBox: "0 0 18 6" });
  lineSvg.append(svgEl("line", { x1: 0, x2: 18, y1: 3, y2: 3, class: "line" }));
  lineKey.append(lineSvg, el("span", "", "hourly mean"));
  legend.append(lineKey);
  for (const [sev, meta] of Object.entries(SEV_META)) {
    const key = el("span", "key");
    const icon = el("span", "icon", meta.icon);
    icon.style.color = meta.color;
    key.append(icon, el("span", "", `${meta.label} anomaly`));
    legend.append(key);
  }
  const threshKey = el("span", "key");
  const threshSvg = svgEl("svg", { width: 18, height: 6, viewBox: "0 0 18 6" });
  threshSvg.append(svgEl("line", { x1: 0, x2: 18, y1: 3, y2: 3, class: "thresh",
    stroke: "var(--status-critical)" }));
  threshKey.append(threshSvg, el("span", "", "engineering limit"));
  legend.append(threshKey);
}

function renderCharts() {
  const charts = document.getElementById("charts");
  charts.replaceChildren();
  const trainSeries = P.series[state.train] || {};
  for (const [key, spec] of Object.entries(P.sensors)) {
    const card = el("div", "card chart-card");
    const title = el("h3", "", `${spec.label} `);
    title.append(el("span", "unit", `(${spec.unit})`));
    card.append(title);
    if (trainSeries[key]) renderChart(card, spec, trainSeries[key]);
    charts.append(card);
  }
}

/* ---------- alert feed ---------- */

function rangeStartMs() {
  const endMs = new Date(P.window.end).getTime();
  return state.rangeH === null ? -Infinity : endMs - state.rangeH * 3600 * 1000;
}

function renderAlerts() {
  const list = document.getElementById("alerts");
  list.replaceChildren();
  const startMs = rangeStartMs();
  const rows = P.alerts.filter(a =>
    a.train_id === state.train && new Date(a.ended).getTime() >= startMs);
  document.getElementById("alerts-title").textContent =
    `Alerts — ${state.train} (${rows.length} in range)`;
  if (!rows.length) {
    list.append(el("div", "empty", "No alerts for this train in the selected range."));
    return;
  }
  for (const a of rows) {
    const row = el("div", "alert-row");
    const meta = SEV_META[a.severity];
    const badge = el("span", "badge");
    const icon = el("span", "", meta.icon);
    icon.style.color = meta.color;
    badge.append(icon, el("span", "", meta.label));
    row.append(badge);
    row.append(el("span", "alert-when",
      `${fmtTime(a.started)} → ${a.active ? "ongoing" : fmtTime(a.ended)}`));
    const main = el("div", "alert-main");
    main.append(el("div", "alert-msg", `${a.train_id} · ${a.message}`));
    main.append(el("div", "alert-rec", a.recommendation));
    row.append(main);
    const stateBadge = el("span", a.active ? "badge" : "badge badge-resolved",
      a.active ? "Active" : "Resolved");
    if (a.active) stateBadge.style.color = "var(--status-critical)";
    row.append(stateBadge);
    list.append(row);
  }
}

/* ---------- boot ---------- */

function renderScoped() { renderLegend(); renderCharts(); renderAlerts(); }

state.rangeH = null; // 14 d
state.train = [...P.trains].sort((a, b) => a.health - b.health)[0].id; // worst first
renderTiles();
renderFleetTable();
renderFilters();
renderScoped();
</script>
</body>
</html>
"""
