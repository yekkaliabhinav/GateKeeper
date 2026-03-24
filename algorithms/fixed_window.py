import time

class FixedWindowLimiter:
    """
    Fixed Window Rate Limiter
    Counts requests in a fixed time window (e.g. 0-60s, 60-120s).
    Simple but vulnerable to burst at window boundaries.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> (request_count, window_start_time)
        self.store: dict = {}

    def is_allowed(self, client_id: str) -> dict:
        now = time.time()
        
        if client_id not in self.store:
            self.store[client_id] = {"count": 0, "window_start": now}
    
        record = self.store[client_id]
        window_elapsed = now - record["window_start"]

        # Reset window if expired
        if window_elapsed >= self.window_seconds:
            record["count"] = 0
            record["window_start"] = now

        if record["count"] < self.max_requests:
            record["count"] += 1
            return {
                "allowed": True,
                "remaining": self.max_requests - record["count"],
                "reset_in": round(self.window_seconds - window_elapsed, 2)
            }
        
        return {
            "allowed": False,
            "remaining": 0,
            "reset_in": round(self.window_seconds - window_elapsed, 2)
        }