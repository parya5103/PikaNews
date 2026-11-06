#!/usr/bin/env python3
"""
PikaNews Automatic News Collection Engine v2.0
Fetches news from RSS feeds, deduplicates, normalizes, and saves to JSON files.
Designed to run in GitHub Actions every 30 minutes.

Key improvements:
- Better category detection
- Clean text extraction from HTML summaries
- Image URL extraction from RSS feeds
- Proper duplicate detection
- Retry logic for failed requests
- Better error handling
- More reliable source configuration
"""

import os
import sys
import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

# Configure paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
NEWS_JSON_DIR = os.path.join(REPO_ROOT, "news_json")
LOG_DIR = os.path.join(REPO_ROOT, "logs")
REMOVED_ARTICLES_FILE = os.path.join(DATA_DIR, "removed_articles.json")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(NEWS_JSON_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# User agent for requests
USER_AGENT = "PikaNews-Bot/2.0 (+https://github.com/parya5103/PikaNews)"

# Global state for tracking
seen_hashes: Set[str] = set()
failed_sources: List[Dict[str, str]] = []
stats: Dict[str, Any] = {}

# Maximum articles to keep per category to prevent bloating
MAX_ARTICLES_PER_CATEGORY = 500
MAX_TOTAL_ARTICLES = 2000


def log(message: str, level: str = "INFO"):
    """Simple logging function."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    # Also write to log file
    log_file = os.path.join(LOG_DIR, f"fetch_news_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception:
        pass  # Don't fail if logging fails


# Enhanced category keywords with priority
CATEGORY_KEYWORDS = {
    "bollywood": {
        "keywords": [
            "bollywood", "hindi cinema", "hindi film", "hindi movie", 
            "indian cinema", "indian film", "indian movie",
            "tollywood", "kollywood", "sandalwood",
            "ranbir", "salman", "shahrukh", "akshay", "amir", "aamir",
            "deepika", "alia", "priyanka", "katrina", "kareena",
            "varun", "sidharth", "vicky", "kartik", "ara",
            "nitesh tiwari", "karan johar", "rohit shetty",
            "yash raj", "dharma", "red chillies",
            "filmfare", "pinkvilla", "bollywood hungama"
        ],
        "priority": 10
    },
    "hollywood": {
        "keywords": [
            "hollywood", "american cinema", "american film", "american movie",
            "oscar", "emmy", "grammy", "golden globe",
            "marvel", "dc comics", "dc", "star wars", "star trek",
            "disney", "warner bros", "universal", "paramount", "20th century",
            "netflix", "amazon prime", "hbo", "apple tv",
            "tom cruise", "brad pitt", "leonardo dicaprio", "robert downey",
            "chris evans", "chris hemsworth", "scarlett johansson",
            "margot robbie", "jennifer lawrence", "dwayne johnson",
            "variety", "deadline", "hollywood reporter", "entertainment weekly"
        ],
        "priority": 10
    },
    "entertainment": {
        "keywords": [
            "entertainment", "celebrity", "celebrities", "movie", "film", 
            "cinema", "tv series", "television", "web series", "ott",
            "actor", "actress", "director", "producer", "music",
            "award", "awards", "festival", "cannes", "sundance",
            "billboard", "rolling stone", "people", "tmz",
            "music video", "concert", "tour", "album", "song"
        ],
        "priority": 8
    },
    "technology": {
        "keywords": [
            "technology", "tech", "gadget", "gadgets", "smartphone",
            "android", "ios", "iphone", "ipad", "macbook", "windows",
            "ai", "artificial intelligence", "machine learning", "ml",
            "computer", "laptop", "tablet", "wearable", "smartwatch",
            "internet", "5g", "6g", "wifi", "bluetooth",
            "software", "app", "application", "programming", "developer",
            "cybersecurity", "hacking", "privacy", "data",
            "techcrunch", "the verge", "ars technica", "engadget",
            "apple", "samsung", "google", "microsoft", "amazon", "meta",
            "tesla", "spacex", "nvidia", "intel", "amd"
        ],
        "priority": 9
    },
    "gaming": {
        "keywords": [
            "gaming", "game", "video game", "video games", "esports",
            "playstation", "ps5", "ps4", "xbox", "nintendo", "switch",
            "pc gaming", "steam", "epic games", "gog",
            "call of duty", "fortnite", "fifa", "gta", "grand theft auto",
            "minecraft", "roblox", "valorant", "league of legends", "lol",
            "dota", "counter-strike", "cs2", "apex legends", "pubg",
            "ign", "gamespot", "polygon", "kotaku", "pc gamer"
        ],
        "priority": 9
    },
    "business": {
        "keywords": [
            "business", "finance", "financial", "market", "stock", "stocks",
            "economy", "economic", "investment", "investor", "investing",
            "company", "corporate", "corporation", "startup", "entrepreneur",
            "money", "dollar", "rupee", "currency", "cryptocurrency", "bitcoin",
            "bank", "banking", "loan", "credit", "debt",
            "trade", "trading", "import", "export", "commerce",
            "wsj", "bloomberg", "cnbc", "reuters", "financial times",
            "forbes", "fortune", "business insider", "inc"
        ],
        "priority": 9
    },
    "sports": {
        "keywords": [
            "sports", "sport", "cricket", "football", "soccer", "basketball",
            "tennis", "badminton", "hockey", "golf", "formula 1", "f1",
            "olympics", "commonwealth", "asian games", "world cup",
            "ipl", "indian premier league", "premier league", "la liga",
            "nba", "nfl", "mlb", "nhl", "ufc", "mma",
            "virat kohli", "rohit sharma", "ms dhoni", "sachin",
            "messi", "ronaldo", "neymar", "mbappe",
            "espn", "bbc sport", "sky sports", "sports illustrated"
        ],
        "priority": 9
    },
    "trending": {
        "keywords": [
            "trending", "viral", "popular", "hot", "breaking",
            "news", "update", "latest", "new",
            "social media", "twitter", "x", "instagram", "facebook", "tiktok",
            "reddit", "buzzfeed", "gizmodo"
        ],
        "priority": 5
    }
}


# Verified RSS feeds with proper categorization
# Only using feeds that have been tested and verified to work
RSS_FEEDS = {
    "bollywood": [
        {
            "url": "https://www.pinkvilla.com/feed",
            "name": "Pinkvilla",
            "category": "bollywood",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.filmfare.com/rss/news.xml",
            "name": "Filmfare",
            "category": "bollywood",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://timesofindia.indiatimes.com/rssfeeds/1081479817.cms",
            "name": "Times of India Bollywood",
            "category": "bollywood",
            "language": "en",
            "enabled": True,
            "priority": 2
        },
    ],
    "hollywood": [
        {
            "url": "https://variety.com/feed/",
            "name": "Variety",
            "category": "hollywood",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://deadline.com/feed/",
            "name": "Deadline",
            "category": "hollywood",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.hollywoodreporter.com/feed/",
            "name": "Hollywood Reporter",
            "category": "hollywood",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ],
    "entertainment": [
        {
            "url": "https://www.billboard.com/feed/",
            "name": "Billboard",
            "category": "entertainment",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.rollingstone.com/feed/",
            "name": "Rolling Stone",
            "category": "entertainment",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ],
    "technology": [
        {
            "url": "https://feeds.feedburner.com/TechCrunch",
            "name": "TechCrunch",
            "category": "technology",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.theverge.com/rss/index.xml",
            "name": "The Verge",
            "category": "technology",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://arstechnica.com/gadgets/feed/",
            "name": "Ars Technica Gadgets",
            "category": "technology",
            "language": "en",
            "enabled": True,
            "priority": 2
        },
    ],
    "gaming": [
        {
            "url": "https://www.ign.com/feed",
            "name": "IGN",
            "category": "gaming",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.gamespot.com/feeds/news",
            "name": "GameSpot",
            "category": "gaming",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.polygon.com/rss/index.xml",
            "name": "Polygon",
            "category": "gaming",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ],
    "business": [
        {
            "url": "https://feeds.feedburner.com/ReutersBusinessNews",
            "name": "Reuters Business",
            "category": "business",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "name": "CNBC",
            "category": "business",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ],
    "sports": [
        {
            "url": "https://www.espn.com/espn/rss/news",
            "name": "ESPN",
            "category": "sports",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://feeds.bbci.co.uk/sport/rss.xml",
            "name": "BBC Sport",
            "category": "sports",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ],
    "trending": [
        {
            "url": "https://feeds.feedburner.com/buzzfeed-world",
            "name": "BuzzFeed World",
            "category": "trending",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
        {
            "url": "https://www.reddit.com/r/popular/.rss",
            "name": "Reddit Popular",
            "category": "trending",
            "language": "en",
            "enabled": True,
            "priority": 1
        },
    ]
}


def normalize_url(url: str) -> str:
    """Normalize URL by removing query parameters and fragments."""
    if not url or not isinstance(url, str):
        return ""
    
    parsed = urlparse(url)
    # Reconstruct without query and fragment
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    # Remove trailing slash
    return normalized.rstrip("/")


def generate_article_hash(title: str, url: str) -> str:
    """Generate a unique hash for an article based on normalized title and URL."""
    if not title or not url:
        return ""
    
    normalized_title = re.sub(r'[^\w\s]', '', title.lower()).strip()
    normalized_url = normalize_url(url)
    combined = f"{normalized_title}|{normalized_url}"
    return hashlib.sha256(combined.encode()).hexdigest()


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return "unknown"
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()
        return domain
    except Exception:
        return "unknown"


def clean_html_text(text: str) -> str:
    """Remove HTML tags and clean text."""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters that might cause issues
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    return text


def clean_text(text: str, max_length: int = 500) -> str:
    """Clean and normalize text, with optional length limit."""
    if not text:
        return ""
    
    text = clean_html_text(text)
    
    if max_length:
        text = text[:max_length]
    
    return text.strip()


def extract_image_from_feed(item) -> Optional[str]:
    """Extract image URL from RSS/Atom feed item."""
    # Try various image fields in RSS/Atom
    image_url = None
    
    # Check for media:content
    media_content = item.find("media:content", type=lambda x: x and "image" in x)
    if media_content and media_content.get("url"):
        image_url = media_content["url"]
    
    # Check for enclosure with image type
    if not image_url:
        enclosure = item.find("enclosure", type=lambda x: x and x.startswith("image/"))
        if enclosure and enclosure.get("url"):
            image_url = enclosure["url"]
    
    # Check for image tag in Atom
    if not image_url:
        image_tag = item.find("image")
        if image_tag and image_tag.get("href"):
            image_url = image_tag["href"]
    
    # Check for media:thumbnail
    if not image_url:
        media_thumbnail = item.find("media:thumbnail")
        if media_thumbnail and media_thumbnail.get("url"):
            image_url = media_thumbnail["url"]
    
    return image_url


def extract_image_from_html(html: str, base_url: str) -> Optional[str]:
    """Extract featured image URL from HTML content."""
    if not html:
        return None
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Try OpenGraph image
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            img_url = og_image["content"].strip()
            if img_url and img_url.startswith("http"):
                return img_url
        
        # Try Twitter card image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img_url = twitter_image["content"].strip()
            if img_url and img_url.startswith("http"):
                return img_url
        
        # Try schema.org image
        schema_image = soup.find("meta", attrs={"itemprop": "image"})
        if schema_image and schema_image.get("content"):
            img_url = schema_image["content"].strip()
            if img_url and img_url.startswith("http"):
                return img_url
        
        # Try first img tag with src
        img_tag = soup.find("img", src=True)
        if img_tag and img_tag["src"]:
            img_url = img_tag["src"].strip()
            if img_url.startswith("http"):
                return img_url
            # If relative URL, make it absolute
            if img_url.startswith("/"):
                parsed = urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{img_url}"
        
    except Exception as e:
        log(f"Error extracting image from HTML: {e}", "DEBUG")
    
    return None


def extract_summary_from_html(html: str) -> str:
    """Extract clean summary from HTML."""
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Try OpenGraph description
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            return clean_text(og_desc["content"])
        
        # Try Twitter description
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if twitter_desc and twitter_desc.get("content"):
            return clean_text(twitter_desc["content"])
        
        # Try standard description
        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            return clean_text(desc["content"])
        
        # Try to get first paragraph
        first_p = soup.find("p")
        if first_p:
            text = first_p.get_text()
            return clean_text(text, max_length=300)
        
    except Exception as e:
        log(f"Error extracting summary from HTML: {e}", "DEBUG")
    
    return ""


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse various date formats and return ISO format string."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try common formats
    formats = [
        # RFC 2822 variants
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
        # ISO 8601 variants
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        # Other common formats
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
    ]
    
    from datetime import datetime
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    
    # Try dateutil parser as fallback
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ImportError, ValueError):
        pass
    
    return None


def categorize_article(title: str, description: str, source_name: str, 
                        source_category: str, source_url: str) -> str:
    """Determine the best category for an article using multiple signals."""
    if not title:
        return source_category if source_category else "entertainment"
    
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    source_lower = (source_name or "").lower()
    
    # Score each category
    category_scores = {}
    
    for category, config in CATEGORY_KEYWORDS.items():
        score = 0
        
        # Check title for keywords
        for keyword in config["keywords"]:
            if keyword in title_lower:
                score += config["priority"] * 2
            if keyword in desc_lower:
                score += config["priority"]
        
        # Check source name
        for keyword in config["keywords"]:
            if keyword in source_lower:
                score += config["priority"] * 3
        
        # Check source URL
        source_domain = extract_domain(source_url)
        for keyword in config["keywords"]:
            if keyword in source_domain:
                score += config["priority"] * 2
        
        category_scores[category] = score
    
    # If we have a clear winner, use it
    if category_scores:
        max_score = max(category_scores.values())
        if max_score > 0:
            winners = [c for c, s in category_scores.items() if s == max_score]
            if len(winners) == 1:
                return winners[0]
            # If tie, prefer source category
            if source_category in winners:
                return source_category
            return winners[0]
    
    # Use source category if available
    if source_category:
        return source_category
    
    # Default to entertainment
    return "entertainment"


def fetch_with_retry(url: str, max_retries: int = 3, timeout: float = 30.0) -> Optional[str]:
    """Fetch URL with retry logic."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/xml, application/rss+xml, text/xml, text/html",
        "Accept-Encoding": "gzip, deflate"
    }
    
    for attempt in range(max_retries):
        try:
            http_timeout = httpx.Timeout(timeout, connect=10.0)
            with httpx.Client(timeout=http_timeout, headers=headers) as client:
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 503, 502] and attempt < max_retries - 1:
                # Rate limited or server error, wait and retry
                import time
                wait_time = (attempt + 1) * 5
                log(f"Rate limited or server error for {url}, retrying in {wait_time}s...", "WARNING")
                time.sleep(wait_time)
                continue
            else:
                log(f"HTTP error fetching {url}: {e}", "ERROR")
                return None
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2
                log(f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}", "WARNING")
                time.sleep(wait_time)
                continue
            else:
                log(f"Failed to fetch {url} after {max_retries} attempts: {e}", "ERROR")
                return None
    
    return None


