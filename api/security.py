"""Pure-stdlib security helpers for the PikaNews API.

Kept dependency-free (no FastAPI / pydantic / structlog imports) so the CI
test suite can import and verify every rule without installing the API
runtime dependencies.

Security policy implemented here:
- CORS uses an explicit origin allowlist, never a wildcard.
- Webhooks require HMAC-SHA256 signatures with a fresh timestamp
  (fail-closed: no configured secret means the endpoint is disabled).
- Monitoring endpoints (/metrics, /dashboard, /api/stats) require a bearer
  token; when no token is configured they stay disabled (fail-closed).
- A small in-memory sliding-window limiter protects against abuse.
"""

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from typing import List, Optional, Tuple

# Explicit CORS allowlist. Wildcard origins combined with credentials are
# forbidden; the production frontend origin is the only default.
DEFAULT_ALLOWED_ORIGINS = ["https://gogocompany.in"]

# Webhook hardening constants.
WEBHOOK_TOLERANCE_SECONDS = 300  # +/- 5 minutes replay window
WEBHOOK_MAX_BODY_BYTES = 65536   # 64 KB request body cap
WEBHOOK_EVENT_MAX_LENGTH = 64
WEBHOOK_ARTICLE_MAX_KEYS = 64
WEBHOOK_FIELD_MAX_LENGTH = 1000

# Rate limiting defaults (per client key, sliding window).
RATE_LIMIT_DEFAULT = 60
RATE_LIMIT_WINDOW_SECONDS = 60


def parse_allowed_origins(raw: Optional[str]) -> List[str]:
    """Parse PIKANEWS_ALLOWED_ORIGINS ("https://a.example, https://b.example").

    Empty / unset -> the production default. Entries are stripped; empty
    entries are dropped. Origins are kept exactly as provided (exact-match
    policy; no wildcards, no regex).
    """
    if raw is None or not raw.strip():
        return list(DEFAULT_ALLOWED_ORIGINS)
    origins = [entry.strip() for entry in raw.split(",")]
    return [origin for origin in origins if origin]


def is_origin_allowed(origin: Optional[str], allowed: List[str]) -> bool:
    """Exact-match CORS check. None/absent Origin headers are not allowed."""
    if not origin:
        return False
    return origin in allowed


def webhook_secret_from_env() -> Optional[str]:
    """Return the configured webhook secret, or None when unset/empty.

    Callers must treat None as "webhook disabled" (fail-closed).
    """
    secret = os.getenv("PIKANEWS_WEBHOOK_SECRET", "")
    if secret is None:
        return None
    secret = secret.strip()
    return secret or None


def monitor_token_from_env() -> Optional[str]:
    """Return the configured monitoring bearer token, or None when unset.

    Callers must treat None as "monitoring endpoints disabled" (fail-closed).
    """
    token = os.getenv("PIKANEWS_MONITOR_TOKEN", "")
    if token is None:
        return None
    token = token.strip()
    return token or None


def verify_webhook_signature(
    secret: Optional[str],
    body: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    now: Optional[float] = None,
) -> Tuple[bool, str]:
    """Verify an HMAC-SHA256 webhook signature with replay protection.

    Expected headers:
      X-Signature: sha256=<hex digest of the raw request body>
      X-Timestamp: unix seconds (must be within WEBHOOK_TOLERANCE_SECONDS)

    Returns (ok, reason). Never raises on hostile input.
    """
    if secret is None:
        return False, "webhook secret not configured"
    if not isinstance(body, bytes):
        return False, "invalid body"
    if not signature or not isinstance(signature, str):
        return False, "missing signature"
    if not timestamp or not isinstance(timestamp, str):
        return False, "missing timestamp"

    signature = signature.strip()
    if not signature.lower().startswith("sha256="):
        return False, "unsupported signature scheme"
    provided = signature.split("=", 1)[1].strip().lower()
    if len(provided) != 64:
        return False, "malformed signature"
    try:
        int(provided, 16)
    except ValueError:
        return False, "malformed signature"

    try:
        ts = int(timestamp.strip())
    except ValueError:
        return False, "malformed timestamp"
    current = time.time() if now is None else now
    if abs(current - ts) > WEBHOOK_TOLERANCE_SECONDS:
        return False, "timestamp outside tolerance window"

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        return False, "signature mismatch"
    return True, "ok"


def validate_webhook_payload(payload: object) -> Tuple[bool, str]:
    """Structural validation of a parsed webhook JSON payload.

    Schema: {"event": str 1..64, "article": dict with bounded keys/strings}.
    """
    if not isinstance(payload, dict):
        return False, "payload must be an object"
    event = payload.get("event")
    if not isinstance(event, str) or not (1 <= len(event) <= WEBHOOK_EVENT_MAX_LENGTH):
        return False, "invalid event field"
    article = payload.get("article")
    if not isinstance(article, dict):
        return False, "invalid article field"
    if len(article) > WEBHOOK_ARTICLE_MAX_KEYS:
        return False, "too many article fields"
    for key in ("title", "summary"):
        value = article.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > WEBHOOK_FIELD_MAX_LENGTH:
            return False, "invalid article %s" % key
    url = article.get("url")
    if url is not None:
        if not isinstance(url, str) or len(url) > WEBHOOK_FIELD_MAX_LENGTH:
            return False, "invalid article url"
        # Explicit protocol policy: only http(s) URLs are accepted.
        if not (url.startswith("https://") or url.startswith("http://")):
            return False, "article url must use http(s)"
    return True, "ok"


def bearer_token_matches(expected: Optional[str], provided: str) -> bool:
    """Constant-time check of a 'Authorization: Bearer <token>' header value.

    Returns False when no token is configured (fail-closed) or on mismatch.
    """
    if expected is None:
        return False
    return hmac.compare_digest(("Bearer " + expected).strip(), (provided or "").strip())


class RateLimiter:
    """Small in-memory sliding-window limiter (per client key).

    Suitable for a single-process deployment; for multi-process setups put a
    real limiter (e.g. nginx or Redis) in front of the API.
    """

    def __init__(self, limit: int = RATE_LIMIT_DEFAULT, window: int = RATE_LIMIT_WINDOW_SECONDS) -> None:
        if limit <= 0 or window <= 0:
            raise ValueError("limit and window must be positive")
        self.limit = limit
        self.window = window
        self._hits = defaultdict(deque)

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        current = time.time() if now is None else now
        hits = self._hits[key]
        cutoff = current - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(current)
        return True

    def reset(self) -> None:
        self._hits.clear()
