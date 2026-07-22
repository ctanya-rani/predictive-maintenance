# TrainWatch Architecture

## Overview

TrainWatch is a predictive maintenance platform for train fleet monitoring. It combines synthetic telemetry generation, statistical anomaly detection, alert processing, and a modern web interface.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Web Console                             │
│  (fleet health, train detail, sensor charts, alert feed)             │
└──────────────────┬──────────────────────────────────────────────────┘
                   │ HTTP/JSON
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Flask API Server                               │
│  /api/fleet, /api/train/<id>, /api/alerts, /api/sensor/<>/<>        │
└──────────────────┬──────────────────────────────────────────────────┘
                   │ Python
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TrainWatch Backend                               │
├──────────────────────────────────────────────────────────────────────┤
│  Generator   → Detect    → Alerts     → Score                        │
│  (synthetic    (anomaly   (episodes)   (health)                      │
│   telemetry)   detection)                                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Data flow

1. **Generation** (`trainwatch/generate.py`)
   - Creates synthetic telemetry for 8 trains × 4 sensor channels
   - 14-day history at 10-minute cadence (~64k samples)
   - Healthy duty cycle (daily service pattern) + injected faults

2. **Detection** (`trainwatch/detect.py`)
   - Scores each channel independently
   - Seasonal robust z-score (hour-of-day medians, detects spikes)
   - EWMA drift tracking (detects slow degradation)
   - Stuck-channel check (detects sensor failures)
   - Engineering limits (hard thresholds)

3. **Alerts** (`trainwatch/alerts.py`)
   - Merges consecutive anomalies into episodes (no point spam)
   - Assigns severity (warning/critical) and kind (spike/drift/stuck/limit)
   - Generates maintenance recommendations
   - Computes health scores per train (0–100)

4. **API** (`api.py`)
   - Flask server with CORS
   - `/api/fleet` — complete data (health, alerts, time-series)
   - `/api/train/<id>` — specific train detail
   - `/api/alerts` — filtered alerts with query params
   - `/api/sensor/<train>/<sensor>` — one channel's time-series
   - Caches simulation in memory (regenerated on startup)

5. **Frontend** (`frontend/`)
   - React + TanStack Start + TailwindCSS
   - Fetches from API, displays fleet console
   - Fallback to client-side simulation if API unavailable
   - Auto-refresh every 30s (optional)
   - CSV export for alerts & health

## Key design decisions

### Why synthetic data?

Real train sensor feeds require infrastructure (MQTT brokers, data lakes, 24/7 ops). Synthetic data demonstrates the full platform without those dependencies. Production use case:

```python
# Instead of generate_fleet_data(), read from kafka/API/database
data = fetch_from_production_feed()
scored = detect_anomalies(data)
```

### Why in-memory caching?

For a demo, regenerating the 14-day simulation on every request (~1s) is acceptable. For production with real data:

```python
# Cache scored results in Redis or a database
scored = redis.get("fleet:scored")
if not scored:
    scored = detect_anomalies(fetch_latest_data())
    redis.setex("fleet:scored", 300, scored)
```

### Why EWMA drift detection?

Hard limits catch failures, but only *after* they're critical. EWMA (exponentially weighted moving average) flags slow degradation days before the limit, giving maintenance teams time to act — the core value prop of predictive maintenance.

Example: a bearing heating up slowly. Hard limit (warning) triggers at 85°C. EWMA flags at 72°C when the trend is clear, leaving a 2-week window to schedule repair instead of emergency shutdown.

### Why health scores instead of just alerts?

A single high-priority fault shouldn't tank a train's overall score if only one channel is affected. Health scores weight active criticals heavily, but cap the penalty per channel so a bad bearing doesn't mask other problems.

```python
score = 100
for channel_penalties in grouped_by_channel:
    score -= min(channel_penalties[0] + 0.25 * sum(rest), 45)
# One bad channel can drop score by ~45 max, not 100
```

## Extending the system

### Add a new sensor type

1. **Add to config** (`trainwatch/config.py`):
   ```python
   SENSORS["diesel_level_pct"] = SensorSpec(
       key="diesel_level_pct",
       label="Diesel fuel level",
       unit="%",
       baseline=75.0,
       # ... more specs
   )
   ```

2. **Regenerate data** — `generate_fleet_data()` automatically includes it

3. **Add detector logic** (optional) in `trainwatch/detect.py`

4. **React UI** automatically renders charts for new sensors (no code change needed)

### Add a new detector

1. **Implement in `detect.py`** — compute a score per sample
2. **Mark anomalies** — flag which samples and severity
3. **Add to alerts** — the alert engine automatically picks it up
4. **Tune thresholds** in `DetectionConfig`

### Connect to real data

Replace `generate_fleet_data()` with a function that reads from your source:

```python
def get_real_fleet_data():
    # Read from Kafka, S3, database, HTTP API, etc.
    df = pd.read_csv("s3://bucket/train-telemetry.csv")
    return df[["timestamp", "train_id", "sensor", "value"]]

# In api.py:
data = get_real_fleet_data()  # instead of generate_fleet_data()
scored = detect_anomalies(data)
```

### Deploy at scale

Current: in-memory, single process, 14-day history.

Production scale-up:

1. **Data persistence** — PostgreSQL/TimescaleDB for telemetry
2. **Background job** — Celery/APScheduler for hourly anomaly detection
3. **Cache layer** — Redis for recent scores & alerts
4. **Async API** — ASGI (Quart/FastAPI) instead of Flask
5. **Message queue** — publish alerts to Kafka for downstream systems
6. **Monitoring** — Prometheus metrics, Sentry error tracking

## Testing

### Backend

```bash
pytest tests/
# test_generate.py    — determinism, fault signatures
# test_detect.py      — detector accuracy, false positives
# test_alerts.py      — episode merging, health scoring
# test_api.py         — API endpoints, response shapes
```

### Frontend

```bash
cd frontend
npm run lint
npm test  # (not yet added; run `npm install --save-dev vitest @testing-library/react`)
```

### End-to-end

```bash
python api.py &
cd frontend && npm run dev
# Open http://localhost:5173, check load, drill down, export CSV
```

## Performance notes

- **Generation** (~1s for 14 days) — memory-bound, not CPU-bound
- **Detection** (~2s) — scales O(n*detectors), parallelizable per channel
- **API response** (~10ms) — cached in memory, network I/O dominates
- **React render** (~100ms for all charts) — incremental updates via React.memo

For production data (years, 100+ trains, sub-minute cadence):
- Move detection to a background job (hourly batches)
- Cache results in a time-series database
- Paginate time-series queries (`?start=<t>&end=<t>&limit=1000`)

## Security notes

- **No authentication** in the current demo (add JWT, OAuth2 for production)
- **No data validation** on API inputs (add Pydantic models)
- **CORS enabled for localhost only** (configure for your domain)
- **No rate limiting** (add to prevent scraping)
- **Alert recommendations are static** (could be data-driven, monitor for abuse)

## Monitoring & observability

Add the following for production:

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

alerts_raised = Counter('trainwatch_alerts_raised_total', 'Alerts', ['severity'])
detection_time = Histogram('trainwatch_detection_seconds', 'Detection latency')

# Sentry error tracking
import sentry_sdk
sentry_sdk.init("https://your-project@sentry.io/123456")

# Structured logging
import structlog
structlog.configure(
    processors=[structlog.processors.JSONRenderer()]
)
logger = structlog.get_logger()
```

## References

- `SETUP.md` — deployment & ops
- `openapi.yml` — API specification
- `frontend/README.md` — React app guide
