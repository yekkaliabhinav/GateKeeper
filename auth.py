import redis
import os
import secrets
import hashlib

class APIKeyAuth:
    """
    API Key Authentication backed by Redis.
    Keys are stored as hashes for security —
    raw key is never stored, only its SHA256 hash.
    """

    def __init__(self):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        self.redis = redis.Redis(host=host, port=port, decode_responses=True)

    def _hash_key(self, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def generate_key(self, client_id: str, tier: str = "free") -> str:
        """
        Generate a new API key for a client.
        Stores hashed key in Redis with metadata.
        """
        raw_key = f"gk_{secrets.token_urlsafe(32)}"
        hashed = self._hash_key(raw_key)

        self.redis.hset(f"apikey:{hashed}", mapping={
            "client_id": client_id,
            "tier": tier,           # free | pro | enterprise
            "active": "true"
        })

        return raw_key  # only time raw key is ever returned

    def validate_key(self, raw_key: str) -> dict:
        """
        Validate an API key.
        Returns client info if valid, None if invalid.
        """
        if not raw_key:
            return None

        hashed = self._hash_key(raw_key)
        data = self.redis.hgetall(f"apikey:{hashed}")

        if not data or data.get("active") != "true":
            return None

        return {
            "client_id": data["client_id"],
            "tier": data["tier"]
        }

    def revoke_key(self, raw_key: str) -> bool:
        """Revoke an API key."""
        hashed = self._hash_key(raw_key)
        exists = self.redis.exists(f"apikey:{hashed}")
        if exists:
            self.redis.hset(f"apikey:{hashed}", "active", "false")
            return True
        return False

    def list_keys(self) -> list:
        """List all registered client IDs and their tiers."""
        keys = self.redis.keys("apikey:*")
        result = []
        for k in keys:
            data = self.redis.hgetall(k)
            result.append({
                "client_id": data.get("client_id"),
                "tier": data.get("tier"),
                "active": data.get("active")
            })
        return result