import time
import redis
import os

class RedisRateLimiter:
    """
    Redis-backed Rate Limiter
    All state stored in Redis — works correctly across
    multiple instances of the app running simultaneously.
    """

    def __init__(self):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        self.redis = redis.Redis(host=host, port=port, decode_responses=True)

    # ── Fixed Window ────────────────────────────────────────────
    def fixed_window(self, client_id: str, max_requests: int, window_seconds: int) -> dict:
        key = f"fw:{client_id}"
        now = time.time()
        window_key = f"{key}:{int(now // window_seconds)}"

        pipe = self.redis.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds)
        count, _ = pipe.execute()

        allowed = count <= max_requests
        return {
            "allowed": allowed,
            "algorithm": "fixed_window",
            "remaining": max(0, max_requests - count),
            "reset_in": window_seconds - (now % window_seconds)
        }

    # ── Token Bucket ─────────────────────────────────────────────
    def token_bucket(self, client_id: str, capacity: int, refill_rate: float) -> dict:
        key = f"tb:{client_id}"
        now = time.time()

        data = self.redis.hgetall(key)
        if not data:
            tokens = float(capacity)
            last_refill = now
        else:
            tokens = float(data["tokens"])
            last_refill = float(data["last_refill"])

        # Refill tokens based on time elapsed
        elapsed = now - last_refill
        tokens = min(capacity, tokens + elapsed * refill_rate)

        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False

        self.redis.hset(key, mapping={"tokens": tokens, "last_refill": now})
        self.redis.expire(key, int(capacity / refill_rate) + 10)

        return {
            "allowed": allowed,
            "algorithm": "token_bucket",
            "remaining_tokens": int(tokens),
            "retry_after": round(1 / refill_rate, 2) if not allowed else 0
        }

    # ── Sliding Window ───────────────────────────────────────────
    def sliding_window(self, client_id: str, max_requests: int, window_seconds: int) -> dict:
        key = f"sw:{client_id}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)   # remove old entries
        pipe.zadd(key, {str(now): now})                # add current request
        pipe.zcard(key)                                # count requests in window
        pipe.expire(key, window_seconds)
        _, _, count, _ = pipe.execute()

        allowed = count <= max_requests
        if not allowed:
            # remove the request we just added since it's denied
            self.redis.zrem(key, str(now))

        return {
            "allowed": allowed,
            "algorithm": "sliding_window",
            "remaining": max(0, max_requests - count),
            "window_seconds": window_seconds
        }