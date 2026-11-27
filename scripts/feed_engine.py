"""Reliable, cache-aware and SSRF-safe RSS/Atom/JSON Feed transport.

The collector remains static-first and GitHub Actions hosted. This module adds
persistent HTTP validators, bounded retries, source health and feed discovery
without introducing a database, paid API or always-on service.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

REDIRECT_CODES = {301, 302, 303, 307, 308}
FEED_MIME_TYPES = {
    "application/rss+xml", "application/atom+xml", "application/feed+json",
    "application/json", "application/xml", "text/xml",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def _read_json(path: str | Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_json_atomic(path: str | Path, data: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)


def is_public_http_url(url: str) -> bool:
    """Reject non-HTTP, credentialed, localhost and private/reserved destinations."""
    try:
        parsed = urlparse(str(url))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip(".").casefold()
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            }
        return bool(addresses) and all(ip.is_global for ip in addresses)
    except (OSError, ValueError, TypeError):
        return False


def _retry_delay(response: Any, attempt: int) -> float:
    raw = getattr(response, "headers", {}).get("Retry-After")
    if raw:
        try:
            return min(300.0, max(0.0, float(raw)))
        except (TypeError, ValueError):
            try:
                when = parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                return min(300.0, max(0.0, (when - utc_now()).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(60.0, 2.0 ** attempt)


def feed_health_snapshot(path: str | Path) -> dict:
    return _read_json(path)


def fetch_feed(
    url: str,
    cache_dir: str | Path,
    health_path: str | Path,
    *,
    max_retries: int = 3,
    timeout: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str | None, str]:
    """Fetch a feed with conditional requests, safe redirects and durable health.

    Returns (body, status), where status is updated, not_modified or failed.
    """
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    body_path = cache_root / (key + ".feed")
    state = _read_json(health_path)
    record = state.get(url, {}) if isinstance(state.get(url, {}), dict) else {}
    now = utc_now()
    record["last_attempt"] = _iso(now)

    retry_at = record.get("next_retry_at")
    if retry_at:
        try:
            if datetime.fromisoformat(retry_at.replace("Z", "+00:00")) > now:
                state[url] = record
                _write_json_atomic(health_path, state)
                if body_path.is_file():
                    return body_path.read_text(encoding="utf-8"), "not_modified"
                return None, "failed"
        except ValueError:
            pass

    headers = {
        "User-Agent": "PikaNews-Bot/3.0 (+https://github.com/parya5103/PikaNews)",
        "Accept": "application/rss+xml, application/atom+xml, application/feed+json, application/json, application/xml, text/xml;q=0.9, */*;q=0.5",
    }
    if record.get("etag"):
        headers["If-None-Match"] = record["etag"]
    if record.get("last_modified"):
        headers["If-Modified-Since"] = record["last_modified"]

    last_error = "unknown error"
    last_status = None
    for attempt in range(max(1, max_retries)):
        current_url = url
        try:
            if not is_public_http_url(current_url):
                raise ValueError("Feed URL or redirect target is not a public HTTP(S) address")
            with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)), headers=headers, follow_redirects=False) as client:
                for _ in range(6):
                    response = client.get(current_url, headers=headers, follow_redirects=False)
                    last_status = response.status_code
                    if response.status_code in REDIRECT_CODES:
                        location = response.headers.get("Location")
                        if not location:
                            raise ValueError("Redirect response did not include Location")
                        current_url = urljoin(current_url, location)
                        if not is_public_http_url(current_url):
                            raise ValueError("Redirect target is not a public HTTP(S) address")
                        continue
                    if response.status_code == 304:
                        if not body_path.is_file():
                            raise ValueError("Server returned 304 but no cached feed body exists")
                        record.update({
                            "last_success": _iso(), "last_status": 304,
                            "consecutive_failures": 0, "last_error": None,
                            "next_retry_at": None,
                        })
                        state[url] = record
                        _write_json_atomic(health_path, state)
                        return body_path.read_text(encoding="utf-8"), "not_modified"
                    if response.status_code in (429, 500, 502, 503, 504):
                        last_error = f"HTTP {response.status_code}"
                        if attempt < max_retries - 1:
                            sleep(_retry_delay(response, attempt))
                            break
                    response.raise_for_status()
                    body = response.text
                    if not body.strip():
                        raise ValueError("Feed response was empty")
                    body_path.write_text(body, encoding="utf-8")
                    response_headers = response.headers
                    record.update({
                        "etag": response_headers.get("ETag"),
                        "last_modified": response_headers.get("Last-Modified"),
                        "last_success": _iso(),
                        "last_status": response.status_code,
                        "consecutive_failures": 0,
                        "last_error": None,
                        "next_retry_at": None,
                        "final_url": current_url,
                    })
                    state[url] = record
                    _write_json_atomic(health_path, state)
                    return body, "updated"
                else:
                    raise ValueError("Too many feed redirects")
            # transient response retry loop continues after leaving client
            if last_status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                continue
            raise RuntimeError(last_error)
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_retries - 1 and not isinstance(exc, ValueError):
                sleep(min(60.0, 2.0 ** attempt))
                continue
            break

    failures = int(record.get("consecutive_failures") or 0) + 1
    cooldown = min(6 * 60 * 60, 60 * (2 ** min(failures - 1, 8)))
    record.update({
        "last_status": last_status,
        "consecutive_failures": failures,
        "last_error": last_error[:500],
        "next_retry_at": _iso(now + timedelta(seconds=cooldown)),
    })
    state[url] = record
    _write_json_atomic(health_path, state)
    return None, "failed"


def parse_json_feed(content: str, feed_url: str) -> list[dict]:
    """Convert JSON Feed 1.0/1.1 items into the collector's common item shape."""
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return []
    version = str(payload.get("version") or "")
    if not version.startswith("https://jsonfeed.org/version/"):
        return []
    output = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        authors = item.get("authors") or []
        author = next((a.get("name") for a in authors if isinstance(a, dict) and a.get("name")), None)
        attachments = item.get("attachments") or []
        image = item.get("image")
        if not image:
            image = next((a.get("url") for a in attachments if isinstance(a, dict) and str(a.get("mime_type") or "").startswith("image/")), None)
        output.append({
            "url": item.get("url") or item.get("external_url") or "",
            "title": item.get("title") or "",
            "description": item.get("summary") or item.get("content_text") or item.get("content_html") or "",
            "date": item.get("date_published") or item.get("date_modified"),
            "image_url": image,
            "author": author,
            "categories": item.get("tags") or [],
            "feed_url": feed_url,
        })
    return output


