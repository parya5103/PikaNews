# PikaNews Security Test Results

Evidence collected on 2026-11-06. Only checks actually executed are listed.

## Executed in CI (GitHub Actions, this PR)

- Existing gates: tests/test_news_collector.py, tests/test_news_expiry.py,
  tests/test_generators.py, tests/test_production_build.py - unchanged
  behavior expected; plus NEW tests/test_api_security.py (18 test
  functions) and the new production-build invariant
  test_no_visitor_facing_github_links.
- See the PR's checks tab for the authoritative pass/fail status. The
  status at PR creation is recorded in the final report of the audit
  session.

## New tests and what they prove

1. test_no_visitor_facing_github_links (production-build suite): every
   frontend page is scanned; fails if any page links to github.com/parya5103,
   shows a GitHub icon, or submits a form to github.com. Regression guard for
   the removed footer links.
2. CORS allowlist tests: default = production origin only; explicit parsing;
   exact-match origin checks (subdomain/lookalike origins rejected; empty and
   absent Origin rejected).
3. Webhook HMAC tests: valid signature+timestamp accepted; tampered body,
   wrong secret, missing/malformed headers, unsupported scheme, stale and
   future timestamps rejected; unset secret = endpoint disabled; replay
   window boundary verified at exactly +/-300s.
4. Payload schema tests: bounded event length, dict-only article, key-count
   cap, field-length caps, http(s)-only article URLs (javascript: rejected).
5. Monitor-token tests: unset token = fail-closed; constant-time bearer
   comparison; wrong/empty tokens rejected.
6. RateLimiter tests: limit enforcement, window sliding, per-key isolation,
   invalid configuration rejected.

## Static verification performed during the audit (no runtime needed)

- Grep of pipelines/db.py: parameterized SQL only.
- Search of all frontend pages: no remaining visitor-facing GitHub links
  (the two fixed files were the only hits).
- Workflow review: no pull_request_target usage; no fork-triggered secret
  exposure paths; permissions already explicit (contents: read/write as
  needed) and now SHAs pinned.

## Not verified (honest gaps)

- No live deployment of api/server.py exists in this zero-budget
  architecture, so HMAC/CORS/rate-limit behavior could not be exercised
  against a running server; the logic is covered by the unit tests above,
  not by an integration run.
- No browser/device test of the replaced footer icons (visual check pending
  owner review on the live site after sync).
- CodeQL results appear only after the workflow's first run post-merge.
- Dependabot alerts depend on GitHub's scanning of the dependency manifests.
