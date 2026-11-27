# PikaNews — Global News Discovery

PikaNews is a lightweight, static-first news discovery product published at
[GoGo Company](https://gogocompany.in/pikanews/). It organizes short,
publisher-attributed headlines and excerpts from public RSS/Atom feeds and
links readers to the original publisher for full reporting.

It is an aggregator, not an independent newsroom. It does not claim to
independently report or verify every linked story.

## Current production architecture

```text
Publisher RSS / Atom feeds
        |
        v
scripts/fetch_news.py
  - feed parsing and validation
  - URL/title deduplication
  - deterministic topic classification
  - publication-date retention and removal tombstones
        |
        v
news_json/*.json + data/*.json
        |
        +--> frontend/js/data.js + frontend/js/app.js
        |      static news discovery UI
        |
        +--> scripts/generate_article_pages.py
        |      static reader pages and category listings
        |
        +--> scripts/generate_sitemap.py
        +--> scripts/generate_news_sitemap.py
        +--> scripts/generate_rss.py
        |
        v
GoGo Company central website sync workflow
  (this repository intentionally does not deploy a second Pages site)
```

The public site is static-first and uses relative asset/data paths so it works
under the `/pikanews/` subdirectory. The GitHub Actions collector runs every
30 minutes. The central GoGo Company repository performs the actual publishing
sync after PikaNews data and generated pages are ready.

Legacy or experimental API/pipeline directories may exist in this repository;
they are not the production publishing path described above.

## News coverage

The topic taxonomy includes World, Science, Politics, Health, Climate,
Technology, Business, Sports, Gaming, Entertainment, Bollywood and Hollywood.
The collector uses deterministic, dependency-free rules: headline evidence
has priority over summary evidence, and publisher brand/domain is not treated
as proof of an article's topic.

New feeds must be checked for:
- current feed availability and parseability;
- publisher terms and commercial display permissions;
- attribution and original-link requirements;
- image and third-party content restrictions;
- accurate source name, topic, language and region metadata.

A public RSS endpoint is not, by itself, permission to republish full articles
or images. PikaNews uses limited excerpts and source links. Feed-specific image
restrictions are enforced where configured.


## Collector reliability and five-phase upgrade

The production collector keeps the original static-first GitHub Actions
architecture while using scripts/feed_engine.py for:

- Conditional HTTP requests using ETag and Last-Modified validators.
- A bounded local feed-body cache restored/saved by GitHub Actions cache.
- Manual redirect validation that rejects private, loopback and reserved IP
  destinations before following a publisher redirect.
- Bounded retry/backoff, Retry-After handling, and persistent per-feed health
  records in data/feed_health.json.
- JSON Feed 1.0/1.1 normalization into the same article pipeline as RSS/Atom.
- Feed autodiscovery helpers for RSS, Atom and JSON Feed alternate links.
- Deterministic source scheduling by configured priority and recent failure
  streak; no publisher is silently added to production just because discovery
  finds a feed.

The feed engine also exposes a limited reading-context text extractor. It is
not used to republish complete third-party articles. The product continues to
show attributed excerpts and link to the publisher unless content is separately
licensed or written/reviewed as original PikaNews editorial.

### Five implementation phases

1. **Transport reliability:** conditional requests, cache, redirect safety,
   bounded retries and retry cooldowns.
2. **Feed intelligence:** persistent health/failure state, feed autodiscovery
   helpers and priority-aware scheduling.
3. **Extraction compatibility:** JSON Feed support, normalized metadata,
   image fallbacks and limited reading-context extraction without wholesale
   article copying.
4. **Discovery quality:** deterministic classification remains the topic
   baseline; healthy/high-priority sources are fetched first, while the
   existing source-diversity and freshness gates remain in force.
5. **SEO/publishing validation:** generated article checks plus a sitemap
   validator that confirms every advertised URL has a real page, a self
   canonical and no noindex directive. Aggregated story pages remain noindex;
   useful topic hubs and reviewed original editorial qualify under their
   existing quality gates.

### Verification commands

    pytest tests/test_feed_engine.py tests/test_sitemap_indexation_validator.py -q
    python scripts/validate_generated_articles.py
    python scripts/validate_sitemap_indexation.py

## Reader preferences and accounts

Reading does not require an account. Bookmarks and the optional For You topic
preferences are stored locally in the reader's browser. No login, paid LLM,
model download or server-side profile is required for this guest experience.
Account-based cross-device sync is not configured in the current static
architecture and must not be represented as active until an identity provider
and backend are deliberately added.

## Indexation and editorial safeguards

- Third-party aggregated story pages remain `noindex,follow` and are excluded from
  regular and Google News sitemaps.
- Latest and category topic hubs can enter the regular sitemap only when their
  pre-rendered listings meet strict freshness, excerpt-depth and publisher-diversity
  gates (12 stories / 5 publishers for Latest; 8 stories / 4 publishers for a
  category; all published within 14 days with excerpts of at least 120 characters).
- Trending remains `noindex` until it has a separately reviewed purpose and quality gate.
- The Google News sitemap is reserved for substantial, reviewed original
  PikaNews editorial that meets the existing author, date and content checks.
- Collection timestamps are not presented as editorial publication or
  modification dates.
- Thin stories are not promoted as indexable articles or placed beside ads.
- Removed and expired stories are blocked from re-import by tombstones.
- Unknown publication dates are not guessed into freshness or expiry decisions.

Do not remove these safeguards just to increase indexed URL counts. Google
News inclusion is not guaranteed by schema or a sitemap.

## Repository map

| Path | Responsibility |
|---|---|
| `scripts/fetch_news.py` | RSS collection, normalization, classification integration, retention and JSON output |
| `scripts/classification_rules.py` | Free deterministic topic rules |
| `scripts/generate_article_pages.py` | Static article pages and category listings |
| `scripts/generate_sitemap.py` | Regular sitemap with editorial indexation gates |
| `scripts/generate_news_sitemap.py` | Google News sitemap for eligible original editorial only |
| `scripts/generate_rss.py` | Public PikaNews RSS feed |
| `scripts/admin_actions.py` | Moderation, deletion, restore and tombstones |
| `news_json/` | Generated article/category JSON feeds |
| `data/` | Stats, source failures and removal metadata |
| `frontend/` | Static reader pages, styles and browser JavaScript |
| `.github/workflows/news_collector.yml` | Scheduled collection and generated-content workflow |
| `.github/workflows/ci.yml` | Pull-request and push test gate |

## Local development

Use Python 3.11.

```bash
python -m pip install -r requirements-collector.txt python-dateutil pytest
pytest tests/test_classification_rules.py tests/test_guest_preferences.py tests/test_news_collector.py -q
python scripts/fetch_news.py
python scripts/generate_article_pages.py
python scripts/generate_sitemap.py
python scripts/generate_rss.py
python scripts/generate_news_sitemap.py
python scripts/validate_generated_articles.py
node --check frontend/js/preferences.js
```

The collector uses GitHub Actions in production. Do not run a local collector
against production data or push generated JSON manually without reviewing the
workflow and its tombstone/retention behavior.

## Contribution and deployment safety

- Work on a feature branch and open a pull request.
- Keep CI and collector tests green before merging.
- Do not change the GoGo central sync/deploy workflow from this repository.
- Preserve relative paths and subdirectory compatibility.
- Never expose admin credentials, tokens or private configuration in the
  frontend or repository.
