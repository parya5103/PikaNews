# PikaNews (parya5103/PikaNews) - Project Knowledge

Persistent project knowledge file. Created by the documentation-sync audit on 2026-11-24.

## What this repo is

- A lightweight, aggregator-first news discovery product ("PikaNews"), published at
  https://gogocompany.in/pikanews/ by the GoGo central website sync. It is an aggregator,
  NOT an independent newsroom: short publisher-attributed excerpts + original-publisher links.
- A Python collector (scripts/fetch_news.py) runs every 30 minutes in GitHub Actions
  (news_collector.yml), fetches public RSS/Atom feeds, deduplicates, classifies topics
  deterministically (scripts/classification_rules.py - no LLM), enforces retention, and
  commits news_json/ + data/ + generated sitemaps/RSS/static pages to main.
- This repo intentionally deploys NO second Pages site; gogo-website is the only publisher.

## Verified architecture (source-inspected 2026-11-24)

- Collector chain: scripts/fetch_news.py -> news_json/*.json + data/*.json ->
  generate_article_pages.py (static reader + category pages), generate_sitemap.py,
  generate_news_sitemap.py (Google News sitemap), generate_rss.py, admin_actions.py
  (moderation via .github/workflows/news-admin.yml workflow_dispatch).
- Frontend (frontend/): static reader pages; js/data.js resolves its data as the RELATIVE
  path "data" - this is load-bearing for the /pikanews/ subdirectory. Never reintroduce
  absolute /data or /PikaNews/data paths.
- Indexation safeguards (verified): third-party aggregated stories stay noindex,follow and
  EXCLUDED from both sitemaps; the Google News sitemap is reserved for substantial original
  PikaNews editorial (thin-content gate: title/summary minimums); tombstones
  (data/removed_articles.json + expired tombstones) block re-import of removed/expired
  stories; unknown publication dates are never guessed.
- Advertising: frontend/js/ads.js is the single loader, one verified GoGo publisher ID,
  fail-closed adsAllowed() (publisher + cmpReady); placements are limited and labelled;
  zero ad code on legal/search/admin/error pages. The root ads.txt is served by gogo-website.
- Security hardening (PR #7 era, api/ present): API-side CORS origin allowlist replacing
  wildcard+credentials, webhook HMAC signature + replay validation, payload validation,
  rate limiting, restricted /metrics. api/ + scrape.yml/Dockerfile are legacy or auxiliary
  paths, NOT the publishing path.

## Workflows (repo listing 2026-11-24: ci.yml, codeql.yml, lighthouse.yml, news-admin.yml,
news_collector.yml, scorecard.yml, scrape.yml, security-scan.yml, seo-validation.yml)

- news_collector.yml: the 30-minute collector; commit-only-when-changed; no gh-pages deploy
  job (the central sync owns publishing).
- ci.yml: pytest gate (tests/test_production_build.py string invariants scan comments too -
  never put "ca-pub-" or publisher IDs in comment text of test-scanned files).

## COMPLETED (evidence)

- Collector architecture + retention: 30-day NEWS_RETENTION_DAYS expiry in UTC, tombstones,
  feeds/sitemaps/static regeneration on every run, cleanup with zero new articles
  (PR #5 era, tests/test_news_expiry.py).
- Newsroom redesign: utility bar, masthead, ticker from real data, editorial hero,
  sources.html + editorial-policy.html, honest newsletter/RSS block, takedown/correction
  form via mailto (PR #4 era).
- Ad consent fail-closed gate (PR #6) and API security hardening (PR #7).
- Subsequent merged fixes: RSS entity decode safety before rendering (#81), GA4 page-view
  tracking (#79), CodeQL alignment (#78), heavy dependency updates (#8-#12).
- Database moved off git: scrape.yml now keeps pikanews.db as a 30-day Actions artifact
  instead of committing it (repo root still carries the two historical ~88 MB .db files).

## PENDING / NOT VERIFIED

- The two ~88 MB pikanews.db files committed at the repo root remain in git history;
  recommended follow-up (owner decision): external storage/artifacts only plus history
  cleanup - never delete data without owner authorization.
- Feed availability changes constantly; the authoritative status lives in PikaNews Actions
  runs and data/failed_sources.json, not in any doc.
- AdSense approval/CMP status is owner dashboard state; never claim approval or revenue.

## PLANNED (not implemented)

- Growing original editorial output to meet the published news-inclusion policy (4 reviewed
  original stories overall, 3 per category); dedicated PikaNews ad units; account-based
  sync (only after a deliberate identity-provider + backend decision).

## Cross-repository dependencies

- parya5103/gogo-website: sync-pikanews.yml runs at :10/:40 UTC, publishes frontend/ +
  news_json/ into gogocompany.in/pikanews/ with a hard verification step (21 files,
  production domains in sitemaps, NO serviceWorker.register, refuses query-param article
  URLs). Shared sync-products concurrency group serializes pushes against the daily
  product sync.
- parya5103/gogo-central-backend: GoGo Central push notifications module wired in the
  frontend (PR #21 era).

## Constraints future agents must preserve

- Branch off main immediately before opening a PR: the collector commits to main every
  ~30 minutes and can conflict work touching generated files. If the branch went stale,
  recreate it from the latest main instead of force-pushing.
- Preserve relative paths, the noindex editorial safeguards and tombstone semantics.
- Never do a local collector run against production data or manually push generated JSON
  without reviewing the workflow.
- Keep secrets out of the frontend; .env.example documents names only.
- Feature branch + PR, keep CI green, update KNOWLEDGE.md/AGENTS.md/README.md after every
  significant change, merge only with owner approval.