def discover_feed_urls(html: str, page_url: str) -> list[str]:
    """Find RSS, Atom and JSON Feed alternate links; never fetch them automatically."""
    soup = BeautifulSoup(html or "", "html.parser")
    found = []
    for tag in soup.find_all("link", rel=lambda value: value and "alternate" in value):
        mime = str(tag.get("type") or "").split(";", 1)[0].strip().lower()
        href = tag.get("href")
        if mime not in FEED_MIME_TYPES or not href:
            continue
        candidate = urljoin(page_url, href)
        if is_public_http_url(candidate) and candidate not in found:
            found.append(candidate)
    return found


def rank_feed_candidates(candidates: list[dict]) -> list[dict]:
    """Stable, deterministic ordering: configured priority then current health."""
    return sorted(
        candidates,
        key=lambda item: (
            int(item.get("priority") or 99),
            int((item.get("health") or {}).get("consecutive_failures") or 0),
            str(item.get("name") or "").casefold(),
        ),
    )


def extract_reading_text(html: str, max_chars: int = 5000) -> str:
    """Extract a short reader-context preview from allowed publisher HTML.

    This helper is deliberately not used to republish full copyrighted articles.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup.select("script,style,noscript,nav,header,footer,aside,form,button,iframe"):
        node.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in main.find_all("p")]
    text = " ".join(part for part in paragraphs if part)
    return " ".join(text.split())[:max(0, max_chars)]
