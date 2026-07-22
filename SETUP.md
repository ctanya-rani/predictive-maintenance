# TrainWatch — Setup & Deployment

This guide covers running TrainWatch with the React frontend wired to the Python backend.

## Architecture

```
┌─────────────────────┐         ┌──────────────────┐
│  React Frontend     │ HTTP    │  Flask API       │
│  (port 5173)        │◄───────►│  (port 5000)     │
│  - Fleet console    │         │  - Generate data │
│  - Train detail     │         │  - Detect        │
│  - Alert feed       │         │  - Score         │
└─────────────────────┘         └──────────────────┘
                                        ▲
                                        │
                                 Python backend
                                 (trainwatch/)
```

## Quick start (local dev)

### 1. Backend (Python)

```bash
pip install -r requirements.txt
python api.py
```

The API starts on `http://localhost:5000` and serves `/api/fleet` with synthetic data.

### 2. Frontend (React)

In a separate terminal:

```bash
cd frontend
npm install         # or 'bun install'
npm run dev         # or 'bun dev'
```

The app starts on `http://localhost:5173` and fetches data from the API.

Open **http://localhost:5173** in your browser. You'll see:
- Fleet health summary (4 stat tiles)
- Train list (sorted by health, worst first)
- Selected train's sensor charts (4 channels × 14 days)
- Alert feed (fleet-wide, sorted by severity)

---

## Production deployment

### Option 1: Traditional stack (Recommended)

**Backend:** Deploy `api.py` as a service
```bash
# Using gunicorn (production WSGI server)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api:app
```

**Frontend:** Build and serve static files
```bash
cd frontend
npm run build
# Serve the dist/ folder on your web server (nginx, apache, etc.)
# Point VITE_API_URL env var to your backend URL
```

### Option 2: Docker (Single container)

```dockerfile
FROM python:3.11-slim as backend
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY trainwatch/ trainwatch/
COPY api.py .

FROM node:20-alpine as frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock* ./
RUN npm ci
COPY frontend/src frontend/src
COPY frontend/*.json frontend/*.ts frontend/
ENV VITE_API_URL=http://localhost:5000
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY trainwatch/ trainwatch/
COPY api.py .
COPY --from=frontend /app/frontend/dist /app/static

EXPOSE 5000
CMD ["python", "api.py"]
```

Then serve the React build as static files from the Flask app (see below).

### Option 3: Flask serving static files

Update `api.py` to serve the React build:

```python
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

# Catch-all for React Router
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    if path and path.startswith('api'):
        return jsonify({"error": "404"}), 404
    return send_from_directory(app.static_folder, 'index.html')
```

Then:
```bash
cd frontend && npm run build
python api.py
# Open http://localhost:5000
```

---

## Environment variables

### Frontend (`frontend/.env` or shell)

```bash
VITE_API_URL=http://your-api-server:5000
```

### Backend (optional)

```bash
TRAINWATCH_DAYS=14          # History length
TRAINWATCH_SEED=20260717    # Reproducible data
FLASK_ENV=production
FLASK_DEBUG=0
```

---

## Troubleshooting

### "Failed to fetch fleet data"

**Problem:** React app can't reach the API.

**Solutions:**
1. Check backend is running: `curl http://localhost:5000/health`
2. Check CORS: the Flask app has `flask_cors` enabled
3. Check network: if frontend and backend are on different hosts, ensure they can reach each other
4. Check env var: `echo $VITE_API_URL` or check browser DevTools

### "Fallback also failed"

**Problem:** Both API and client-side simulation failed.

**Solutions:**
1. Check React console for errors
2. Verify `trainwatch/` Python package is importable
3. Check if synthetic data generation is working: `python -m trainwatch`

### Port 5000 already in use

**Solution:**
```bash
# Use a different port
python -c "
from api import app
app.run(port=5001, host='0.0.0.0')
"

# Update frontend env var
export VITE_API_URL=http://localhost:5001
```

---

## API reference

### `GET /api/fleet`

Returns complete fleet simulation data:

```json
{
  "historyEndMs": 1721509200000,
  "health": [
    {
      "trainId": "T-103",
      "score": 55.0,
      "status": "watch",
      "activeAlerts": 1
    }
  ],
  "alerts": [
    {
      "id": "T-103:axle_bearing_temp_c:2026-07-17T09:30:00",
      "trainId": "T-103",
      "sensor": "axle_bearing_temp_c",
      "severity": "crit",
      "detector": "drift",
      "startedTs": 1721508600000,
      "endTs": 1721509200000,
      "active": true,
      "peak": 99.8,
      "recommendation": "Schedule bearing inspection; check lubrication..."
    }
  ],
  "series": {
    "T-101": {
      "axle_bearing_temp_c": {
        "t0": 1720742400,
        "dt": 3600,
        "mean": [56.2, 57.1, ...],
        "sev": [0, 0, ...],
        "anom": [0, 0, ...]
      }
    }
  },
  "totalSamples": 64512
}
```

### `GET /health`

Health check:

```json
{ "status": "ok" }
```

---

## Development notes

### Adding a new detector

1. Update `trainwatch/detect.py` with the new scoring function
2. Run tests: `python -m pytest`
3. Restart the API: it will regenerate data with the new detector
4. React frontend automatically picks it up (no code change needed)

### Changing simulation parameters

Edit `trainwatch/config.py`:
- `SENSORS` — add/modify sensor specs
- `FAULTS` — change fault narratives
- `DETECTION` — tune detector thresholds

Restart the API to apply changes.

### Modifying the React UI

```bash
cd frontend
npm run dev    # Watch mode
npm run build  # Production build
npm run lint   # Check code style
```

Changes to `src/routes/` or `src/components/` auto-reload in dev mode.
