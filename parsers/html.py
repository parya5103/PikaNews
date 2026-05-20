import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import structlog

logger = structlog.get_logger(__name__)

class HTMLParser:
    @staticmethod
    def parse_static(html_content: str, source_config: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Extract article data from raw HTML using selectors defined in source config."""
        selectors = source_config.get("selectors", {})
        soup = BeautifulSoup(html_content, "html.parser")
        
        result: Dict[str, Any] = {
            "title": "",
            "subtitle": None,
            "author": "Unknown",
            "published_at": None,
            "body_text": "",
            "body_html": None,
            "featured_image_url": None,
            "gallery_urls": [],
            "video_embeds": [],
            "tags": []
        }

        # Title
        title_sel = selectors.get("title", "h1")
        title_el = soup.select_one(title_sel)
        if title_el:
            result["title"] = title_el.text.strip()
        else:
            # Fallback title parsing from meta
            og_title = soup.find("meta", property="og:title") or soup.find("meta", name="title")
            if og_title:
                result["title"] = og_title.get("content", "").strip()

        # Author
        author_sel = selectors.get("author")
        if author_sel:
            author_el = soup.select_one(author_sel)
            if author_el:
                result["author"] = author_el.text.strip()

        # Published At
        pub_sel = selectors.get("published_at")
        if pub_sel:
            pub_el = soup.select_one(pub_sel)
            if pub_el:
                pub_str = pub_el.get("datetime") or pub_el.get("content") or pub_el.text
                result["published_at"] = pub_str

        if not result["published_at"]:
            # Fallback published time from meta
            pub_meta = (
                soup.find("meta", property="article:published_time") or 
                soup.find("meta", name="publish-date") or
                soup.find("meta", property="og:pubdate")
            )
            if pub_meta:
                result["published_at"] = pub_meta.get("content")

        # Body Text & Safe HTML
        body_sel = selectors.get("body_text", "article")
        body_els = soup.select(body_sel)
        if body_els:
            paragraphs = [p.text.strip() for p in body_els if p.text.strip()]
            result["body_text"] = "\n\n".join(paragraphs)
            
            # Wrap paragraphs in clean HTML container
            result["body_html"] = "".join(str(p) for p in body_els)
        else:
            # Fallback content scrape if selector fails
            body_container = soup.find("article") or soup.find("div", class_=re.compile("post-content|article-content|entry-content"))
            if body_container:
                p_elements = body_container.find_all("p")
                if p_elements:
                    result["body_text"] = "\n\n".join(p.text.strip() for p in p_elements if p.text.strip())
                    result["body_html"] = "".join(str(p) for p in p_elements)

        # Featured Image URL
        img_sel = selectors.get("featured_image")
        if img_sel:
            img_el = soup.select_one(img_sel)
            if img_el:
                result["featured_image_url"] = img_el.get("content") or img_el.get("src")
        
        if not result["featured_image_url"]:
            og_img = soup.find("meta", property="og:image")
            if og_img:
                result["featured_image_url"] = og_img.get("content")

        # Extract tags
        tag_els = soup.select(".tags a, .article-tags a, a[href*='/tag/']")
        result["tags"] = list(set([el.text.strip() for el in tag_els if el.text.strip()]))

        # Extract video embeds
        iframes = soup.find_all("iframe")
        for iframe in iframes:
            src = iframe.get("src")
            if src and any(domain in src for domain in ["youtube.com", "youtu.be", "vimeo.com", "dailymotion.com"]):
                result["video_embeds"].append(src)

        return result

    @classmethod
    async def parse_dynamic(cls, url: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Launch dynamic render browser using Playwright, wait for content load, and extract data with proxy and evasion setups."""
        import os
        import random
        from scrapers.engine import USER_AGENTS
        
        logger.info("Falling back to Playwright for dynamic page rendering", url=url, source=source_config["name"])
        
        # Load proxy list if available
        proxies = []
        proxies_file = "proxies.txt"
        if os.path.exists(proxies_file):
            try:
                with open(proxies_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            proxies.append(line)
            except Exception as e:
                logger.warn("Could not read proxies.txt for Playwright context", error=str(e))
        
        proxy_config = None
        if proxies:
            chosen_proxy = random.choice(proxies)
            proxy_config = {"server": chosen_proxy}
            logger.info("Using proxy for Playwright request", proxy=chosen_proxy)

        try:
            async with async_playwright() as p:
                # Launch headless browser with proxy
                browser = await p.chromium.launch(headless=True, proxy=proxy_config)
                
                # Create a fresh isolated context with custom User Agent and Evasion settings
                user_agent = random.choice(USER_AGENTS)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                    bypass_csp=True,
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Connection": "keep-alive"
                    }
                )
                page = await context.new_page()
                
                # Navigate and wait until DOM is parsed (avoiding waiting on heavy ad tracking)
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                # Wait extra to let JS dynamic elements render
                await page.wait_for_timeout(2000)
                
                html_content = await page.content()
                await browser.close()
                
                # Standard parsing of fully-rendered HTML
                return cls.parse_static(html_content, source_config, url)
        except Exception as e:
            logger.error("Playwright scraping failed", url=url, source=source_config["name"], error=str(e))
            return None

    @classmethod
    async def parse_article(cls, static_html: Optional[str], url: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Decide between static or dynamic scraper, executes extraction and normalizes results."""
        data = None
        if static_html:
            data = cls.parse_static(static_html, source_config, url)

        # Trigger dynamic parsing if article content appears empty (indicating hydration requirements)
        if not data or not data["body_text"] or len(data["body_text"]) < 100:
            logger.info("Static content empty or too short. Triggering Playwright fallback.", url=url)
            dynamic_data = await cls.parse_dynamic(url, source_config)
            if dynamic_data and dynamic_data["body_text"]:
                data = dynamic_data

        return data
