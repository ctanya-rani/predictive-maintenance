# TrainWatch — predictive maintenance dashboard

A predictive-maintenance platform for a train fleet: synthetic sensor data with
injected faults → anomaly detection → maintenance alerts → interactive web
console.

Two frontends available:
- **Static HTML** (`output/dashboard.html`) — single file, no build, works offline
- **React web app** (`frontend/`) — modern UI, wired to Python API backend

![Dashboard (light mode)](docs/dashboard-light.png)

## Quick start

### Option 1: Static HTML dashboard (no build, no dependencies)

```bash
pip install -r requirements.txt
python -m trainwatch
```

Open `output/dashboard.html` in a browser. It's a single self-contained file.

### Option 2: React web app + API (modern UI, scalable)

**Terminal 1 — Backend API:**
```bash
pip install -r requirements.txt
python api.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install          # or bun install
npm run dev
```

Open `http://localhost:5173` in your browser.

See **[SETUP.md](SETUP.md)** for production deployment (Docker, gunicorn, etc.)

## What it does

### 1. Synthetic telemetry (`trainwatch/generate.py`)

8 trains × 4 sensor channels × 14 days at a 10-minute cadence (~64k samples).
Healthy behaviour is a daily duty cycle (morning/evening service peaks) plus
per-train character offsets and measurement noise. Four fault narratives are
injected on top:

| Train | Channel | Fault pattern |
|-------|---------|---------------|
| T-103 | Axle bearing temperature | accelerating drift — progressive bearing wear |
| T-105 | Bogie vibration (RMS) | intermittent spikes — developing wheel flat |
| T-102 | Brake pipe pressure | slow downward drift — air leak |
| T-107 | Traction motor current | frozen signal — failed transducer |

### 2. Anomaly detection (`trainwatch/detect.py`)

Each channel is scored against a baseline fitted on its own leading (healthy)
window:

- **Seasonal robust z-score** — hour-of-day medians + MAD scale, so the daily
  duty cycle isn't mistaken for a fault; flags *spikes*.
- **EWMA drift tracking** — control limits in units of the EWMA's own sigma;
  flags slow *drifts* days before any hard limit is crossed (the point of
  predictive maintenance — there's a test asserting exactly that).
- **Stuck-channel check** — rolling variance collapsing to zero flags a frozen
  transducer that limit checks would never catch.
- **Engineering limits** — conventional absolute warn/critical thresholds.

### 3. Alerts & health (`trainwatch/alerts.py`)

Consecutive anomalous samples merge into **episode alerts** (flicker-bridging,
no point spam) carrying severity, detector kind, time window, peak reading and
a maintenance recommendation. Per-train **health scores** (0–100) weight
active criticals heaviest, with diminishing penalties for repeat episodes on
the same channel.

### 4. Dashboard (`trainwatch/dashboard.py`)

One self-contained HTML file: fleet stat tiles, per-train health meters and
status, hourly sensor charts with anomaly markers and engineering-limit lines,
crosshair tooltips, per-chart data tables, time-range presets (24 h / 3 d /
7 d / 14 d), a train switcher (worst train pre-selected), the alert feed, and
automatic light/dark mode.

## Outputs

| File | Contents |
|------|----------|
| `output/dashboard.html` | the dashboard (open in a browser) |
| `output/telemetry.csv` | raw synthetic telemetry (tidy: timestamp, train, sensor, value) |
| `output/anomalies.csv` | every anomalous sample with scores, detectors and severity |
| `output/alerts.csv` | deduplicated alert episodes |

## Tests

```bash
python -m pytest
```

Covers generator determinism and fault signatures, detector hits and
false-positive behaviour (including "drift detected well before the hard
limit"), alert episode merging, health-score ranking, and the dashboard
payload shape.

## Project layout

```
trainwatch/               Python backend
├─ config.py            fleet, sensor specs, fault narratives
├─ generate.py          synthetic telemetry generator
├─ detect.py            statistical anomaly detectors
├─ alerts.py            episode alerts & health scores
├─ dashboard.py         HTML dashboard renderer
└─ __main__.py          pipeline CLI

api.py                   Flask API server (serves /api/fleet)
SETUP.md                 Deployment guide

frontend/                React + TanStack Start
├─ src/routes/          page routes (fleet console, etc.)
├─ src/components/      UI components (charts, train list)
├─ src/hooks/           useFleetData (API fetcher)
├─ src/lib/             config, simulation (fallback)
└─ package.json         dependencies

tests/                   pytest suite
output/                  generated telemetry & dashboard
```

## Architecture

```
                    Static HTML
                   (single file)
                        │
Python → Generate       ├─→ JSON payload
Backend  + Detect       │   (embedded)
         + Score        │
                        ├─→ Serve as API
                        │
                  React Frontend
                   (http://localhost:5173)
                        │
                   fetch /api/fleet
                        │
                   Display & filter
```
