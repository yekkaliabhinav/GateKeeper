import time

class TokenBucketLimiter:
    """
    Token Bucket Rate Limiter
    Bucket fills with tokens at a steady rate.
    Each request consumes one token.
    Allows natural bursting up to bucket capacity.
    Used by AWS, Stripe, and most real-world APIs.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity     -- max tokens bucket can hold (burst limit)
        refill_rate  -- tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        # key -> (current_tokens, last_refill_time)
        self.store: dict = {}

    def _refill(self, record: dict, now: float) -> None:
        elapsed = now - record["last_refill"]
        new_tokens = elapsed * self.refill_rate
        record["tokens"] = min(self.capacity, record["tokens"] + new_tokens)
        record["last_refill"] = now

    def is_allowed(self, client_id: str) -> dict:
        now = time.time()

        if client_id not in self.store:
            self.store[client_id] = {
                "tokens": self.capacity,
                "last_refill": now
            }

        record = self.store[client_id]
        self._refill(record, now)

        if record["tokens"] >= 1:
            record["tokens"] -= 1
            return {
                "allowed": True,
                "remaining_tokens": int(record["tokens"]),
                "refill_rate": self.refill_rate
            }

        return {
            "allowed": False,
            "remaining_tokens": 0,
            "retry_after": round(1 / self.refill_rate, 2)
        }