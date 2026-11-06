#!/usr/bin/env python3
"""Security regression tests for the PikaNews API (api/security.py).

These tests import ONLY the stdlib security module - no FastAPI or database
dependencies - so they run in the standard CI pytest gate.
"""

import hashlib
import hmac
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.security import (  # noqa: E402
    DEFAULT_ALLOWED_ORIGINS,
    RateLimiter,
    bearer_token_matches,
    is_origin_allowed,
    monitor_token_from_env,
    parse_allowed_origins,
    validate_webhook_payload,
    verify_webhook_signature,
    webhook_secret_from_env,
)

SECRET = "test-webhook-secret"


def sign(secret: str, body: bytes, timestamp: int) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


# ---------------------------------------------------------------- CORS allowlist

def test_cors_allowlist_defaults_to_production_origin():
    assert parse_allowed_origins(None) == DEFAULT_ALLOWED_ORIGINS
    assert parse_allowed_origins("") == DEFAULT_ALLOWED_ORIGINS
    assert parse_allowed_origins("   ") == DEFAULT_ALLOWED_ORIGINS


def test_cors_allowlist_parses_explicit_origins_without_wildcards():
    assert parse_allowed_origins("https://a.example, https://b.example") == [
        "https://a.example", "https://b.example"
    ]
    assert parse_allowed_origins(" https://a.example , , ") == ["https://a.example"]


def test_cors_origin_check_is_exact_match():
    allowed = parse_allowed_origins("https://gogocompany.in")
    assert is_origin_allowed("https://gogocompany.in", allowed) is True
    assert is_origin_allowed("https://evil.example", allowed) is False
    assert is_origin_allowed("https://gogocompany.in.evil.example", allowed) is False
    assert is_origin_allowed(None, allowed) is False
    assert is_origin_allowed("", allowed) is False


# ---------------------------------------------------------------- Webhook HMAC

def _body():
    return b'{"event": "article.new", "article": {"title": "Hello"}}'


def test_webhook_accepts_valid_signature_and_fresh_timestamp():
    body = _body()
    ok, reason = verify_webhook_signature(
        SECRET, body, sign(SECRET, body, 1000), "1000", now=1000
    )
    assert ok is True, reason


def test_webhook_rejects_tampered_body():
    body = _body()
    ok, reason = verify_webhook_signature(
        SECRET, b'{"event": "article.new", "article": {"title": "Hacked"}}',
        sign(SECRET, body, 1000), "1000", now=1000,
    )
    assert ok is False
    assert reason == "signature mismatch"


def test_webhook_rejects_wrong_secret_signature():
    body = _body()
    ok, reason = verify_webhook_signature(
        SECRET, body, sign("other-secret", body, 1000), "1000", now=1000
    )
    assert ok is False


def test_webhook_rejects_missing_or_malformed_headers():
    body = _body()
    assert verify_webhook_signature(SECRET, body, None, "1000", now=1000)[0] is False
    assert verify_webhook_signature(SECRET, body, "", "1000", now=1000)[0] is False
    assert verify_webhook_signature(SECRET, body, sign(SECRET, body, 1000), None, now=1000)[0] is False
    # Unsupported scheme / malformed digest
    assert verify_webhook_signature(
        SECRET, body, "md5=" + "a" * 32, "1000", now=1000
    )[0] is False
    assert verify_webhook_signature(
        SECRET, body, "sha256=zz" + "0" * 62, "1000", now=1000
    )[0] is False


def test_webhook_replay_window_blocks_stale_and_future_timestamps():
    body = _body()
    signature = sign(SECRET, body, 1000)
    assert verify_webhook_signature(SECRET, body, signature, "1000", now=1000 + 301)[0] is False
    assert verify_webhook_signature(SECRET, body, signature, "1000", now=1000 - 301)[0] is False
    # Inside the window still passes.
    assert verify_webhook_signature(SECRET, body, signature, "1000", now=1000 + 300)[0] is True
    # Non-numeric timestamp is rejected.
    assert verify_webhook_signature(SECRET, body, signature, "not-a-number", now=1000)[0] is False


