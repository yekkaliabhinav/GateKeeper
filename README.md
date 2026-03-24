# GateKeeper

A production-grade API Gateway built from scratch with Python, FastAPI, and Redis.

## Features

**Core gateway**
- Rate limiting with 3 algorithms — Token Bucket, Sliding Window, Fixed Window
- API Key authentication with SHA256 hashing and tier-based limits
- Round-robin load balancing across multiple backend instances
- Circuit breaker pattern — closed, open, half-open states
- Per-client custom rate limit configuration

**Observability**
- Structured request logging with unique trace IDs
- Latency tracking per request
- Prometheus metrics at /metrics
- Real-time dashboard with allow/deny stats

**Infrastructure**
- Redis-backed distributed state — works across multiple instances
- Docker Compose for one-command local setup
- Deployed on Railway

## Tech stack
Python · FastAPI · Redis · Docker · Prometheus

## Architecture
Every request passes through 3 layers in order:
1. API Key Auth — validates key, identifies client and tier
2. Rate Limiter — enforces limits based on tier or custom config
3. Load Balancer — routes to next healthy backend (circuit breaker skips failing ones)

## Running locally

### With Docker
docker-compose up --build

### Without Docker
pip install -r requirements.txt
python -m uvicorn main:app --reload

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /gateway/{service}/{path} | Main gateway endpoint |
| POST | /keys/generate | Generate API key |
| POST | /keys/revoke | Revoke API key |
| GET | /keys/list | List all clients |
| POST | /config/{client_id} | Set custom rate limit |
| GET | /config/{client_id} | Get active config |
| GET | /logs | Recent request logs |
| GET | /logs/trace/{trace_id} | Look up by trace ID |
| GET | /circuit-breaker/status | Circuit breaker states |
| GET | /services | Registered backends |
| GET | /metrics | Prometheus metrics |
| GET | /stats | Global allow/deny stats |

## Live demo
[Railway deployment link here]