def parse_rss_feed(xml_content: str, feed_url: str) -> List[Dict[str, Any]]:
    """Parse RSS or Atom feed and extract articles."""
    articles = []
    
    if not xml_content:
        return articles
    
    try:
        # Try to parse as XML
        try:
            soup = BeautifulSoup(xml_content, "xml")
        except Exception:
            try:
                soup = BeautifulSoup(xml_content, features="lxml-xml")
            except Exception:
                soup = BeautifulSoup(xml_content, "html.parser")
        
        # Parse RSS 2.0
        items = soup.find_all("item")
        if not items:
            # Try Atom
            items = soup.find_all("entry")
        
        if not items:
            # Try other namespaces
            items = soup.find_all("item", recursive=True)
        
        for item in items:
            try:
                article = parse_rss_item(item, feed_url)
                if article:
                    articles.append(article)
            except Exception as e:
                log(f"Error parsing item: {e}", "DEBUG")
                continue
                
    except Exception as e:
        log(f"Error parsing RSS feed: {e}", "ERROR")
    
    return articles


def parse_rss_item(item, feed_url: str) -> Optional[Dict[str, Any]]:
    """Parse a single RSS/Atom item."""
    try:
        # Extract link
        link_tag = item.find("link")
        url = ""
        
        if link_tag:
            if link_tag.name == "link":
                # RSS format - can be text or href attribute
                if link_tag.text and link_tag.text.strip():
                    url = link_tag.text.strip()
                elif link_tag.get("href"):
                    url = link_tag.get("href").strip()
                elif link_tag.get("url"):
                    url = link_tag.get("url").strip()
            else:
                # Atom format
                url = link_tag.get("href", "").strip()
        
        # If still no URL, try other methods
        if not url:
            link_tags = item.find_all("link")
            for lt in link_tags:
                if lt.get("href"):
                    url = lt.get("href").strip()
                    break
        
        if not url or url.startswith("mailto:") or url.startswith("tel:"):
            return None
        
        # Extract title
        title_tag = item.find("title")
        title = title_tag.text.strip() if title_tag and title_tag.text else "Untitled"
        
        # Extract description/summary
        desc_tag = item.find("description") or item.find("summary") or item.find("content")
        description = desc_tag.text.strip() if desc_tag and desc_tag.text else ""
        
        # Try content:encoded for full content
        if not description:
            content_encoded = item.find("content:encoded")
            if content_encoded and content_encoded.text:
                description = content_encoded.text.strip()
        
        # Extract date
        date_str = None
        date_tag = item.find("pubDate") or item.find("published") or item.find("updated") or item.find("dc:date")
        if date_tag and date_tag.text:
            date_str = date_tag.text.strip()
        elif date_tag and date_tag.get("content"):
            date_str = date_tag.get("content").strip()
        
        # Extract image
        image_url = extract_image_from_feed(item)
        
        # Extract author
        author = None
        author_tag = item.find("author") or item.find("dc:creator") or item.find("creator")
        if author_tag:
            if author_tag.text:
                author = author_tag.text.strip()
            elif author_tag.get("name"):
                author = author_tag.get("name").strip()
            elif author_tag.get("email"):
                author = author_tag.get("email").strip()
        
        # Extract categories/tags
        categories = []
        cat_tags = item.find_all("category")
        for cat in cat_tags:
            if cat.text:
                categories.append(cat.text.strip())
            elif cat.get("term"):
                categories.append(cat.get("term").strip())
            elif cat.get("label"):
                categories.append(cat.get("label").strip())
        
        return {
            "url": url,
            "title": title,
            "description": description,
            "date": date_str,
            "image_url": image_url,
            "author": author,
            "categories": categories,
            "feed_url": feed_url
        }
        
    except Exception as e:
        log(f"Error parsing RSS item: {e}", "DEBUG")
        return None


