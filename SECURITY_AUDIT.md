# PikaNews Security Audit

Date: 2026-11-06. Scope: parya5103/PikaNews (frontend published at
gogocompany.in/pikanews/ via the gogo-website sync workflow; optional
self-hosted FastAPI API). Audit covers visitor-facing pages, the API server
(api/server.py), GitHub Actions workflows, and dependency/supply-chain posture.

Severity scale: Critical / High / Medium / Low / Informational.

## Findings

### PK-01 (High) - Visitor-facing GitHub links on published pages
- File: frontend/index.html (footer social icon linking to
  https://github.com/parya5103/PikaNews), frontend/search.html (dead "#"
  GitHub icon).
- Behavior: the footer exposed the repository URL and a GitHub icon to every
  visitor. The official visitor support channel is the GoGo Company email.
- Impact: encourages visitors to open issues/PRs on the development repo,
  exposing internal infrastructure to abuse and confusing support routing.
- Fix: both icons replaced with a mailto link to
  officialgogocompany@gmail.com (envelope icon, aria-label "Email GoGo
  Company"). Verified by test_no_visitor_facing_github_links.
- Remaining risk: other pages were scanned by the same test (all clean).

### PK-02 (High) - Wildcard CORS with credentials on the API
- File: api/server.py.
- Behavior: `allow_origins=["*"]` combined with `allow_credentials=True`,
  `allow_methods=["*"]`, `allow_headers=["*"]`. The wildcard+credentials
  combination is invalid per the CORS spec and, where a middleware echoes
  origins, would let any website make credentialed cross-origin requests.
- Impact: any origin could call the API with cookies/credentials if the API
  is ever deployed with an authentication layer.
- Fix: explicit origin allowlist (default: https://gogocompany.in, override
  with PIKANEWS_ALLOWED_ORIGINS), methods limited to GET/POST, headers
  limited to Content-Type, X-Signature, X-Timestamp. Exact-match check in
  api/security.py (is_origin_allowed) covered by unit tests.
- Remaining risk: none identified for the allowlist logic itself.

### PK-03 (High) - Unauthenticated webhook accepting arbitrary payloads
- File: api/server.py POST /webhook.
- Behavior: any anonymous client could POST any JSON of any size; the
  payload was only shallowly typed (event: str, article: dict) and logged.
- Impact: spam/log flooding, log injection via unbounded article fields,
  potential resource exhaustion.
- Fix: fail-closed HMAC-SHA256 signature (X-Signature) + timestamp replay
  window (X-Timestamp, +/-300s), 64KB body cap, structural payload
  validation (bounded event/article fields, http(s)-only article URLs),
  safe generic error responses. When PIKANEWS_WEBHOOK_SECRET is unset the
  endpoint returns 403 "Webhook disabled". Covered by
  tests/test_api_security.py.
- Remaining risk: in-memory rate limiting is per-process only (documented).

### PK-04 (Medium) - Public monitoring endpoints
- Files: api/server.py /metrics, /dashboard, /, /api/stats.
- Behavior: internal operational metrics (Prometheus), a monitoring
  dashboard, and database distribution stats were reachable by anyone.
- Impact: information disclosure about internals and traffic patterns.
- Fix: all four endpoints now require `Authorization: Bearer
  <PIKANEWS_MONITOR_TOKEN>`; when the token is unset they return 404
  (fail-closed, no existence oracle). Public read-only news endpoints
  (/health, /latest, /search, /trending, /by-celebrity) remain open as
  required.
- Remaining risk: none for static analysis; runtime verification requires a
  deployment (not available in CI).

### PK-05 (Medium) - No rate limiting / request-size caps
- File: api/server.py.
- Behavior: no per-client limits; search accepted arbitrarily long q
  values; no body-size guard.
- Impact: resource exhaustion and abuse.
- Fix: sliding-window per-client rate limiter middleware (60 req/min
  default, PIKANEWS_RATE_LIMIT), 64KB webhook body cap, q max_length=200,
  by-celebrity name max_length=100. Pagination limits already capped
  (limit<=100). Covered by unit tests for the limiter.
- Remaining risk: single-process limiter; multi-process deployments need a
  shared limiter (documented in api/security.py).

### PK-06 (Medium) - Workflow input interpolation into shell commands
- File: .github/workflows/news-admin.yml.
- Behavior: `${{ inputs.* }}` was interpolated directly into a `run:`
  script (commit message and argument list). workflow_dispatch inputs are
  restricted to users with write access, so exploitation requires a
  malicious/compromised admin, but the pattern is a known script-injection
  vector.
- Fix: inputs are passed through environment variables and double-quoted
  shell expansions.
- Remaining risk: none known; admin actions remain GitHub-authenticated.

### PK-07 (Low) - Unpinned third-party/official Actions
- Files: all .github/workflows/*.yml.
- Behavior: actions referenced by mutable tags (@v3/@v4/@v5); a compromised
  or renamed upstream tag would silently change CI behavior.
- Fix: every action pinned to an immutable commit SHA (with the tag kept as
  a comment). SHAs resolved from the tags via the GitHub API on 2026-11-06.
- Remaining risk: none; dependabot tracks future updates.

### PK-08 (Low) - No automated dependency/vulnerability scanning
- Fix: added .github/dependabot.yml (github-actions + pip, weekly) and
  .github/workflows/codeql.yml (python, weekly + push/PR).
- Remaining risk: CodeQL is newly added; first results appear after merge.

## Verified without change (informational)
- SQL: pipelines/db.py uses parameterized queries (placeholder-based
  executes); no string-formatted SQL found in an audit grep.
- Error handling: existing handlers already return generic messages and
  log details server-side; no stack traces are returned to clients.
- Static frontend has no service worker, no form endpoints, no localStorage;
  article data is rendered through escapeHtml (utils.js) and generator-side
  escaping; the production-build tests assert the generator contracts.
- Secrets: workflows use GitHub Secrets only; the audit found no embedded
  credentials (POSTGRES_URL passed via env, never printed).

## Explicitly retained (not removed)
- Internal/developer GitHub references: README, DEPLOYMENT_GUIDE.md,
  IMPLEMENTATION_NOTES.md, IMPLEMENTATION_SUMMARY.md, deployment_guide.md,
  scripts/, tests/ (including the User-Agent string "PikaNews-Bot/2.0
  (+https://github.com/parya5103/PikaNews)" used for scraper politeness).
- The daily scrape.yml DB artifact flow, news-admin audit log, and all
  public read-only news functionality.
