import threading
import httpx
from circuit_breaker import CircuitBreaker

class LoadBalancer:
    def __init__(self):
        self.services: dict = {
            "payments": [
                "http://localhost:8001",
                "http://localhost:8002",
            ],
            "users": [
                "http://localhost:8003",
            ],
            "orders": [
                "http://localhost:8004",
                "http://localhost:8005",
            ],
        }
        self._counters: dict = {s: 0 for s in self.services}
        self._lock = threading.Lock()
        self.cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=2
        )

    def get_next(self, service: str) -> str | None:
        if service not in self.services:
            return None

        backends = self.services[service]
        if not backends:
            return None

        # Try each backend in round robin — skip open circuits
        with self._lock:
            start_idx = self._counters[service]
            for i in range(len(backends)):
                idx = (start_idx + i) % len(backends)
                backend = backends[idx]
                if self.cb.is_allowed(backend):
                    self._counters[service] = idx + 1
                    return backend

        return None  # all backends are open

    def register_service(self, service: str, urls: list) -> None:
        self.services[service] = urls
        self._counters[service] = 0

    def get_all_services(self) -> dict:
        return self.services

    async def forward_request(
        self,
        service: str,
        path: str,
        method: str,
        headers: dict,
        body: bytes = None
    ) -> dict:
        backend = self.get_next(service)

        if not backend:
            return {
                "success": False,
                "status_code": 503,
                "error": f"All backends for '{service}' are unavailable"
            }

        url = f"{backend}{path}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body
                )
                self.cb.record_success(backend)
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "body": response.text,
                    "backend": backend
                }

        except httpx.ConnectError:
            self.cb.record_failure(backend)
            return {
                "success": False,
                "status_code": 503,
                "error": f"Backend unreachable: {backend}"
            }

        except httpx.TimeoutException:
            self.cb.record_failure(backend)
            return {
                "success": False,
                "status_code": 504,
                "error": f"Backend timed out: {backend}"
            }