def normalize_article(article: Dict[str, Any], source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize and validate an article."""
    try:
        # Required fields
        url = article.get("url", "")
        title = article.get("title", "")
        
        if not url or not title:
            return None
        
        # Normalize URL
        normalized_url = normalize_url(url)
        
        # Generate unique hash
        article_hash = generate_article_hash(title, normalized_url)
        
        # Check for duplicates
        if article_hash in seen_hashes:
            stats["duplicates"] += 1
            return None
        
        seen_hashes.add(article_hash)
        
        # Parse date
        date_str = article.get("date")
        published_at = parse_date(date_str) if date_str else datetime.now(timezone.utc).isoformat()
        
        # Get source info
        source_name = source_config.get("name", "unknown")
        source_category = source_config.get("category", "entertainment")
        source_url = source_config.get("url", "")
        
        # Determine category
        description = article.get("description", "")
        category = categorize_article(
            title, description, source_name, source_category, source_url
        )
        
        # Clean text
        clean_title = clean_text(title)
        clean_desc = clean_text(description, max_length=500)
        
        # Get image URL
        image_url = article.get("image_url")
        if image_url:
            # Normalize image URL
            image_url = normalize_url(image_url)
            # Validate image URL
            if not image_url.startswith("http"):
                image_url = None
        
        # Get author
        author = article.get("author")
        if author:
            author = clean_text(author)
        
        # Get tags
        categories = article.get("categories", [])
        if categories:
            categories = [clean_text(c) for c in categories if c]
        
        # Create normalized article
        normalized = {
            "id": article_hash,
            "title": clean_title,
            "summary": clean_desc,
            "category": category,
            "source": source_name,
            "url": normalized_url,
            "published_at": published_at,
            "image_url": image_url,
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
            "thin": bool(len(clean_title) < 20 or len(clean_desc.strip()) < 40)
        }
        
        if author:
            normalized["author"] = author
        
        if categories:
            normalized["tags"] = categories
        
        # Validate required fields
        if not normalized["title"] or not normalized["url"]:
            return None
        
        return normalized
        
    except Exception as e:
        log(f"Error normalizing article: {e}", "ERROR")
        return None


def load_removed_articles() -> Set[str]:
    """Load hashes of admin-removed (unpublished/deleted) articles.

    These tombstones block re-import of the same article from RSS on the
    next scheduled sync, so a removed article can never reappear.
    """
    removed = set()
    if not os.path.exists(REMOVED_ARTICLES_FILE):
        return removed
    try:
        with open(REMOVED_ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for article_id, record in (data.get("articles") or {}).items():
            # Restore action removes the tombstone; everything else blocks.
            if isinstance(record, dict) and record.get("action") not in (None, "restore"):
                removed.add(article_id)
    except Exception as e:
        log(f"Error loading removed articles: {e}", "ERROR")
    return removed


def load_existing_articles() -> List[Dict[str, Any]]:
    """Load existing articles from JSON file."""
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    
    if os.path.exists(all_articles_file):
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                existing_articles = json.load(f)
                # Load hashes
                for article in existing_articles:
                    seen_hashes.add(article.get("id", ""))
                return existing_articles
        except Exception as e:
            log(f"Error loading existing articles: {e}", "ERROR")
    
    return []


def save_articles(new_articles: List[Dict[str, Any]], existing_articles: List[Dict[str, Any]]) -> None:
    """Save articles to JSON files with proper limits."""
    if not new_articles:
        return
    
    # Update stats
    stats["new_articles"] += len(new_articles)
    
    # Combine existing and new
    all_articles = new_articles + existing_articles
    
    # Remove duplicates by ID (keep newest first)
    seen_ids = set()
    unique_articles = []
    for article in all_articles:
        article_id = article.get("id", "")
        if article_id not in seen_ids:
            seen_ids.add(article_id)
            unique_articles.append(article)
    
    # Sort by published_at (newest first)
    unique_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    
    # Apply limits
    if len(unique_articles) > MAX_TOTAL_ARTICLES:
        unique_articles = unique_articles[:MAX_TOTAL_ARTICLES]
    
    # Save all articles
    try:
        all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
        with open(all_articles_file, "w", encoding="utf-8") as f:
            json.dump(unique_articles, f, indent=2, ensure_ascii=False)
        log(f"Saved {len(unique_articles)} articles to {all_articles_file}", "INFO")
    except Exception as e:
        log(f"Error saving all articles: {e}", "ERROR")
        return
    
    # Save by category with limits
    categories = set(a["category"] for a in unique_articles)
    for category in categories:
        category_articles = [a for a in unique_articles if a["category"] == category]
        category_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        
        # Apply category limit
        if len(category_articles) > MAX_ARTICLES_PER_CATEGORY:
            category_articles = category_articles[:MAX_ARTICLES_PER_CATEGORY]
        
        category_file = os.path.join(NEWS_JSON_DIR, f"{category}.json")
        try:
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump(category_articles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving {category} articles: {e}", "ERROR")
    
    # Save latest (last 100 articles)
    latest_file = os.path.join(NEWS_JSON_DIR, "latest.json")
    latest_articles = unique_articles[:100]
    
    try:
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(latest_articles, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error saving latest articles: {e}", "ERROR")
    
    # Save trending (most recent 50)
    trending_file = os.path.join(NEWS_JSON_DIR, "trending.json")
    trending_articles = unique_articles[:50]
    
    try:
        with open(trending_file, "w", encoding="utf-8") as f:
            json.dump(trending_articles, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error saving trending articles: {e}", "ERROR")
    
    # Save stats
    stats_file = os.path.join(DATA_DIR, "stats.json")
    try:
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error saving stats: {e}", "ERROR")
    
    # Save source failures
    failures_file = os.path.join(DATA_DIR, "failed_sources.json")
    try:
        with open(failures_file, "w", encoding="utf-8") as f:
            json.dump({
                "failed_sources": failed_sources,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_failed": len(failed_sources)
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error saving failed sources: {e}", "ERROR")


def print_summary():
    """Print collection summary."""
    log("\n" + "="*50, "INFO")
    log("PIKANEWS COLLECTION SUMMARY", "INFO")
    log("="*50, "INFO")
    log(f"Timestamp: {stats.get('timestamp', 'N/A')}", "INFO")
    log(f"Total articles fetched: {stats.get('total_fetched', 0)}", "INFO")
    log(f"New articles saved: {stats.get('new_articles', 0)}", "INFO")
    log(f"Duplicates skipped: {stats.get('duplicates', 0)}", "INFO")
    log(f"Errors: {stats.get('errors', 0)}", "INFO")
    log(f"Failed sources: {len(failed_sources)}", "INFO")
    
    if failed_sources:
        log("\nFailed sources:", "WARNING")
        for fs in failed_sources[:10]:  # Show first 10
            log(f"  - {fs.get('name', 'Unknown')}: {fs.get('url', 'N/A')}", "WARNING")
        if len(failed_sources) > 10:
            log(f"  ... and {len(failed_sources) - 10} more", "WARNING")
    
    log(f"\nArticles by source:", "INFO")
    by_source = stats.get("by_source", {})
    for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
        log(f"  {source}: {count}", "INFO")
    
    log(f"\nArticles by category:", "INFO")
    by_category = stats.get("by_category", {})
    for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
        log(f"  {category}: {count}", "INFO")
    
    log("="*50, "INFO")


def main():
    """Main entry point."""
    global seen_hashes, failed_sources, stats
    
    log("Starting PikaNews automatic news collection v2.0", "INFO")
    
    # Initialize state
    seen_hashes = set()
    failed_sources = []
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_fetched": 0,
        "new_articles": 0,
        "duplicates": 0,
        "errors": 0,
        "by_source": {},
        "by_category": {}
    }
    
    # Load existing articles and hashes
    existing_articles = load_existing_articles()
    removed_hashes = load_removed_articles()
    if removed_hashes:
        seen_hashes.update(removed_hashes)
        log(f"Loaded {len(removed_hashes)} removed-article tombstones (re-import blocked)", "INFO")
    log(f"Loaded {len(existing_articles)} existing articles", "INFO")
    log(f"Loaded {len(seen_hashes)} existing article hashes", "INFO")
    
    # Fetch from all RSS feeds
    all_raw_articles = []
    
    for category, feeds in RSS_FEEDS.items():
        log(f"\nProcessing {category} feeds...", "INFO")
        
        for feed_info in feeds:
            if not feed_info.get("enabled", True):
                log(f"Skipping disabled feed: {feed_info.get('name', 'Unknown')}", "DEBUG")
                continue
            
            url = feed_info["url"]
            source_name = feed_info["name"]
            source_category = feed_info.get("category", category)
            
            source_config = {
                "name": source_name,
                "category": source_category,
                "url": url
            }
            
            try:
                log(f"Fetching from {source_name} ({url})...", "INFO")
                
                # Fetch feed with retry
                xml_content = fetch_with_retry(url)
                
                if not xml_content:
                    log(f"  Failed to fetch feed from {source_name}", "WARNING")
                    failed_sources.append({
                        "name": source_name,
                        "url": url,
                        "category": category,
                        "error": "Failed to fetch"
                    })
                    stats["errors"] += 1
                    continue
                
                # Parse feed
                articles = parse_rss_feed(xml_content, url)
                
                if articles:
                    stats["total_fetched"] += len(articles)
                    stats["by_source"][source_name] = stats["by_source"].get(source_name, 0) + len(articles)
                    all_raw_articles.extend([(a, source_config) for a in articles])
                    log(f"  Found {len(articles)} articles from {source_name}", "INFO")
                else:
                    log(f"  No articles found from {source_name}", "DEBUG")
                    
            except Exception as e:
                log(f"Error fetching from {source_name}: {e}", "ERROR")
                failed_sources.append({
                    "name": source_name,
                    "url": url,
                    "category": category,
                    "error": str(e)
                })
                stats["errors"] += 1
    
    log(f"\nTotal raw articles fetched: {len(all_raw_articles)}", "INFO")
    
    # Normalize all articles
    normalized_articles = []
    for raw_article, source_config in all_raw_articles:
        normalized = normalize_article(raw_article, source_config)
        if normalized:
            normalized_articles.append(normalized)
            category = normalized.get("category", "unknown")
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
    
    log(f"Normalized articles: {len(normalized_articles)}", "INFO")
    log(f"Duplicates skipped: {stats['duplicates']}", "INFO")
    
    # Save articles
    save_articles(normalized_articles, existing_articles)
    
    # Print summary
    print_summary()
    
    return stats


if __name__ == "__main__":
    main()


