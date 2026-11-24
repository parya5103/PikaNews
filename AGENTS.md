# PikaNews - Agent Instructions

Operating rules for any AI coding agent in parya5103/PikaNews.

## Read first
- README.md (current production architecture, local dev commands) and KNOWLEDGE.md.
- Inspect code before changing it; smallest safe change; no new dependencies without a
  demonstrated need.

## Publishing model (do not break)
- The collector (news_collector.yml, every 30 min) commits generated data to main; the
  gogo-website sync-pikanews workflow is the ONLY publisher. Do not add a Pages deploy job,
  and do not change the central sync workflow from this repo.
- Keep frontend asset/data paths RELATIVE (frontend/js/data.js uses "data"); the app runs
  under the /pikanews/ subdirectory.

## Editorial safeguards (hard rules)
- Aggregated third-party stories stay noindex,follow and out of both sitemaps.
- The Google News sitemap only includes substantial original editorial that passes the
  author/date/content checks; thin stories are never indexable or ad-adjacent.
- Never guess publication dates into freshness or expiry logic; tombstones block re-import
  of removed/expired stories and must keep working.
- Keep source attribution and original-publisher links on every story. PikaNews never
  republishes full articles or images.

## Testing requirements
- Every PR keeps ci.yml green (pytest). Careful: the string-invariant tests scan COMMENTS
  too; publisher IDs or forbidden patterns inside comments fail the build. Fix behavior or
  reword comments; never weaken assertions.
- ads.js changes must preserve the single-loader pattern, fail-closed cmpReady gate and
  placement rules (no ads on legal/search/admin/error pages).

## Process
- The collector moves main every ~30 minutes: branch immediately before the PR; if a
  conflict appears on generated files, recreate the branch from the latest main.
- No force push; no direct commits to main; merge only with owner approval.
- Never commit secrets or .env values; reference environment variable names only.
- Update README.md/KNOWLEDGE.md when architecture changes; do not claim collector or sync
  success without the workflow run proving it.
