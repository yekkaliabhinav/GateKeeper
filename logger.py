import time
import uuid
import json
import os
import redis

class RequestLogger:
    """
    Structured request logger with trace IDs.
    Every request gets a unique trace_id for end-to-end tracking.
    Logs stored in Redis as a capped list (last 1000 requests).
    """

    MAX_LOGS = 1000

    def __init__(self):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        self.redis = redis.Redis(host=host, port=port, decode_responses=True)

    def generate_trace_id(self) -> str:
        return f"req_{uuid.uuid4().hex[:12]}"

    def log(
        self,
        trace_id: str,
        client_id: str,
        tier: str,
        service: str,
        method: str,
        allowed: bool,
        status_code: int,
        latency_ms: float,
        backend: str = None,
        error: str = None
    ) -> None:
        entry = {
            "trace_id":   trace_id,
            "client_id":  client_id,
            "tier":       tier,
            "service":    service,
            "method":     method,
            "allowed":    allowed,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "backend":    backend,
            "error":      error,
            "timestamp":  time.time()
        }
        self.redis.lpush("request_logs", json.dumps(entry))
        self.redis.ltrim("request_logs", 0, self.MAX_LOGS - 1)

    def get_recent(self, limit: int = 50) -> list:
        logs = self.redis.lrange("request_logs", 0, limit - 1)
        return [json.loads(l) for l in logs]

    def get_by_trace_id(self, trace_id: str) -> dict | None:
        logs = self.redis.lrange("request_logs", 0, self.MAX_LOGS - 1)
        for l in logs:
            entry = json.loads(l)
            if entry["trace_id"] == trace_id:
                return entry
        return None

    def get_by_client(self, client_id: str, limit: int = 20) -> list:
        logs = self.redis.lrange("request_logs", 0, self.MAX_LOGS - 1)
        result = []
        for l in logs:
            entry = json.loads(l)
            if entry["client_id"] == client_id:
                result.append(entry)
            if len(result) >= limit:
                break
        return result