def test_webhook_is_disabled_without_configured_secret():
    body = _body()
    ok, reason = verify_webhook_signature(None, body, sign(SECRET, body, 1000), "1000", now=1000)
    assert ok is False
    assert reason == "webhook secret not configured"


def test_webhook_secret_env_parsing(monkeypatch):
    monkeypatch.delenv("PIKANEWS_WEBHOOK_SECRET", raising=False)
    assert webhook_secret_from_env() is None
    monkeypatch.setenv("PIKANEWS_WEBHOOK_SECRET", "  ")
    assert webhook_secret_from_env() is None
    monkeypatch.setenv("PIKANEWS_WEBHOOK_SECRET", " abc ")
    assert webhook_secret_from_env() == "abc"


# ---------------------------------------------------------------- Payload schema

def test_webhook_payload_accepts_valid_shape():
    ok, reason = validate_webhook_payload(
        {"event": "article.new", "article": {"title": "T", "summary": "S", "url": "https://x.example"}}
    )
    assert ok is True, reason


def test_webhook_payload_rejects_structural_abuse():
    assert validate_webhook_payload("string")[0] is False
    assert validate_webhook_payload({})[0] is False
    assert validate_webhook_payload({"event": "", "article": {}})[0] is False
    assert validate_webhook_payload({"event": "x" * 65, "article": {}})[0] is False
    assert validate_webhook_payload({"event": "ok", "article": "not-a-dict"})[0] is False
    assert validate_webhook_payload({"event": "ok", "article": {str(i): "v" for i in range(65)}})[0] is False
    assert validate_webhook_payload(
        {"event": "ok", "article": {"title": "x" * 1001}}
    )[0] is False
    assert validate_webhook_payload(
        {"event": "ok", "article": {"url": "javascript:alert(1)"}}
    )[0] is False


# ---------------------------------------------------------------- Monitor token

def test_monitor_token_env_parsing(monkeypatch):
    monkeypatch.delenv("PIKANEWS_MONITOR_TOKEN", raising=False)
    assert monitor_token_from_env() is None
    monkeypatch.setenv("PIKANEWS_MONITOR_TOKEN", "tok")
    assert monitor_token_from_env() == "tok"


def test_monitor_bearer_check_is_fail_closed_and_constant_time():
    assert bearer_token_matches(None, "Bearer anything") is False
    assert bearer_token_matches("secret-token", "Bearer secret-token") is True
    assert bearer_token_matches("secret-token", "Bearer wrong") is False
    assert bearer_token_matches("secret-token", "") is False


# ---------------------------------------------------------------- Rate limiting

def test_rate_limiter_blocks_after_limit_within_window():
    rl = RateLimiter(limit=3, window=60)
    assert [rl.allow("ip-1", now=100) for _ in range(3)] == [True, True, True]
    assert rl.allow("ip-1", now=101) is False
    assert rl.allow("ip-1", now=110) is False


def test_rate_limiter_window_slides_and_keys_are_independent():
    rl = RateLimiter(limit=2, window=60)
    assert rl.allow("ip-1", now=100) is True
    assert rl.allow("ip-1", now=101) is True
    assert rl.allow("ip-1", now=102) is False
    # After the window passes, capacity is restored.
    assert rl.allow("ip-1", now=161) is True
    # A different key is unaffected.
    assert rl.allow("ip-2", now=100) is True


def test_rate_limiter_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        RateLimiter(limit=0, window=60)
    with pytest.raises(ValueError):
        RateLimiter(limit=10, window=0)


if __name__ == "__main__":
    failures = 0
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]:
        try:
            fn()
            print(f"  OK {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failures += 1
    print(f"api security tests: {'PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    raise SystemExit(0 if failures == 0 else 1)
