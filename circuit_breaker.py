import time
import threading

class CircuitBreaker:
    """
    Circuit Breaker Pattern — three states:

    CLOSED   — normal operation, requests flow through
    OPEN     — backend is failing, requests blocked immediately
    HALF_OPEN — cooldown passed, testing if backend recovered

    Transitions:
    CLOSED -> OPEN       when failure_threshold is reached
    OPEN -> HALF_OPEN    after recovery_timeout seconds
    HALF_OPEN -> CLOSED  if test request succeeds
    HALF_OPEN -> OPEN    if test request fails again
    """

    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold   # failures before opening
        self.recovery_timeout  = recovery_timeout    # seconds before half-open
        self.success_threshold = success_threshold   # successes to close again

        # Per-backend state
        self._states:    dict = {}
        self._failures:  dict = {}
        self._successes: dict = {}
        self._opened_at: dict = {}
        self._lock = threading.Lock()

    def _get_state(self, backend: str) -> str:
        return self._states.get(backend, self.CLOSED)

    def is_allowed(self, backend: str) -> bool:
        """Check if request should be allowed through to this backend."""
        with self._lock:
            state = self._get_state(backend)

            if state == self.CLOSED:
                return True

            if state == self.OPEN:
                # Check if recovery timeout has passed
                elapsed = time.time() - self._opened_at.get(backend, 0)
                if elapsed >= self.recovery_timeout:
                    self._states[backend]   = self.HALF_OPEN
                    self._successes[backend] = 0
                    return True  # allow one test request
                return False  # still open, block request

            if state == self.HALF_OPEN:
                return True  # allow test requests through

        return True

    def record_success(self, backend: str) -> None:
        """Call this when a backend request succeeds."""
        with self._lock:
            state = self._get_state(backend)

            if state == self.HALF_OPEN:
                self._successes[backend] = self._successes.get(backend, 0) + 1
                if self._successes[backend] >= self.success_threshold:
                    # Backend recovered — close the circuit
                    self._states[backend]   = self.CLOSED
                    self._failures[backend] = 0
                    self._successes[backend] = 0

            elif state == self.CLOSED:
                # Reset failure count on success
                self._failures[backend] = 0

    def record_failure(self, backend: str) -> None:
        """Call this when a backend request fails."""
        with self._lock:
            self._failures[backend] = self._failures.get(backend, 0) + 1

            if self._failures[backend] >= self.failure_threshold:
                self._states[backend]   = self.OPEN
                self._opened_at[backend] = time.time()
                self._failures[backend] = 0

    def get_status(self) -> dict:
        """Get current state of all backends."""
        with self._lock:
            result = {}
            for backend in self._states:
                state = self._states[backend]
                result[backend] = {
                    "state":    state,
                    "failures": self._failures.get(backend, 0),
                    "opened_at": self._opened_at.get(backend, None)
                }
            return result