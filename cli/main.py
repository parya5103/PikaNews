import os
import sys
import asyncio
import json
import csv
import yaml
import typer
from typing import Optional
from datetime import datetime, timezone
import structlog

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.coordinator import ScrapeCoordinator
from pipelines.db import DatabasePipeline
from scrapers.engine import ScraperEngine
from parsers.html import HTMLParser

# Typer CLI app
app = typer.Typer(help="CLI tool to manage and debug the PikaNews Aggregator")

# Logger setup
logger = structlog.get_logger(__name__)

def load_config() -> dict:
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not os.path.exists(config_path):
        typer.echo(f"Error: Config not found at {config_path}")
        raise typer.Exit(code=1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_async(coro):
    """Utility helper to run async coroutine synchronously inside Typer."""
    return asyncio.run(coro)

@app.command()
def scrape(
    source: Optional[str] = typer.Option(None, help="Name of the source to scrape (e.g. pinkvilla, variety). If omitted, scrapes all sources.")
):
    """Manually trigger ingestion cycle for specific source or all sources."""
    config = load_config()
    coordinator = ScrapeCoordinator(config)
    
    async def _run():
        await coordinator.initialize_pipelines()
        sources_to_run = [source] if source else [s["name"] for s in config.get("sources", [])]
        
        for name in sources_to_run:
            typer.echo(f"Starting manual scrape for: {name}...")
            res = await coordinator.scrape_source(name)
            typer.echo(f"Scrape completed: Ingested={res.get('scraped')}, Skipped={res.get('skipped')}, Errors={res.get('errors')}")
            
        await coordinator.close_pipelines()

    run_async(_run())

@app.command()
def test_source(
    name: str = typer.Argument(..., help="Name of the source defined in config.yaml"),
    url: Optional[str] = typer.Option(None, help="Specific article URL to test. If omitted, parses listing page/RSS feeds.")
):
    """Test scrape selectors configuration and preview extraction outputs without saving to Database."""
    config = load_config()
    source_config = next((s for s in config.get("sources", []) if s["name"] == name), None)
    
    if not source_config:
        typer.echo(f"Error: Source '{name}' not found in config.yaml")
        raise typer.Exit(code=1)

    engine = ScraperEngine(config)

    async def _run():
        target_url = url
        if not target_url:
            # Try fetching index page
            typer.echo(f"Testing listing page extraction for: {name} from {source_config['base_url']}")
            html = await engine.fetch(name, source_config["base_url"])
            if not html:
                typer.echo("Failed to fetch base URL")
                return
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            soup = BeautifulSoup(html, "html.parser")
            link_sel = source_config.get("selectors", {}).get("article_link", "a")
            links = soup.select(link_sel)
            if not links:
                typer.echo("Failed to parse article links from index page")
                return
            target_url = urljoin(source_config["base_url"], links[0].get("href"))

        typer.echo(f"Fetching article content from: {target_url}")
        art_html = await engine.fetch(name, target_url)
        if not art_html:
            typer.echo("Failed to fetch article body HTML")
            return
            
        details = await HTMLParser.parse_article(art_html, target_url, source_config)
        if not details:
            typer.echo("Failed to parse article details using defined selectors")
            return

        typer.echo("\n--- Extraction Results ---")
        typer.echo(f"Title:       {details.get('title')}")
        typer.echo(f"Subtitle:    {details.get('subtitle')}")
        typer.echo(f"Author:      {details.get('author')}")
        typer.echo(f"Date:        {details.get('published_at')}")
        typer.echo(f"Image:       {details.get('featured_image_url')}")
        typer.echo(f"Tags:        {details.get('tags')}")
        typer.echo(f"Embeds:      {details.get('video_embeds')}")
        body = details.get('body_text', '')
        typer.echo(f"Body (chars): {len(body)} chars")
        typer.echo(f"Body snippet:\n{body[:400]}...")

    run_async(_run())

@app.command()
def stats():
    """Print current ingestion statistics and record counts."""
    config = load_config()
    db = DatabasePipeline(config)
    
    async def _run():
        await db.initialize()
        latest = await db.get_latest_articles(limit=1000)
        
        counts_by_src = {}
        counts_by_ind = {"bollywood": 0, "hollywood": 0}
        counts_by_cat = {}
        
        for art in latest:
            src = art["source"]
            counts_by_src[src] = counts_by_src.get(src, 0) + 1
            
            ind = art["industry"]
            counts_by_ind[ind] = counts_by_ind.get(ind, 0) + 1
            
            cat = art["category"]
            counts_by_cat[cat] = counts_by_cat.get(cat, 0) + 1

        typer.echo("\n===== INGESTION STATISTICS =====")
        typer.echo(f"Total Articles cached: {len(latest)}")
        
        typer.echo("\nCounts by Source:")
        for k, v in counts_by_src.items():
            typer.echo(f"  - {k}: {v}")
            
        typer.echo("\nCounts by Industry:")
        for k, v in counts_by_ind.items():
            typer.echo(f"  - {k}: {v}")
            
        typer.echo("\nCounts by Category:")
        for k, v in counts_by_cat.items():
            typer.echo(f"  - {k}: {v}")

    run_async(_run())

@app.command()
def export(
    format: str = typer.Option("json", help="Export file format: json, csv, jsonl"),
    output: str = typer.Option("export_data.json", help="Path to write the output file")
):
    """Export article datasets to local files."""
    config = load_config()
    db = DatabasePipeline(config)
    
    async def _run():
        await db.initialize()
        articles = await db.get_latest_articles(limit=5000)
        
        if not articles:
            typer.echo("No articles found in DB to export.")
            return

        if format.lower() == "json":
            with open(output, "w", encoding="utf-8") as f:
                json.dump(articles, f, default=str, indent=2)
                
        elif format.lower() == "jsonl":
            with open(output, "w", encoding="utf-8") as f:
                for a in articles:
                    f.write(json.dumps(a, default=str) + "\n")
                    
        elif format.lower() == "csv":
            if not articles:
                return
            headers = list(articles[0].keys())
            with open(output, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for a in articles:
                    # Flatten dicts/lists to strings for CSV compatibility
                    row = {}
                    for k, v in a.items():
                        if isinstance(v, (list, dict)):
                            row[k] = json.dumps(v, default=str)
                        else:
                            row[k] = v
                    writer.writerow(row)
        else:
            typer.echo(f"Unsupported format: {format}")
            return
            
        typer.echo(f"Exported {len(articles)} articles to {output} successfully.")

    run_async(_run())

@app.command()
def purge():
    """Purge all database records (warning: destructive)."""
    confirm = typer.confirm("Are you sure you want to clear the entire database?")
    if not confirm:
        typer.echo("Aborted.")
        raise typer.Exit()

    config = load_config()
    
    async def _run():
        db_pipeline = DatabasePipeline(config)
        # Recreate tables by deleting files or executing truncate
        if db_pipeline.use_postgres:
            import asyncpg
            conn = await asyncpg.connect(db_pipeline.postgres_url)
            await conn.execute("TRUNCATE TABLE articles;")
            await conn.close()
            typer.echo("Postgres database purged.")
        else:
            path = db_pipeline.sqlite_path
            if os.path.exists(path):
                os.remove(path)
                typer.echo(f"SQLite file {path} deleted.")
            else:
                typer.echo("Database file does not exist.")

    run_async(_run())

if __name__ == "__main__":
    app()
