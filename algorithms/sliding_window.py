import time
from collections import deque

class SlidingWindowLimiter:
    """
    Sliding Window Rate Limiter
    Tracks exact timestamps of each request.
    Looks at a rolling window from NOW, not a fixed clock boundary.
    Most accurate — cannot be gamed at window edges.
    More memory intensive than Fixed Window.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> deque of request timestamps
        self.store: dict = {}

    def is_allowed(self, client_id: str) -> dict:
        now = time.time()
        window_start = now - self.window_seconds

        if client_id not in self.store:
            self.store[client_id] = deque()

        timestamps = self.store[client_id]

        # Remove timestamps outside the current window
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) < self.max_requests:
            timestamps.append(now)
            return {
                "allowed": True,
                "remaining": self.max_requests - len(timestamps),
                "window_seconds": self.window_seconds
            }

        # Time until oldest request falls outside window
        retry_after = round(timestamps[0] - window_start, 2)
        return {
            "allowed": False,
            "remaining": 0,
            "retry_after": retry_after
        }