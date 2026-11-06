# PikaNews Security Remediation

Companion to SECURITY_AUDIT.md. Describes what was changed, what needs
infrastructure or owner action, and how to operate the new controls.

## Changes made (this PR)

1. frontend/index.html, frontend/search.html: GitHub footer icon replaced
   with mailto:officialgogocompany@gmail.com. No other layout/SEO change.
2. NEW api/security.py: stdlib-only security helpers (CORS allowlist,
   HMAC webhook verification with replay window, payload schema validation,
   bearer-token check, sliding-window RateLimiter). Importable in CI without
   FastAPI.
3. api/server.py: explicit CORS allowlist; rate-limit middleware;
   fail-closed HMAC webhook (403 when secret unset, 413 oversized, 400 bad
   payload); /metrics, /dashboard, /, /api/stats require
   PIKANEWS_MONITOR_TOKEN (404 when unset); q/name length caps; pydantic
   WebhookPayload replaced by validated manual parsing.
4. tests/test_api_security.py (NEW) and a new production-build invariant
   (test_no_visitor_facing_github_links) added to the CI gates
   (.github/workflows/ci.yml and news_collector.yml).
5. news-admin.yml: workflow inputs passed via env vars (script-injection
   hardening).
6. All workflows: actions pinned to immutable commit SHAs.
7. NEW .github/dependabot.yml (github-actions + pip, weekly).
8. NEW .github/workflows/codeql.yml (python).

## Backend / deployment notes

The published PikaNews site is fully static (GitHub Pages via the gogo
sync); the FastAPI API is optional and self-hosted (docker-compose). The API
is NOT exposed publicly by the current zero-budget architecture. If/when it
is deployed:

- Set PIKANEWS_WEBHOOK_SECRET before enabling any external webhook sender.
  The sender must compute `X-Signature: sha256=<HMAC-SHA256 of raw body>`
  and send `X-Timestamp: <unix seconds>`; requests older/newer than 5
  minutes are rejected (replay protection).
- Set PIKANEWS_MONITOR_TOKEN to enable /metrics, /dashboard and /api/stats;
  without it they return 404 (fail-closed). Do NOT put the token in code;
  use your server's secret manager or environment.
- Optional env overrides: PIKANEWS_ALLOWED_ORIGINS (comma-separated explicit
  origins; default https://gogocompany.in), PIKANEWS_RATE_LIMIT (requests
  per minute per client; default 60).
- For multi-process deployments, put a shared rate limiter (nginx
  limit_req or Redis) in front; the in-app limiter is per-process.
- Serve behind HTTPS with a reverse proxy; add request timeouts there
  (uvicorn keep-alive defaults otherwise apply).

## What was intentionally NOT done

- No major dependency upgrades (dependabot will propose; review before
  merge).
- No database changes; news data, tombstones and audit logs untouched.
- No changes to collector cadence, sync workflow, ads or SEO contracts.

## Rollback

Revert this PR's merge commit. All changes are additive or file-local; the
site and collector continue to work without the API module. The new env
vars are optional - with none set, the API keeps working for public
read-only endpoints with webhooks and monitoring disabled (fail-closed).
