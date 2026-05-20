# PikaNews: Entertainment News Scraper & Aggregator

PikaNews is a production-grade, asynchronous Python-based scraping pipeline that aggregates, processes, and indexes Bollywood and Hollywood entertainment news from multiple sources.

## Features

- **Async Ingestion**: Leverages `aiohttp` + `asyncio` with configurable per-domain concurrency limits and exponential backoff retry logic.
- **Dynamic Playwright Fallback**: Auto-detects hydration-dependent JS pages, executing rendering via headless Chromium.
- **RSS-First Scrapes**: Prioritizes RSS/Atom parsing for speed and bandwidth optimization before falling back to listing page parses.
- **NLP Enrichment**: Integrates Named Entity Extraction (actors, films, studios) using spaCy, Language Detection (`langdetect`), Sentiment Buzz (`TextBlob`), and Local Summary Generation (Ollama LLM API).
- **Image De-duplication**: Features asynchronous image processing (resizing variants) and perceptual hash calculation (`imagehash`) to flag duplicate images.
- **Database Storage**: Supports Postgres or SQLite with full-text search indexing (FTS5 in SQLite, tsvector in Postgres).
- **FastAPI Endpoints**: Search index, celebrity lookup, trending keywords, and latest articles, fully instrumented with Prometheus metrics.
- **Scheduler**: Powered by `APScheduler` driven entirely by `config.yaml` cron parameters.
- **Alert Integrations**: Dispatches keyword-matched breaking-news alerts directly to Telegram, Discord, Slack, and custom webhooks.

---

## Architecture

```
                      +-------------------+
                      |    config.yaml    |
                      +---------+---------+
                                |
                                v
                      +---------+---------+
                      |     Scheduler     |
                      |   (APScheduler)   +---------------+
                      +---------+---------+               |
                                |                         |
                                v (Periodic Runs)         v
                      +---------+---------+        +------+------+
                      |  Scraper Engine   |        |  FastAPI UI |
                      | (aiohttp/Playwr.) |        |   & Search  |
                      +---------+---------+        +------+------+
                                |                         |
                                v                         |
                      +---------+---------+               |
                      |  HTML/RSS Parser  |               |
                      +---------+---------+               |
                                |                         |
                                v                         v
                      +---------+---------+        +------+------+
                      |    NLP/Image      |------->| SQLite FTS5 |
                      |    Pipelines      |        |  / Postgres |
                      +---------+---------+        +------+------+
                                |                         |
                                v                         v
                      +---------+---------+        +------+------+
                      |  Redis Cache      |        | Elastic /   |
                      |  (Deduplication)  |        | Webhooks    |
                      +-------------------+        +-------------+
```

---

## Directory Structure

```
PikaNews/
│
├── api/
│   └── server.py             # FastAPI Web backend
│
├── cli/
│   └── main.py               # Typer command line dashboard
│
├── scheduler/
│   └── runner.py             # Periodic APScheduler runner
│
├── scrapers/
│   └── engine.py             # Async client engine (UAs, Proxy pool, breakers)
│
├── parsers/
│   ├── feed.py               # RSS / Atom XML parser
│   └── html.py               # BeautifulSoup + Playwright dual-parser
│
├── models/
│   └── article.py            # Pydantic v2 schemas
│
├── pipelines/
│   ├── coordinator.py        # Central scraping task orchestrator
│   ├── db.py                 # SQLite FTS5 & Postgres adapter
│   ├── cache.py              # Redis Caching layer (ETags & Evasion)
│   ├── nlp.py                # spaCy, TextBlob, Ollama LLM processor
│   ├── image.py              # Image variant resizer & perceptual hashes
│   └── notifier.py           # Telegram / Discord / Slack notifications
│
├── config.yaml               # Sources selectors and cron parameters
├── Dockerfile                # Production multi-stage image
├── docker-compose.yml        # Docker compose orchestrator
├── requirements.txt          # Python library constraints
└── pyproject.toml            # Poetry configurations
```

---

## Installation & Setup

### Local Setup (Virtual Environment)

1. **Clone and Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize Playwright dependencies**:
   ```bash
   python -m playwright install chromium
   python -m playwright install-deps chromium
   ```

3. **Install spaCy language package**:
   ```bash
   python -m spacy download en_core_web_sm
   ```

4. **Ensure Redis & local Ollama are running**:
   ```bash
   # Ollama default endpoint must be up: http://localhost:11434
   ollama run Llama3
   ```

5. **Run DB initialization & start backend**:
   ```bash
   # API backend
   uvicorn api.server:app --host 0.0.0.0 --port 8000
   
   # Scheduler task loop
   python scheduler/runner.py
   ```

---

## Usage Commands (CLI)

Use the built-in CLI to test and operate the aggregator:

- **Dry-run a source configuration** (checks selectors and preview parse outputs without DB save):
  ```bash
  python cli/main.py test-source pinkvilla
  ```

- **Force run scraping cycle**:
  ```bash
  python cli/main.py scrape --source variety
  ```

- **Check cached database statistics**:
  ```bash
  python cli/main.py stats
  ```

- **Export stored data**:
  ```bash
  python cli/main.py export --format csv --output entertainment.csv
  ```

- **Purge database cache**:
  ```bash
  python cli/main.py purge
  ```

---

## API Documentation

The REST server starts on port `8000`:

- **Get latest articles**:
  - `GET http://localhost:8000/latest?limit=20`
- **Full Text Search**:
  - `GET http://localhost:8000/search?q=Marvel`
- **Filter by extracted celebrity names**:
  - `GET http://localhost:8000/by-celebrity/Salman%20Khan`
- **High-Velocity Trending buzz**:
  - `GET http://localhost:8000/trending`
- **Prometheus Metrics**:
  - `GET http://localhost:8000/metrics`

---

## Production Deployment

Deploy the system in Docker container cluster using Docker Compose:

```bash
# Build custom Playwright-spaCy images and spin up stack (Postgres + Redis + API + Scheduler)
docker-compose up --build -d
```
