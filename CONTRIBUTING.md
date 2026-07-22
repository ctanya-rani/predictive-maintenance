# Contributing to TrainWatch

## Setup

### Prerequisites

- Python 3.10+
- Node.js 20+
- Git

### Local development

```bash
# Clone and setup
git clone https://github.com/ctanya-rani/predictive-maintenance
cd predictive-maintenance

# Backend
pip install -r requirements.txt
python -m pytest tests/

# Frontend
cd frontend
npm install
npm run lint
npm run build
```

### Using Docker Compose

```bash
docker-compose up
# Backend: http://localhost:5000
# Frontend: http://localhost:5173
```

## Code style

### Python

```bash
pip install flake8 black
black trainwatch tests api.py
flake8 trainwatch tests api.py --max-line-length=100
```

### TypeScript/React

```bash
cd frontend
npm run lint
npm run format
```

## Testing

### Backend

```bash
pytest tests/ -v
pytest tests/test_detect.py -v -k "bearing"  # specific test
pytest --cov=trainwatch --cov-report=html    # coverage report
```

### Frontend

```bash
cd frontend
npm run build
npm run preview  # test production build locally
```

### API

```bash
# Start server
python api.py &

# Test endpoints
curl http://localhost:5000/health
curl http://localhost:5000/api/fleet | jq '.health[0]'
curl http://localhost:5000/api/alerts?severity=crit
```

## Adding a detector

1. **Implement in `trainwatch/detect.py`**:
   ```python
   def _score_my_detector(channel, cfg):
       # Return boolean array of anomalies
       return some_anomalies
   ```

2. **Add to scoring loop**:
   ```python
   def _score_channel(channel, cfg):
       my_anomalies = _score_my_detector(channel, cfg)
       raise_to(my_anomalies, SEVERITY_RANK["warning"], "my_kind")
   ```

3. **Add tests** in `tests/test_detect.py`:
   ```python
   def test_my_detector_catches_faults(scored):
       ch = channel(scored, "T-103", "some_sensor")
       assert ch[ch["kinds"].str.contains("my_kind")].shape[0] > 0
   ```

4. **Tune thresholds** in `trainwatch/config.py`:
   ```python
   my_detector_threshold: float = 3.5
   ```

## Adding a sensor

1. **Update `trainwatch/config.py`**:
   ```python
   SENSORS["my_sensor"] = SensorSpec(
       key="my_sensor",
       label="My sensor label",
       unit="units",
       baseline=50.0,
       daily_amplitude=5.0,
       noise_sd=0.5,
       warn_high=80.0,
       crit_high=90.0,
       axis_min=0.0,
       axis_max=100.0,
   )
   ```

2. **Update `frontend/src/lib/trainwatch/config.ts`** to match

3. **Tests** auto-generate — no UI changes needed

## Adding a feature

### Example: Email alerts on critical faults

1. **Update API** (`api.py`):
   ```python
   from flask_mail import Mail, Message
   
   mail = Mail(app)
   
   @app.route("/api/alerts/email", methods=["POST"])
   def send_alert_email():
       alerts = request.json.get("alerts", [])
       for alert in alerts:
           if alert["severity"] == "crit":
               msg = Message(
                   subject=f"Critical alert: {alert['trainId']}",
                   recipients=["ops@example.com"],
                   body=alert["recommendation"]
               )
               mail.send(msg)
       return jsonify({"status": "sent"}), 200
   ```

2. **Update frontend** (`frontend/src/routes/index.tsx`):
   ```typescript
   <button
       onClick={() => sendAlertEmail(sim.alerts)}
       className="..."
   >
       Email critical alerts
   </button>
   ```

3. **Add tests**:
   ```python
   def test_email_alert_endpoint(client):
       response = client.post("/api/alerts/email", json={
           "alerts": [{"severity": "crit", ...}]
       })
       assert response.status_code == 200
   ```

## Opening a pull request

1. **Fork & branch**: `git checkout -b feature/my-feature`
2. **Make changes**: commit with clear messages
3. **Test**: `pytest tests/` and `npm run build`
4. **Push**: `git push origin feature/my-feature`
5. **PR**: describe what changed and why

### PR checklist

- [ ] Tests pass locally (`pytest` + `npm run build`)
- [ ] Code is linted (`flake8` + `npm run lint`)
- [ ] Docstrings/comments added for complex logic
- [ ] No secrets or credentials in commits
- [ ] Commit messages are clear (imperative: "Add", "Fix", "Improve")

## Deploying changes

### Staging

```bash
git push origin feature/branch
# Opens PR, runs CI tests automatically

# Once approved:
git checkout main
git pull origin main
docker-compose up
# Visit http://localhost:5173
```

### Production

See **[SETUP.md](SETUP.md)** for deployment options.

## Questions?

- Check **[ARCHITECTURE.md](ARCHITECTURE.md)** for design decisions
- Review **[openapi.yml](openapi.yml)** for API shapes
- Open an issue on GitHub

Thanks for contributing! 🚆
