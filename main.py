import time
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from limiter import RedisRateLimiter
from auth import APIKeyAuth
from load_balancer import LoadBalancer
from prometheus_fastapi_instrumentator import Instrumentator
from logger import RequestLogger

app = FastAPI(title="GateKeeper", version="3.0.0")
Instrumentator().instrument(app).expose(app)
limiter = RedisRateLimiter()
auth = APIKeyAuth()
lb = LoadBalancer()
logger = RequestLogger()

TIER_CONFIG = {
    "free":       {"max_requests": 10,  "window_seconds": 60},
    "pro":        {"max_requests": 100, "window_seconds": 60},
    "enterprise": {"max_requests": 1000,"window_seconds": 60},
}

app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Dashboard ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    with open("static/index.html") as f:
        return f.read()

# ── Key Management ───────────────────────────────────────────
@app.post("/keys/generate")
def generate_key(client_id: str, tier: str = "free"):
    key = auth.generate_key(client_id, tier)
    return {
        "client_id": client_id,
        "tier": tier,
        "api_key": key,
        "message": "Store this key safely — it won't be shown again"
    }

@app.post("/keys/revoke")
def revoke_key(api_key: str):
    success = auth.revoke_key(api_key)
    return {"revoked": success}

@app.get("/keys/list")
def list_keys():
    return {"clients": auth.list_keys()}

# ── Service Registry ─────────────────────────────────────────
@app.get("/services")
def list_services():
    """List all registered backend services."""
    return {"services": lb.get_all_services()}

@app.post("/services/register")
def register_service(service: str, urls: str):
    """
    Dynamically register a new service.
    urls should be comma-separated: http://host1,http://host2
    """
    url_list = [u.strip() for u in urls.split(",")]
    lb.register_service(service, url_list)
    return {"service": service, "backends": url_list}

# ── Main Gateway Endpoint ────────────────────────────────────
@app.api_route(
    "/gateway/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    tags=["Gateway"],
    operation_id="gateway"
)
async def gateway(
    service: str,
    path: str = "",
    request: Request = None,
    x_api_key: str = Header(None)
):
    trace_id = logger.generate_trace_id()
    start_time = time.time()

    # Layer 1 — Auth
    client = auth.validate_key(x_api_key)
    if not client:
        latency = (time.time() - start_time) * 1000
        logger.log(
            trace_id=trace_id,
            client_id="unknown",
            tier="none",
            service=service,
            method=request.method,
            allowed=False,
            status_code=401,
            latency_ms=latency,
            error="Invalid or missing API key"
        )
        return JSONResponse(
            status_code=401,
            content={
                "error": "Invalid or missing API key",
                "trace_id": trace_id
            }
        )

    client_id = client["client_id"]
    tier = client["tier"]

    # Layer 2 — Rate limiting
    cfg = TIER_CONFIG[tier]
    result = limiter.sliding_window(
        client_id,
        cfg["max_requests"],
        cfg["window_seconds"]
    )

    # Track stats
    limiter.redis.incr("stats:total")
    limiter.redis.incr("stats:allowed" if result["allowed"] else "stats:denied")
    limiter.redis.hincrby(f"client_stats:{client_id}", "total", 1)
    limiter.redis.hincrby(
        f"client_stats:{client_id}",
        "allowed" if result["allowed"] else "denied", 1
    )

    if not result["allowed"]:
        latency = (time.time() - start_time) * 1000
        logger.log(
            trace_id=trace_id,
            client_id=client_id,
            tier=tier,
            service=service,
            method=request.method,
            allowed=False,
            status_code=429,
            latency_ms=latency,
            error="Rate limit exceeded"
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "trace_id": trace_id,
                "client_id": client_id,
                "tier": tier,
                **result
            }
        )

    # Layer 3 — Load balanced routing
    body = await request.body()
    forward_result = await lb.forward_request(
        service=service,
        path=f"/{path}",
        method=request.method,
        headers=dict(request.headers),
        body=body
    )

    latency = (time.time() - start_time) * 1000

    logger.log(
        trace_id=trace_id,
        client_id=client_id,
        tier=tier,
        service=service,
        method=request.method,
        allowed=forward_result["success"],
        status_code=forward_result["status_code"],
        latency_ms=latency,
        backend=forward_result.get("backend"),
        error=forward_result.get("error")
    )

    if not forward_result["success"]:
        return JSONResponse(
            status_code=forward_result["status_code"],
            content={
                "error": forward_result["error"],
                "trace_id": trace_id,
                "client_id": client_id,
                "service": service
            }
        )

    return JSONResponse(
        status_code=forward_result["status_code"],
        content={
            "trace_id": trace_id,
            "client_id": client_id,
            "tier": tier,
            "service": service,
            "backend": forward_result["backend"],
            "remaining": result["remaining"],
            "response": forward_result["body"]
        }
    )

# ── Stats ────────────────────────────────────────────────────
@app.get("/stats")
def get_global_stats():
    return {
        "total":   int(limiter.redis.get("stats:total") or 0),
        "allowed": int(limiter.redis.get("stats:allowed") or 0),
        "denied":  int(limiter.redis.get("stats:denied") or 0),
    }

@app.get("/stats/{client_id}")
def get_client_stats(client_id: str):
    data = limiter.redis.hgetall(f"client_stats:{client_id}")
    return {
        "client_id": client_id,
        "total":   int(data.get("total", 0)),
        "allowed": int(data.get("allowed", 0)),
        "denied":  int(data.get("denied", 0))
    }

@app.get("/circuit-breaker/status")
def circuit_breaker_status():
    """See the state of all backend circuit breakers."""
    return {"backends": lb.cb.get_status()}

@app.get("/logs", tags=["Observability"])
def get_logs(limit: int = 50):
    """Get recent request logs with trace IDs."""
    return {"logs": logger.get_recent(limit)}

@app.get("/logs/trace/{trace_id}", tags=["Observability"])
def get_log_by_trace(trace_id: str):
    """Look up a specific request by trace ID."""
    entry = logger.get_by_trace_id(trace_id)
    if not entry:
        return JSONResponse(status_code=404, content={"error": "Trace ID not found"})
    return entry

@app.get("/logs/client/{client_id}", tags=["Observability"])
def get_logs_by_client(client_id: str):
    """Get all logs for a specific client."""
    return {"logs": logger.get_by_client(client_id)}