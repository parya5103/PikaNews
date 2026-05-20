import asyncio
import os
import random
import time
import aiohttp
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)

# List of 25 real User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/119.0 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-A205F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warn("Circuit breaker opened due to failures", threshold=self.failure_threshold)

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def can_attempt(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.cooldown_seconds:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker in HALF-OPEN state, attempting connection")
                return True
            return False
        return True


class ScraperEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.proxies: List[str] = []
        self._load_proxies()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # Build semaphores per source based on their concurrency limits
        for src in config.get("sources", []):
            name = src["name"]
            limit = src.get("concurrency_limit", 2)
            self.semaphores[name] = asyncio.Semaphore(limit)
            self.circuit_breakers[name] = CircuitBreaker(
                failure_threshold=config.get("scraping", {}).get("circuit_breaker_failures", 3),
                cooldown_seconds=config.get("scraping", {}).get("circuit_breaker_cooldown_seconds", 300)
            )

    def _load_proxies(self):
        proxies_file = self.config.get("scraping", {}).get("proxies_file", "proxies.txt")
        if os.path.exists(proxies_file):
            try:
                with open(proxies_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            self.proxies.append(line)
                logger.info("Loaded proxies from file", count=len(self.proxies), file=proxies_file)
            except Exception as e:
                logger.error("Failed to load proxies", error=str(e))

    def _get_random_proxy(self) -> Optional[str]:
        if self.proxies:
            return random.choice(self.proxies)
        return None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.5",
            "Connection": "keep-alive"
        }

    async def fetch(self, source_name: str, url: str, response_format: str = "text") -> Optional[Any]:
        """Fetch content from an URL asynchronously respecting rate limits and circuit breaker."""
        cb = self.circuit_breakers.setdefault(source_name, CircuitBreaker())
        sem = self.semaphores.setdefault(source_name, asyncio.Semaphore(2))

        if not cb.can_attempt():
            logger.warn("Request skipped: Circuit breaker is OPEN for source", source=source_name, url=url)
            return None

        # Config limits
        retries = self.config.get("scraping", {}).get("retry_count", 3)
        backoff_factor = self.config.get("scraping", {}).get("retry_backoff_factor", 2.0)
        timeout_sec = self.config.get("scraping", {}).get("timeout_seconds", 30)

        async with sem:
            for attempt in range(1, retries + 1):
                proxy = self._get_random_proxy()
                headers = self._get_headers()
                
                try:
                    logger.debug("Fetching URL", source=source_name, url=url, attempt=attempt, proxy=proxy)
                    timeout = aiohttp.ClientTimeout(total=timeout_sec)
                    
                    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                        async with session.get(url, proxy=proxy) as response:
                            if response.status == 200:
                                cb.record_success()
                                if response_format == "bytes":
                                    return await response.read()
                                elif response_format == "json":
                                    return await response.json()
                                else:
                                    return await response.text()
                            
                            # Handle bad statuses as failures
                            logger.warn("Non-200 response code", source=source_name, status=response.status, url=url)
                            if response.status in [429, 503, 504, 403]:
                                # Back off and retry
                                pass
                            else:
                                # Quick failure for 404, etc.
                                break

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warn("Network or timeout error fetching URL", source=source_name, url=url, error=str(e))
                
                # Exponential backoff
                await asyncio.sleep(backoff_factor ** attempt)

            # If loop finished without returning, record failure on the breaker
            cb.record_failure()
            return None
