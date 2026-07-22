# Changelog

## [Unreleased]

### Added
- Auto-refresh toggle in web console (30s poll interval)
- Manual refresh button with loading spinner
- CSV export for alerts and fleet health
- Expanded API endpoints: `/api/train/<id>`, `/api/alerts`, `/api/sensor/<>/<>`
- API filtering: `?severity=crit&train_id=T-101&active=true`
- OpenAPI 3.0 specification (openapi.yml)
- GitHub Actions CI/CD pipeline
- Docker Compose for local development
- Dockerfiles for backend and frontend
- API test suite (9 new tests)
- Production deployment checklist (DEPLOYMENT.md)
- Architecture documentation (ARCHITECTURE.md)
- Contributing guide (CONTRIBUTING.md)
- Error handling and logging throughout API
- Request validation for query parameters
- Health check endpoints

### Changed
- React frontend now fetches from API instead of client-side simulation
- Improved error messages for user-facing errors
- API now caches simulation in memory on startup
- Frontend refetch capability for manual refresh

### Fixed
- Alert sorting in API responses
- Test coverage for new API endpoints

## [0.2.0] - 2026-07-22

### Added
- React web console with TanStack Start + TailwindCSS
- Fleet health dashboard with stat tiles
- Per-train detail view with sensor charts
- Alert feed with maintenance recommendations
- Time-range filters (24h, 3d, 7d, 14d)
- Light/dark mode support
- Flask API server wrapping Python backend
- CORS support for cross-origin requests
- Data aggregation to hourly buckets for charts
- Graceful fallback to client-side simulation if API unavailable

## [0.1.0] - 2026-07-17

### Added
- Python backend for predictive maintenance
  - Synthetic telemetry generator (8 trains, 4 sensors, 14 days, 10-min cadence)
  - Statistical anomaly detectors:
    - Seasonal robust z-score (spikes)
    - EWMA drift tracking (progressive degradation)
    - Stuck-channel detection (sensor failure)
    - Engineering limits (hard thresholds)
  - Alert engine with episode merging
  - Health scoring (0–100 per train)
  - Maintenance recommendations
- Static HTML dashboard
  - Self-contained single file (no build)
  - Interactive SVG charts with crosshair tooltips
  - Anomaly markers (warning/critical)
  - Fleet health metrics
  - Alert feed
  - Time-range filtering
  - Light/dark mode
  - Responsive layout
- Test suite (21 tests covering generation, detection, alerts)
- Documentation (README, SETUP guide)

---

## Version numbering

- **0.1.x**: Initial MVP (Python backend + static HTML dashboard)
- **0.2.x**: React frontend integration + API expansion
- **0.3.x** (planned): Real-time alerts + notifications + persistence
- **1.0**: Production-ready with full ops runbook

## Migration guide

### From 0.1 to 0.2

The static HTML dashboard still works, but is now optional:

```bash
# Old way (still works)
python -m trainwatch
open output/dashboard.html

# New way (recommended)
python api.py &
cd frontend && npm run dev
open http://localhost:5173
```

No changes needed to the Python backend or data format.

---

## Roadmap

### Near-term (v0.3)
- [ ] Kafka integration for real-time telemetry
- [ ] Email/Slack notifications on critical alerts
- [ ] Database persistence (PostgreSQL)
- [ ] Advanced detectors (multi-sensor correlation, seasonal patterns)
- [ ] User authentication (JWT)
- [ ] Alert history & trends

### Medium-term (v0.4)
- [ ] GraphQL API for flexible queries
- [ ] WebSocket for live updates
- [ ] Mobile app (React Native)
- [ ] Predictive modeling (predict MTBF)
- [ ] Cost calculator (maintenance vs. downtime)

### Long-term (v1.0+)
- [ ] Multi-site deployment
- [ ] Fleet comparison & benchmarking
- [ ] Predictive scheduling optimization
- [ ] Integration with maintenance scheduling systems
- [ ] Supply chain integration (parts inventory)
