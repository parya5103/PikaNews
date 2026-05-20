import os
import hashlib
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)

class RedisCachePipeline:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_url = os.getenv("REDIS_URL") or config.get("redis", {}).get("url", "redis://localhost:6379/0")
        self.ttl = config.get("redis", {}).get("ttl_seconds", 1800)
        self.client: Optional[aioredis.Redis] = None

    async def connect(self):
        """Establish async connection to Redis backend."""
        try:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.client.ping()
            logger.info("Connected to Redis cache", url=self.redis_url)
        except Exception as e:
            logger.warn("Failed to connect to Redis, caching will be bypassed", error=str(e))
            self.client = None

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[str]:
        """Fetch value from cache."""
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warn("Redis GET failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self.client:
            return False
        try:
            expire_ttl = ttl or self.ttl
            await self.client.set(key, value, ex=expire_ttl)
            return True
        except Exception as e:
            logger.warn("Redis SET failed", key=key, error=str(e))
            return False

    async def get_etag_or_last_modified(self, url: str) -> Dict[str, Optional[str]]:
        """Fetch ETag/Last-Modified caching headers for target URL to respect server HTTP cache."""
        result = {"etag": None, "last_modified": None}
        if not self.client:
            return result
            
        try:
            key = f"http_headers:{hashlib.sha256(url.encode()).hexdigest()}"
            data = await self.client.get(key)
            if data:
                import json
                result = json.loads(data)
        except Exception as e:
            logger.warn("Failed to get ETag cache", url=url, error=str(e))
        return result

    async def save_etag_and_last_modified(self, url: str, etag: Optional[str], last_modified: Optional[str]) -> bool:
        """Save returned ETag and Last-Modified headers for target URL."""
        if not self.client or (not etag and not last_modified):
            return False
            
        try:
            key = f"http_headers:{hashlib.sha256(url.encode()).hexdigest()}"
            import json
            data = json.dumps({"etag": etag, "last_modified": last_modified})
            # Cache HTTP headers for 24 hours
            await self.client.set(key, data, ex=86400)
            return True
        except Exception as e:
            logger.warn("Failed to set ETag cache", url=url, error=str(e))
            return False
