import time
from algorithms.fixed_window import FixedWindowLimiter
from algorithms.token_bucket import TokenBucketLimiter
from algorithms.sliding_window import SlidingWindowLimiter

def test_fixed_window():
    print("\n--- Fixed Window ---")
    limiter = FixedWindowLimiter(max_requests=3, window_seconds=5)
    for i in range(5):
        result = limiter.is_allowed("user_1")
        print(f"Request {i+1}: {'✓ allowed' if result['allowed'] else '✗ denied'} | {result}")

def test_token_bucket():
    print("\n--- Token Bucket ---")
    limiter = TokenBucketLimiter(capacity=3, refill_rate=1)
    for i in range(5):
        result = limiter.is_allowed("user_1")
        print(f"Request {i+1}: {'✓ allowed' if result['allowed'] else '✗ denied'} | {result}")

def test_sliding_window():
    print("\n--- Sliding Window ---")
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=5)
    for i in range(5):
        result = limiter.is_allowed("user_1")
        print(f"Request {i+1}: {'✓ allowed' if result['allowed'] else '✗ denied'} | {result}")

if __name__ == "__main__":
    test_fixed_window()
    test_token_bucket()
    test_sliding_window()