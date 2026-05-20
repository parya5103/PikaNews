import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram
from pydantic import BaseModel
import structlog
from pipelines.db import DatabasePipeline
from pipelines.cache import RedisCachePipeline

# Initialize logger
logger = structlog.get_logger(__name__)

# Load config helper
def load_config() -> Dict[str, Any]:
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}

# Metrics definition
from prometheus_client import REGISTRY
for c in list(REGISTRY._collector_to_names.keys()):
    if any(name in ["api_requests_total", "api_latency_seconds"] for name in REGISTRY._collector_to_names[c]):
        try:
            REGISTRY.unregister(c)
        except KeyError:
            pass

API_REQUESTS_TOTAL = Counter("api_requests_total", "Total API Requests", ["method", "endpoint", "status"])
API_LATENCY_SECONDS = Histogram("api_latency_seconds", "API Request Latency", ["endpoint"])

# Create FastAPI app
app = FastAPI(
    title="PikaNews Aggregator API",
    description="Production-grade endpoints for querying aggregated Bollywood and Hollywood news",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipelines
db_pipeline: Optional[DatabasePipeline] = None
cache_pipeline: Optional[RedisCachePipeline] = None

@app.on_event("startup")
async def startup_event():
    global db_pipeline, cache_pipeline
    config = load_config()
    
    # DB init
    db_pipeline = DatabasePipeline(config)
    await db_pipeline.initialize()
    
    # Cache init
    cache_pipeline = RedisCachePipeline(config)
    await cache_pipeline.connect()
    
    logger.info("FastAPI service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    global cache_pipeline
    if cache_pipeline:
        await cache_pipeline.disconnect()
    logger.info("FastAPI service stopped")

# Webhook payload validator
class WebhookPayload(BaseModel):
    event: str
    article: Dict[str, Any]

@app.get("/health")
async def health_check():
    """Verify application integrity."""
    return {"status": "healthy", "service": "pikanews"}

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/latest")
async def get_latest(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None)
):
    """Retrieve list of latest scraped articles, with optional category filter."""
    API_REQUESTS_TOTAL.labels(method="GET", endpoint="/latest", status="200").inc()
    with API_LATENCY_SECONDS.labels(endpoint="/latest").time():
        try:
            articles = await db_pipeline.get_latest_articles(limit=limit, offset=offset, category=category)
            return {"count": len(articles), "articles": articles}
        except Exception as e:
            logger.error("Failed to query latest articles", error=str(e))
            raise HTTPException(status_code=500, detail="Database query error")

@app.get("/search")
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None)
):
    """Perform full-text search across titles, subtitles, and body text, with optional category filter."""
    API_REQUESTS_TOTAL.labels(method="GET", endpoint="/search", status="200").inc()
    with API_LATENCY_SECONDS.labels(endpoint="/search").time():
        try:
            articles = await db_pipeline.search_articles(query_string=q, limit=limit, category=category)
            return {"query": q, "count": len(articles), "articles": articles}
        except Exception as e:
            logger.error("Failed to search articles", query=q, error=str(e))
            raise HTTPException(status_code=500, detail="Search query error")

@app.get("/by-celebrity/{name}")
async def get_by_celebrity(
    name: str,
    limit: int = Query(20, ge=1, le=100)
):
    """Filter articles referencing a specific named celebrity/actor."""
    API_REQUESTS_TOTAL.labels(method="GET", endpoint="/by-celebrity", status="200").inc()
    with API_LATENCY_SECONDS.labels(endpoint="/by-celebrity").time():
        try:
            articles = await db_pipeline.get_by_celebrity(name=name, limit=limit)
            return {"celebrity": name, "count": len(articles), "articles": articles}
        except Exception as e:
            logger.error("Failed to query articles by celebrity", name=name, error=str(e))
            raise HTTPException(status_code=500, detail="Celebrity query error")

@app.get("/trending")
async def get_trending(
    limit: int = Query(10, ge=1, le=50)
):
    """Retrieve hot, high-velocity topics computed based on keyword spikes over 24 hrs."""
    API_REQUESTS_TOTAL.labels(method="GET", endpoint="/trending", status="200").inc()
    with API_LATENCY_SECONDS.labels(endpoint="/trending").time():
        try:
            articles = await db_pipeline.get_trending_articles(limit=limit)
            return {"count": len(articles), "articles": articles}
        except Exception as e:
            logger.error("Failed to query trending articles", error=str(e))
            raise HTTPException(status_code=500, detail="Trending query error")

