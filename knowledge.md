# PikaNews Engineering Knowledge

Last updated: 2026-11-27

## Product and publishing contract

- PikaNews is a global, static-first news discovery product under https://gogocompany.in/pikanews/.
- It aggregates attributed publisher headlines and limited excerpts; it is not an independent newsroom and must not claim that it independently reports or verifies every linked story.
- Full reading links to the original publisher. Feed availability alone does not grant rights to republish full articles or images.
- Reader access is guest-first. Bookmarks and topic preferences are local; account-based cross-device sync is not active unless separately implemented.
- PikaNews data and generated pages are synchronized by the GoGo Company central repository. This repository must not add a second Pages deployment.

## Production data path

Publisher feeds -> scripts/fetch_news.py -> scripts/feed_engine.py -> news_json/*.json and data/*.json -> static frontend and generated pages -> sitemaps/RSS -> GoGo Company central sync workflow.

The scheduled collector remains every 30 minutes and CI must pass before publishing. Generated files are committed only when they change.

## Five-phase collector architecture

1. **Transport reliability:** scripts/feed_engine.py implements ETag and Last-Modified conditional requests, cached response bodies, bounded retries, Retry-After/backoff, manual redirect validation and private/reserved IP rejection. Cache bodies are transient in data/feed_cache/ and excluded from Git; GitHub Actions cache restores them between runs.
2. **Feed intelligence:** source health is persisted inside the Actions-cached data/feed_cache directory. Feed candidates are ordered by configured priority and failure streak. discover_feed_urls() detects RSS, Atom and JSON Feed alternate links but does not automatically activate unreviewed publishers.
3. **Extraction compatibility:** RSS, Atom and JSON Feed are normalized into one common item structure. extract_reading_text() is a limited helper for allowed reading-context previews; do not use it to republish full copyrighted stories.
4. **Discovery quality:** deterministic rules in scripts/classification_rules.py remain the no-cost classification layer. Healthy/high-priority feeds run first. Existing deduplication, publisher diversity, freshness, thin-content and source attribution safeguards remain.
5. **SEO and publishing:** scripts/validate_generated_articles.py validates article robots/schema/breadcrumbs. scripts/validate_sitemap_indexation.py validates sitemap XML, URL-to-file existence, canonical alignment and absence of noindex on advertised pages.

## Indexation policy — do not weaken casually

- Individual third-party RSS aggregation pages remain accessible but noindex,follow; do not add them to regular or Google News sitemaps.
- Latest/category hubs enter the regular sitemap only when the current freshness, excerpt depth and distinct-publisher gates pass.
- Trending remains noindex until a real ranking signal and quality gate exist.
- Google News sitemap is only for reviewed original PikaNews editorial with valid author, publication date and substantive original content.
- Unknown publisher dates must not be replaced by collection timestamps.
- Removed/expired stories remain blocked by tombstones.
- index,follow and sitemap inclusion do not guarantee Google indexing.

## Important files

- scripts/fetch_news.py — collector orchestration, normalization, dedupe, retention and JSON output.
- scripts/feed_engine.py — HTTP cache, retry, source health, discovery, JSON Feed parsing and safe reading-context extraction.
- scripts/classification_rules.py — deterministic free topic classifier.
- scripts/generate_article_pages.py — static article and category pages.
- scripts/generate_sitemap.py — regular sitemap and indexation gates.
- scripts/generate_news_sitemap.py — original-editorial Google News sitemap.
- scripts/validate_generated_articles.py — generated article checks.
- scripts/validate_sitemap_indexation.py — sitemap/canonical/robots checks.
- .github/workflows/news_collector.yml — scheduled collector and publishing gate; no Pages deployment in this repository.
- .github/workflows/ci.yml — pull request and push test gate.

## Required checks

    pip install -r requirements-collector.txt python-dateutil pytest
    pytest tests/test_guest_preferences.py tests/test_classification_rules.py tests/test_news_collector.py tests/test_news_expiry.py tests/test_generators.py tests/test_production_build.py tests/test_api_security.py tests/test_editorial_indexation.py tests/test_generated_article_validation.py tests/test_empty_master_feed_recovery.py tests/test_topic_hub_indexation.py tests/test_feed_engine.py tests/test_sitemap_indexation_validator.py -q
    python scripts/fetch_news.py
    python scripts/generate_article_pages.py
    python scripts/generate_sitemap.py
    python scripts/generate_rss.py
    python scripts/generate_news_sitemap.py
    python scripts/validate_generated_articles.py
    python scripts/validate_sitemap_indexation.py

Never run the collector locally against production data or manually push generated JSON without reviewing retention/tombstone effects. Work on a feature branch, wait for CI, and use a pull request before merging.

## SEO and scheduled collector recheck (2026-11-28)

- The collector workflow on the default branch now schedules at minute 7 and 37 of every hour (`7,37 * * * *`), retaining the intended 30-minute interval while avoiding the top-of-hour boundary. This is a scheduling mitigation, not a delivery guarantee; monitor actual scheduled-run timestamps and failures before claiming reliable 30-minute refreshes.
- The schedule change was validated on head `236f7e2d70557a8017e8fd1d69bc7da2a08147b4`: CI, CodeQL and Security scan all completed successfully. PR #99 is confirmed merged; the current default-branch workflow file confirms the cron expression is present.
- The current committed regular sitemap snapshot contains 10 URLs: the PikaNews homepage, three eligible topic hubs (Hollywood, Entertainment, Science), and six static trust/legal pages. Latest and other category hubs are absent when their freshness, excerpt-depth and publisher-diversity gates do not pass. Do not force them into the sitemap.
- The committed Google News sitemap is empty. This is correct while there are no reviewed original editorial articles that satisfy the named-author, 1,200-character substantive-content, explicit-review and valid-publication-date requirements.
- The root GoGo robots.txt allows crawling and advertises the PikaNews sitemap. PikaNews homepage has an explicit `index,follow` directive and canonical URL. Individual RSS aggregation pages and the dynamic article fallback remain `noindex,follow` by policy; do not weaken this to increase indexed URL counts.
- A web-search snippet made the Editorial & Corrections Policy look as if a bullet and section numbering were malformed; direct source inspection of `frontend/editorial-policy.html` confirms the actual HTML is correctly structured and numbered 1–7. Do not change the source based on the search snippet alone.
- Do not confuse collection time with publisher publication time. Preserve missing/unknown dates and the existing editorial/indexation quality gates.
