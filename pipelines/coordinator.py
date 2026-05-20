import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import structlog

from scrapers.engine import ScraperEngine
from parsers.feed import FeedParser
from parsers.html import HTMLParser
from models.article import Article
from pipelines.nlp import NLPProcessor
from pipelines.image import ImagePipeline
from pipelines.db import DatabasePipeline
from pipelines.cache import RedisCachePipeline
from pipelines.notifier import AlertNotifier

logger = structlog.get_logger(__name__)

class ScrapeCoordinator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.engine = ScraperEngine(config)
        self.nlp_processor = NLPProcessor(config)
        self.db_pipeline = DatabasePipeline(config)
        self.cache_pipeline = RedisCachePipeline(config)
        self.image_pipeline = ImagePipeline(config, self.engine)
        self.notifier = AlertNotifier(config)

    async def initialize_pipelines(self):
        """Prepare database connections and caching layers."""
        await self.db_pipeline.initialize()
        await self.cache_pipeline.connect()

    async def close_pipelines(self):
        """Clean up caching connections."""
        await self.cache_pipeline.disconnect()

    async def scrape_source(self, source_name: str) -> Dict[str, Any]:
        """Scrape articles from a configured source name. Implements RSS-first strategy."""
        source_config = next((s for s in self.config.get("sources", []) if s["name"] == source_name), None)
        if not source_config:
            logger.error("Source not found in configuration", source=source_name)
            return {"source": source_name, "scraped": 0, "errors": 1}

        logger.info("Starting scrape job for source", source=source_name)
        articles_to_scrape: List[Dict[str, Any]] = []

        # 1. RSS-First Check
        rss_url = source_config.get("rss_url")
        if rss_url:
            logger.info("RSS feed URL found, checking feed first", source=source_name, url=rss_url)
            # Fetch RSS feed respecting HTTP Cache headers
            headers_cache = await self.cache_pipeline.get_etag_or_last_modified(rss_url)
            
            # Note: ScraperEngine fetch handles fetching raw XML
            xml_content = await self.engine.fetch(source_name, rss_url)
            if xml_content:
                parsed_feed_items = FeedParser.parse(xml_content, source_config)
                for item in parsed_feed_items:
                    articles_to_scrape.append(item)
                logger.info("Found items via RSS feed", count=len(articles_to_scrape), source=source_name)

        # 2. HTML Scrape Fallback (if RSS unavailable or returned empty)
        if not articles_to_scrape:
            logger.info("RSS empty or absent, falling back to listing page parsing", source=source_name)
            base_url = source_config["base_url"]
            html_content = await self.engine.fetch(source_name, base_url)
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                link_sel = source_config.get("selectors", {}).get("article_link", "a")
                link_elements = soup.select(link_sel)
                
                urls_seen = set()
                for el in link_elements:
                    href = el.get("href")
                    if href:
                        url = urljoin(base_url, href)
                        if url not in urls_seen and url != base_url:
                            urls_seen.add(url)
                            articles_to_scrape.append({
                                "canonical_url": url,
                                "title": el.text.strip() if el.text else "Article Link",
                                "published_at": datetime.now(timezone.utc),
                                "tags": [],
                                "description": ""
                            })
                logger.info("Found items via listing page parsing", count=len(articles_to_scrape), source=source_name)

        # 3. Process Ingestion Queue (deduplicate and scrape details)
        saved_count = 0
        skipped_count = 0
        error_count = 0

        for item in articles_to_scrape[:15]:  # Limit ingestion batch size per execution to avoid throttling
            url = item["canonical_url"]
            title = item.get("title", "")
            
            # Dedup check
            sha256_hash = self.db_pipeline.calculate_hash(title, url)
            
            # We can check DB directly or local cache
            is_cached = await self.cache_pipeline.get(f"article_hash:{sha256_hash}")
            if is_cached:
                skipped_count += 1
                continue

            try:
                # 4. Fetch Article HTML details
                article_html = await self.engine.fetch(source_name, url)
                
                # Parse content details
                details = await HTMLParser.parse_article(article_html, url, source_config)
                if not details or not details["body_text"]:
                    logger.warn("Parsed content empty for article, skipping", url=url)
                    error_count += 1
                    continue

                # Merge feed metadata with page scrape (prefer scraped tags/title/date)
                published_str = details["published_at"] or item.get("published_at")
                if not published_str:
                    published_date = datetime.now(timezone.utc)
                elif isinstance(published_str, datetime):
                    published_date = published_str
                else:
                    try:
                        # Normalize ISO representation
                        published_date = datetime.fromisoformat(str(published_str).replace("Z", "+00:00"))
                    except Exception:
                        published_date = datetime.now(timezone.utc)

                final_title = details["title"] or title
                
                # Create base Pydantic Article model
                article = Article(
                    title=final_title,
                    subtitle=details["subtitle"],
                    author=details["author"] or "Unknown",
                    published_at=published_date,
                    source=source_name,
                    category=source_config.get("category", "movie"),
                    industry=source_config["industry"],
                    tags=details["tags"] or item.get("tags", []),
                    body_text=details["body_text"],
                    body_html=details["body_html"],
                    featured_image_url=details["featured_image_url"],
                    canonical_url=url,
                    video_embeds=details["video_embeds"]
                )
                article.calculate_reading_time()

                # 5. NLP Enrichment
                # TextBlob sentiment & Language
                article.language = self.nlp_processor.detect_lang(article.body_text)
                sent_res = self.nlp_processor.analyze_sentiment(article.body_text)
                article.sentiment = sent_res["sentiment"]
                article.sentiment_score = sent_res["score"]
                
                # Extract entities
                article.entities = self.nlp_processor.extract_entities(article.body_text)

                # Ollama generation summary/tags (async fallback if running)
                # Ensure we run this only for longer texts
                try:
                    ollama_res = await self.nlp_processor.generate_summary_and_tags_via_ollama(
                        article.title, article.body_text
                    )
                    if ollama_res.get("summary"):
                        article.summary = ollama_res["summary"]
                    if ollama_res.get("tags"):
                        # Merge tags
                        article.tags = list(set(article.tags + ollama_res["tags"]))
                except Exception as ex:
                    logger.debug("Ollama summary generation bypassed or failed", error=str(ex))

                # 6. Image pipeline execution
                if article.featured_image_url:
                    img_res = await self.image_pipeline.process_image(str(article.featured_image_url), source_name)
                    article.image_phash = img_res["image_phash"]
                    article.local_image_paths = img_res["local_paths"]

                # 7. Write record to Database and cache deduplication key
                data_dict = article.model_dump()
                inserted = await self.db_pipeline.save_article(data_dict)
                if inserted:
                    saved_count += 1
                    # Notify external webhooks
                    await self.notifier.notify_all(data_dict)
                    # Cache the hash key
                    await self.cache_pipeline.set(f"article_hash:{sha256_hash}", "1")
                else:
                    skipped_count += 1

            except Exception as e:
                logger.error("Error processing article", url=url, error=str(e))
                error_count += 1

        logger.info(
            "Scrape source task completed",
            source=source_name,
            ingested=saved_count,
            duplicates_skipped=skipped_count,
            errors=error_count
        )
        return {
            "source": source_name,
            "scraped": saved_count,
            "skipped": skipped_count,
            "errors": error_count
        }