@app.post("/webhook")
async def receive_webhook(payload: WebhookPayload):
    """Receiver webhook for external data integrations and integrations alerts."""
    logger.info("Webhook received", event=payload.event, article_title=payload.article.get("title"))
    return {"status": "accepted", "event": payload.event}

@app.get("/api/stats")
async def get_stats():
    """Retrieve database metrics and scraping distribution statistics."""
    try:
        stats = await db_pipeline.get_database_stats()
        return stats
    except Exception as e:
        logger.error("Failed to fetch stats", error=str(e))
        raise HTTPException(status_code=500, detail="Stats query error")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the premium, interactive monitoring dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PikaNews | Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #080b11;
            --bg-card: rgba(15, 23, 42, 0.6);
            --border-color: rgba(255, 255, 255, 0.05);
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-pink: #ec4899;
            --accent-green: #10b981;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            padding: 1.25rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
        }

        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            font-size: 2rem;
            animation: pulse 2.5s infinite;
        }

        .logo-text {
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .badge {
            background-color: rgba(59, 130, 246, 0.1);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.2);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }

        .container {
            max-width: 1500px;
            width: 100%;
            margin: 0 auto;
            padding: 2rem 1.5rem;
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 2rem;
            flex-grow: 1;
        }

        @media (max-width: 1100px) {
            .container {
                grid-template-columns: 1fr;
            }
        }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .main-content {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .card {
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
            border-color: rgba(255, 255, 255, 0.1);
        }

        .card-title {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #f8fafc;
        }

        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .stat-box {
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.02);
            border-radius: 0.75rem;
            padding: 1.25rem;
            text-align: center;
        }

        .stat-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 0.25rem;
            text-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
        }

        .stat-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.75px;
            color: var(--text-muted);
        }

        .list-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            font-size: 0.875rem;
        }

        .list-item:last-child {
            border-bottom: none;
        }

        .list-label {
            color: var(--text-muted);
            text-transform: capitalize;
        }

        .list-value {
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.15rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
        }

        /* Category Filter Bar */
        .category-filter-bar {
            display: flex;
            gap: 0.6rem;
            overflow-x: auto;
            padding-bottom: 0.5rem;
            scrollbar-width: thin;
        }

        .category-filter-bar::-webkit-scrollbar {
            height: 4px;
        }

        .category-filter-bar::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
        }

        .category-pill {
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 0.5rem 1.25rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .category-pill:hover {
            color: var(--text-main);
            background: rgba(30, 41, 59, 0.8);
            border-color: rgba(255, 255, 255, 0.1);
        }

        .category-pill.active {
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
            color: white;
            border-color: transparent;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
        }

        /* Search Section */
        .search-container {
            display: flex;
            gap: 1rem;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 0.75rem 1.25rem;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }

        .search-input {
            background: transparent;
            border: none;
            outline: none;
            color: var(--text-main);
            font-size: 1rem;
            width: 100%;
            font-family: inherit;
        }

        .search-input::placeholder {
            color: #475569;
        }

        .search-btn {
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
            color: white;
            border: none;
            outline: none;
            padding: 0.5rem 1.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }

        .search-btn:hover {
            filter: brightness(1.15);
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.4);
        }

        /* Article Card Grid */
        .article-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 1.5rem;
        }

        .article-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 100%;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }

        .article-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: transparent;
            transition: background 0.3s;
        }

        .article-card.bollywood::before {
            background: linear-gradient(to right, var(--accent-pink), #c084fc);
        }

        .article-card.hollywood::before {
            background: linear-gradient(to right, var(--accent-blue), var(--accent-purple));
        }

        .article-card:hover {
            transform: translateY(-4px);
            border-color: rgba(255, 255, 255, 0.1);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
        }

        .card-image-container {
            width: 100%;
            height: 200px;
            position: relative;
            background-color: #0f172a;
            overflow: hidden;
        }

        .card-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.5s;
        }

        .article-card:hover .card-image {
            transform: scale(1.05);
        }

        .card-image-placeholder {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
            color: rgba(255, 255, 255, 0.15);
            font-size: 2.5rem;
            font-weight: 700;
        }

        .card-category-badge {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 0.2rem 0.6rem;
            border-radius: 0.25rem;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-body {
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
            flex-grow: 1;
        }

        .card-meta {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .card-source {
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #f1f5f9;
        }

        .card-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            height: 3.2rem;
        }

        .card-excerpt {
            font-size: 0.875rem;
            color: var(--text-muted);
            line-height: 1.6;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            height: 2.8rem;
        }

        .card-pills {
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
            margin-top: auto;
        }

        .pill {
            padding: 0.15rem 0.6rem;
            border-radius: 0.25rem;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .pill.industry-bollywood { background: rgba(236, 72, 153, 0.15); color: #f472b6; }
        .pill.industry-hollywood { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
        .pill.sentiment-positive { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .pill.sentiment-neutral { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }
        .pill.sentiment-negative { background: rgba(239, 68, 68, 0.15); color: #f87171; }

        .card-actions {
            border-top: 1px solid var(--border-color);
            padding: 0.75rem 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.2);
        }

        .card-btn {
            background: transparent;
            border: none;
            color: #60a5fa;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            transition: color 0.2s;
        }

        .card-btn:hover {
            color: #93c5fd;
        }

        /* Detail Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(8, 11, 17, 0.85);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: none;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .modal-overlay.active {
            display: flex;
            opacity: 1;
        }

        .modal-container {
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            width: 90%;
            max-width: 800px;
            max-height: 85vh;
            overflow-y: auto;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            transform: translateY(20px);
            transition: transform 0.3s ease;
        }

        .modal-overlay.active .modal-container {
            transform: translateY(0);
        }

        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            background: #0f172a;
            z-index: 10;
        }

        .modal-close-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            transition: background-color 0.2s;
        }

        .modal-close-btn:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .modal-hero {
            width: 100%;
            height: 350px;
            position: relative;
            background-color: #020617;
        }

        .modal-hero-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .modal-content-area {
            padding: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .modal-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.35;
        }

        .modal-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.85rem;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
        }

        .modal-body-text {
            font-size: 1.05rem;
            line-height: 1.8;
            color: #cbd5e1;
            white-space: pre-wrap;
        }

        .modal-body-text p {
            margin-bottom: 1.25rem;
        }

        .summary-banner {
            background: rgba(99, 102, 241, 0.08);
            border-left: 4px solid #6366f1;
            padding: 1.25rem 1.5rem;
            border-radius: 0.5rem;
            font-size: 0.95rem;
            line-height: 1.6;
            color: #cbd5e1;
        }

        .entity-group {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
            padding: 0.5rem 0;
        }

        .entity-label {
            font-weight: 600;
            color: var(--text-muted);
            font-size: 0.85rem;
            min-width: 80px;
        }

        .entity-tag {
            background: rgba(139, 92, 246, 0.1);
            color: #c084fc;
            border: 1px solid rgba(139, 92, 246, 0.2);
            padding: 0.2rem 0.6rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .entity-tag:hover {
            background: rgba(139, 92, 246, 0.2);
            color: white;
        }

        .loading-spinner {
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            border-top: 3px solid var(--accent-blue);
            width: 32px;
            height: 32px;
            animation: spin 1s linear infinite;
            display: none;
            margin: 2rem auto;
        }

        .no-results {
            text-align: center;
            padding: 4rem;
            color: var(--text-muted);
            font-size: 1.1rem;
            grid-column: 1 / -1;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.85; transform: scale(1.03); }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-container">
            <span class="logo-icon">⚡</span>
            <span class="logo-text">PikaNews</span>
            <span class="badge">Command Center</span>
        </div>
        <div>
            <span id="scraping-indicator" class="badge" style="background-color: rgba(16, 185, 129, 0.1); color: #34d399; border-color: rgba(16, 185, 129, 0.2);">● Ingest Live</span>
        </div>
    </header>

    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="card">
                <div class="card-title">Database Metrics</div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div id="stat-total" class="stat-value">-</div>
                        <div class="stat-label">Total News</div>
                    </div>
                    <div class="stat-box">
                        <div id="stat-avg-sentiment" class="stat-value">-</div>
                        <div class="stat-label">Sentiment Buzz</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Categories</div>
                <div id="category-stats">
                    <div class="loading-spinner" style="display: block;"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Media Sources</div>
                <div id="source-stats" style="max-height: 250px; overflow-y: auto;">
                    <div class="loading-spinner" style="display: block;"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Sentiment Distribution</div>
                <div id="sentiment-stats">
                    <div class="loading-spinner" style="display: block;"></div>
                </div>
            </div>
        </div>

        <!-- Main Workspace -->
        <div class="main-content">
            <!-- Search & Filters -->
            <div class="search-container">
                <input type="text" id="search-input" class="search-input" placeholder="Search actor, movie name or news tag..." onkeypress="handleSearchKeyPress(event)">
                <div id="search-loader" class="loading-spinner" style="margin-right: 1rem; width: 20px; height: 20px;"></div>
                <button class="search-btn" onclick="executeSearch()">Search</button>
            </div>

            <!-- Category Filters -->
            <div class="category-filter-bar">
                <div class="category-pill active" onclick="selectCategory(null, this)">All Stream</div>
                <div class="category-pill" onclick="selectCategory('movie', this)">Movies</div>
                <div class="category-pill" onclick="selectCategory('tv', this)">TV & Shows</div>
                <div class="category-pill" onclick="selectCategory('reviews', this)">Reviews</div>
                <div class="category-pill" onclick="selectCategory('rumors', this)">Rumors</div>
                <div class="category-pill" onclick="selectCategory('gossip', this)">Gossip & Buzz</div>
            </div>

            <div id="feed-title" class="feed-section-header">Live Entertainment Stream</div>
            
            <!-- Ingest Loading -->
            <div id="feed-loader" class="loading-spinner" style="display: block; margin: 4rem auto;"></div>
            
            <!-- Cards Feed Grid -->
            <div id="article-feed" class="article-grid"></div>
        </div>
    </div>

    <!-- Article Reader Modal Overlay -->
    <div id="reader-modal" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal-container" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="badge" id="modal-category">News</div>
                <button class="modal-close-btn" onclick="toggleModal(false)">&times;</button>
            </div>
            <div id="modal-hero-container" class="modal-hero">
                <img id="modal-image" src="" alt="Featured hero Image" class="modal-hero-img" onerror="this.style.display='none'">
            </div>
            <div class="modal-content-area">
                <div id="modal-title" class="modal-title"></div>
                <div class="modal-meta">
                    <div><strong>Author:</strong> <span id="modal-author"></span></div>
                    <div><strong>Published:</strong> <span id="modal-published"></span></div>
                    <div><strong>Source:</strong> <span id="modal-source" style="text-transform: uppercase;"></span></div>
                </div>
                
                <div id="modal-summary-banner" class="summary-banner" style="display: none;"></div>
                
                <div id="modal-body" class="modal-body-text"></div>
                
                <div id="modal-entities-section" style="border-top: 1px solid var(--border-color); padding-top: 1rem; margin-top: 1.5rem; display: flex; flex-direction: column; gap: 0.5rem;">
                    <!-- Entities populated dynamically -->
                </div>
                
                <div style="margin-top: 1rem; display: flex; justify-content: flex-end;">
                    <a id="modal-source-link" href="" target="_blank" class="search-btn" style="text-decoration: none; text-align: center;">Visit Canonical Publisher ↗</a>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentCategory = null;
        let articlesCache = [];

        async function fetchStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('stat-total').innerText = data.total_articles;
                
                const avgSent = data.avg_sentiment;
                let sentimentLabel = avgSent.toFixed(2);
                if (avgSent > 0.05) sentimentLabel += ' (Positive)';
                else if (avgSent < -0.05) sentimentLabel += ' (Negative)';
                else sentimentLabel += ' (Neutral)';
                document.getElementById('stat-avg-sentiment').innerText = sentimentLabel;
                
                // Categories stats list
                const catStatsDiv = document.getElementById('category-stats');
                catStatsDiv.innerHTML = '';
                if (Object.keys(data.by_category).length === 0) {
                    catStatsDiv.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">No category tags indexed yet</div>';
                } else {
                    for (const [cat, count] of Object.entries(data.by_category)) {
                        catStatsDiv.innerHTML += `
                            <div class="list-item">
                                <span class="list-label">${cat}</span>
                                <span class="list-value">${count}</span>
                            </div>
                        `;
                    }
                }
                
                // Sources list
                const sourceDiv = document.getElementById('source-stats');
                sourceDiv.innerHTML = '';
                const sortedSources = Object.entries(data.by_source).sort((a,b) => b[1] - a[1]);
                for (const [src, count] of sortedSources) {
                    sourceDiv.innerHTML += `
                        <div class="list-item">
                            <span class="list-label">${src.replace('_', ' ')}</span>
                            <span class="list-value">${count}</span>
                        </div>
                    `;
                }
                
                // Sentiment stats list
                const sentDiv = document.getElementById('sentiment-stats');
                sentDiv.innerHTML = '';
                for (const [sent, count] of Object.entries(data.by_sentiment)) {
                    sentDiv.innerHTML += `
                        <div class="list-item">
                            <span class="list-label" style="text-transform: capitalize;">${sent}</span>
                            <span class="list-value">${count}</span>
                        </div>
                    `;
                }
            } catch (error) {
                console.error("Failed to load statistics UI", error);
            }
        }

        async function fetchFeed() {
            const loader = document.getElementById('feed-loader');
            const feed = document.getElementById('article-feed');
            
            loader.style.display = 'block';
            feed.innerHTML = '';
            
            try {
                let url = '/latest?limit=24';
                if (currentCategory) {
                    url += `&category=${encodeURIComponent(currentCategory)}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                articlesCache = data.articles;
                renderArticles(data.articles);
            } catch (error) {
                console.error("Failed to load feed stream", error);
                feed.innerHTML = '<div class="no-results">Error downloading aggregator news stream.</div>';
            } finally {
                loader.style.display = 'none';
            }
        }

        function renderArticles(articles) {
            const feed = document.getElementById('article-feed');
            feed.innerHTML = '';
            
            if (!articles || articles.length === 0) {
                feed.innerHTML = '<div class="no-results">No articles matching selection found.</div>';
                return;
            }
            
            articles.forEach(art => {
                const pubDate = new Date(art.published_at);
                const timeString = pubDate.toLocaleDateString() + ' ' + pubDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                const sentClass = 'sentiment-' + art.sentiment;
                const indClass = 'industry-' + art.industry;
                const borderClass = art.industry === 'bollywood' ? 'bollywood' : 'hollywood';
                
                // Set image html or placeholder
                let imageHtml = `<div class="card-image-placeholder">${art.title.charAt(0)}</div>`;
                if (art.featured_image_url) {
                    imageHtml = `<img src="${art.featured_image_url}" alt="Featured cover" class="card-image" onerror="this.onerror=null; this.parentNode.innerHTML='<div class=&quot;card-image-placeholder&quot;>🎬</div>';">`;
                }

                feed.innerHTML += `
                    <div class="article-card ${borderClass}">
                        <div class="card-image-container">
                            ${imageHtml}
                            <span class="card-category-badge">${art.category || 'News'}</span>
                        </div>
                        <div class="card-body">
                            <div class="card-meta">
                                <span class="card-source">${art.source.replace('_', ' ')}</span>
                                <span>${timeString}</span>
                            </div>
                            <div class="card-title" title="${art.title}">${art.title}</div>
                            <div class="card-excerpt">${art.body_text}</div>
                            <div class="card-pills">
                                <span class="pill ${indClass}">${art.industry}</span>
                                <span class="pill ${sentClass}">${art.sentiment}</span>
                            </div>
                        </div>
                        <div class="card-actions">
                            <button class="card-btn" onclick="openArticle('${art.sha256_hash}')">Quick Read &rarr;</button>
                            <a href="${art.canonical_url}" target="_blank" style="text-decoration: none; font-size: 0.75rem; color: var(--text-muted); hover: color: var(--text-main);">Publisher ↗</a>
                        </div>
                    </div>
                `;
            });
        }

        function openArticle(hash) {
            const article = articlesCache.find(a => a.sha256_hash === hash);
            if (!article) return;

            document.getElementById('modal-category').innerText = article.category || 'News';
            
            // Set Modal Image
            const img = document.getElementById('modal-image');
            const heroContainer = document.getElementById('modal-hero-container');
            if (article.featured_image_url) {
                img.src = article.featured_image_url;
                img.style.display = 'block';
                heroContainer.style.display = 'block';
            } else {
                img.src = "";
                img.style.display = 'none';
                heroContainer.style.display = 'none';
            }

            document.getElementById('modal-title').innerText = article.title;
            document.getElementById('modal-author').innerText = article.author || 'Unknown';
            
            const pubDate = new Date(article.published_at);
            document.getElementById('modal-published').innerText = pubDate.toLocaleString();
            document.getElementById('modal-source').innerText = article.source.replace('_', ' ');
            
            // Set Ollama Summary
            const summaryBanner = document.getElementById('modal-summary-banner');
            if (article.summary) {
                summaryBanner.innerHTML = `<strong>AI TL;DR Summary:</strong> ${article.summary}`;
                summaryBanner.style.display = 'block';
            } else {
                summaryBanner.style.display = 'none';
            }

            // Paragraph formats
            const bodyDiv = document.getElementById('modal-body');
            bodyDiv.innerHTML = article.body_text.split('\n\n').map(p => `<p>${p}</p>`).join('');

            // Entities rendering
            const entSection = document.getElementById('modal-entities-section');
            entSection.innerHTML = '';
            let hasEntities = false;
            
            const entities = article.entities || {};
            if (entities.actors && entities.actors.length > 0) {
                hasEntities = true;
                entSection.innerHTML += `
                    <div class="entity-group">
                        <span class="entity-label">Actors:</span>
                        ${entities.actors.map(a => `<span class="entity-tag" onclick="searchFor('${a}')">${a}</span>`).join('')}
                    </div>
                `;
            }
            if (entities.films && entities.films.length > 0) {
                hasEntities = true;
                entSection.innerHTML += `
                    <div class="entity-group">
                        <span class="entity-label">Films/Series:</span>
                        ${entities.films.map(f => `<span class="entity-tag" onclick="searchFor('${f}')">${f}</span>`).join('')}
                    </div>
                `;
            }
            
            if (!hasEntities) {
                entSection.style.display = 'none';
            } else {
                entSection.style.display = 'flex';
            }

            document.getElementById('modal-source-link').href = article.canonical_url;

            toggleModal(true);
        }

        function toggleModal(show) {
            const overlay = document.getElementById('reader-modal');
            if (show) {
                overlay.classList.add('active');
            } else {
                overlay.classList.remove('active');
            }
        }

        function closeModal(event) {
            toggleModal(false);
        }

        function selectCategory(cat, element) {
            currentCategory = cat;
            
            // Toggle active pill selection
            const pills = document.querySelectorAll('.category-pill');
            pills.forEach(p => p.classList.remove('active'));
            element.classList.add('active');
            
            const titleLabel = cat ? cat.charAt(0).toUpperCase() + cat.slice(1) : 'Live';
            document.getElementById('feed-title').innerText = `${titleLabel} Entertainment Stream`;
            
            fetchFeed();
        }

        function handleSearchKeyPress(event) {
            if (event.key === 'Enter') {
                executeSearch();
            }
        }

        function searchFor(term) {
            toggleModal(false);
            document.getElementById('search-input').value = term;
            executeSearch();
        }

        async function executeSearch() {
            const q = document.getElementById('search-input').value.trim();
            if (!q) {
                fetchFeed();
                return;
            }
            
            const loader = document.getElementById('search-loader');
            const feed = document.getElementById('article-feed');
            
            loader.style.display = 'block';
            feed.innerHTML = '';
            
            try {
                document.getElementById('feed-title').innerText = `Search results for: "${q}"`;
                
                let url = `/search?q=${encodeURIComponent(q)}&limit=30`;
                if (currentCategory) {
                    url += `&category=${encodeURIComponent(currentCategory)}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                articlesCache = data.articles;
                renderArticles(data.articles);
            } catch (error) {
                console.error("Failed to query search parameters", error);
                feed.innerHTML = '<div class="no-results">Error executing search.</div>';
            } finally {
                loader.style.display = 'none';
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            fetchStats();
            fetchFeed();
            // Refresh stats dashboard periodically
            setInterval(fetchStats, 20000);
        });

        // Close on escape key
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                toggleModal(false);
            }
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    print("Starting PikaNews Dashboard at http://localhost:8000/dashboard")
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
