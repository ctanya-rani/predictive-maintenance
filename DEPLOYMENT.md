# Production Deployment Checklist

## Pre-deployment

- [ ] All tests passing: `pytest tests/ -v`
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] No secrets in code (check `.env`, keys, tokens, passwords)
- [ ] Environment variables documented in `SETUP.md`
- [ ] Database migrations run (if applicable)
- [ ] Backups verified

## Infrastructure

### Database (if using)
- [ ] PostgreSQL or equivalent running
- [ ] Connection pool configured (max 20 connections)
- [ ] Indexes created for time-series queries
- [ ] Backups automated (hourly, 30-day retention)
- [ ] Monitoring configured (CPU, memory, disk)

### Load Balancer
- [ ] Health check endpoint: `GET /health`
- [ ] SSL/TLS certificate installed
- [ ] CORS headers configured for your domain
- [ ] Rate limiting enabled (100 req/min per IP)
- [ ] DDoS mitigation active

### Monitoring & Alerts
- [ ] Sentry or equivalent for error tracking
- [ ] Prometheus metrics endpoint active
- [ ] Dashboards created (latency, error rate, alerts)
- [ ] On-call rotation configured
- [ ] Alerts routed to Slack/PagerDuty

## Application config

### Flask/Gunicorn
```bash
# .env
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
DATABASE_URL=postgresql://user:pass@localhost/trainwatch
REDIS_URL=redis://localhost:6379/0
SENTRY_DSN=https://...@sentry.io/...
```

### Gunicorn (use this, not Flask dev server)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 60 --access-logfile - api:app
```

### React frontend
```bash
# .env.production
VITE_API_URL=https://api.your-domain.com
```

### Rate limiting
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route("/api/fleet")
@limiter.limit("100 per minute")
def get_fleet():
    ...
```

### Caching
```python
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'redis'})

@app.route("/api/fleet")
@cache.cached(timeout=300)
def get_fleet():
    ...
```

## Security

### Authentication
- [ ] JWT tokens for API access
- [ ] Token expiration (15 min access, 30 day refresh)
- [ ] OAuth2 for web console (GitHub, Google, etc.)

### Authorization
- [ ] RBAC (role-based access control) configured
- [ ] Admin, viewer, operator roles defined
- [ ] Train access scoped by region/depot

### Input validation
```python
from pydantic import BaseModel

class AlertFilter(BaseModel):
    severity: Optional[str] = None  # "crit" or "warn"
    train_id: Optional[str] = None
    active_only: bool = False

@app.route("/api/alerts")
def get_alerts():
    filters = AlertFilter(**request.args.to_dict())
    ...
```

### Data protection
- [ ] Database encrypted at rest
- [ ] SSL/TLS for all traffic
- [ ] API keys rotated quarterly
- [ ] Access logs retained 90 days
- [ ] GDPR compliant (user data can be deleted)

## Performance

### Database
- [ ] Query indexes on (train_id, sensor, timestamp)
- [ ] Time-series partitioning by month
- [ ] Connection pooling (PgBouncer)
- [ ] Slow query logging enabled

### Caching strategy
```
GET /api/fleet
  ├─ Redis cache (5 min)
  └─ Fallback to generate if miss

GET /api/train/<id>
  ├─ Redis cache (1 min)
  └─ Live database query

GET /api/sensor/<>/<>
  ├─ No cache (time-range specific)
  └─ Direct database query
```

### Frontend
- [ ] Gzip compression enabled
- [ ] Service worker for offline caching
- [ ] Code split by route
- [ ] Image optimization (JPEG/WebP)
- [ ] CSS/JS minified

### Monitoring queries
```bash
# Database size
SELECT pg_size_pretty(pg_database_size('trainwatch'));

# Slow queries (> 1 sec)
SELECT query, calls, mean_time FROM pg_stat_statements WHERE mean_time > 1000;

# Cache hit ratio
redis-cli INFO stats | grep keyspace_hits
```

## Rollback plan

- [ ] Keep previous version available (blue/green deployment)
- [ ] Database migrations reversible
- [ ] Secrets & API keys unchanged (version-agnostic)
- [ ] Rollback runbook written

```bash
# Rollback script
#!/bin/bash
CURRENT=$(git rev-parse HEAD)
git checkout v1.2.3  # previous stable version
docker-compose restart backend
# Verify: curl https://api.your-domain.com/health
```

## Post-deployment

- [ ] Smoke tests pass (curl all endpoints)
- [ ] Frontend loads without errors (check console)
- [ ] Sample alerts generate and appear
- [ ] CSV export works
- [ ] Email/Slack notifications fire (if configured)
- [ ] Performance metrics within SLA (< 500ms p95)
- [ ] Monitoring dashboards show normal baselines

## Ongoing maintenance

- [ ] Weekly: backup verification
- [ ] Monthly: security patches (dependencies)
- [ ] Quarterly: database maintenance (analyze, vacuum)
- [ ] Quarterly: log rotation
- [ ] As-needed: capacity planning (disk, CPU)

## Incident response

**If /api/fleet returns 500:**
1. Check logs: `docker logs -f trainwatch_backend`
2. Check database: `psql -c "SELECT COUNT(*) FROM telemetry"`
3. Restart: `docker-compose restart backend`
4. If persists, rollback to last stable version

**If frontend loads but API is down:**
1. Client-side simulation activates (fallback)
2. User sees stale data, "offline" indicator
3. No loss of functionality

**If database is slow:**
1. Check connections: `SELECT count(*) FROM pg_stat_activity`
2. Kill idle: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE idle_in_transaction_session_timeout`
3. Analyze: `ANALYZE trainwatch_telemetry`

## Cost estimation (AWS example)

| Component | Size | Cost |
|-----------|------|------|
| EC2 (backend) | t3.medium (2 vCPU, 4GB) | $30/mo |
| RDS (PostgreSQL) | db.t3.small (1 vCPU, 2GB, 1TB storage) | $50/mo |
| ElastiCache (Redis) | cache.t3.micro | $15/mo |
| Load Balancer (ALB) | 1 ALB, 1M req/mo | $20/mo |
| Data transfer | 10 GB/mo outbound | $10/mo |
| **Total** | | **~$125/mo** |

For 100 trains, 4 sensors, 10-min cadence: ~50GB/month growth.

## Scaling (10,000 trains)

- [ ] Data warehouse (Snowflake, BigQuery)
- [ ] Time-series database (InfluxDB, TimescaleDB)
- [ ] Message queue (Kafka) for real-time alerts
- [ ] Stream processor (Flink, Spark Streaming)
- [ ] Microservices: generate, detect, alert as separate services
- [ ] GraphQL API for flexible queries
- [ ] Multi-region deployment

See ARCHITECTURE.md for more.
