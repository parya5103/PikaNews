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
import ipaddress
import socket
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, quote
import httpx
from bs4 import BeautifulSoup

try:
    from scripts.classification_rules import classify_article
except ImportError:  # direct script execution from the scripts directory
    from classification_rules import classify_article

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
master_feed_needs_repair = False
failed_sources: List[Dict[str, str]] = []
stats: Dict[str, Any] = {}

# Maximum articles to keep per category to prevent bloating
MAX_ARTICLES_PER_CATEGORY = 500
MAX_TOTAL_ARTICLES = 2000

# Automatic old-news retention policy: an article is removed from ALL
# public PikaNews content once its ORIGINAL published_at is more than
# NEWS_RETENTION_DAYS days in the past (timezone-aware UTC comparison).
# Count limits above stay as secondary safeguards. Articles with a
# missing or invalid published_at are NEVER auto-expired on a guessed
# date - they are logged for review instead.
NEWS_RETENTION_DAYS = 30


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
            "enabled": False,
            "priority": 1
        },
        {
            "url": "https://timesofindia.indiatimes.com/rssfeeds/1081479817.cms",
            "name": "Times of India Bollywood",
            "category": "bollywood",
            "language": "en",
            "enabled": False,
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
            "enabled": False,
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
            "enabled": False,
            "priority": 1
        },
    ],
    "world": [
        {
            "url": "https://www.ungeneva.org/news-media/press-items-list/rss.xml",
            "name": "UN Geneva",
            "category": "world",
            "language": "en",
            "region": "global",
            "enabled": True,
            "priority": 1,
            "image_policy": "none",
            "reuse_policy": "The official UN Geneva RSS page permits displaying its feeds on another website; show only a short attributed excerpt and link to the original."
        },
        {
            "url": "https://ec.europa.eu/eurostat/en/search?p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_state=maximized&p_p_mode=view&p_p_resource_id=atom&_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_PREREL",
            "name": "Eurostat Press Releases",
            "category": "world",
            "language": "en",
            "region": "europe",
            "enabled": True,
            "priority": 1,
            "image_policy": "none",
            "reuse_policy": "EU-owned Eurostat editorial content is reusable under CC BY 4.0 with attribution and indication of changes; check item-level notices for third-party exceptions."
        },
        {
            "url": "https://ec.europa.eu/eurostat/en/search?p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_state=maximized&p_p_mode=view&p_p_resource_id=atom&_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_EURNEW",
            "name": "Eurostat News",
            "category": "world",
            "language": "en",
            "region": "europe",
            "enabled": True,
            "priority": 1,
            "image_policy": "none",
            "reuse_policy": "EU-owned Eurostat editorial content is reusable under CC BY 4.0 with attribution and indication of changes; check item-level notices for third-party exceptions."
        }
    ],
    "science": [
        {
            "url": "https://www.nasa.gov/news-release/feed/",
            "name": "NASA News Releases",
            "category": "science",
            "language": "en",
            "region": "us",
            "enabled": True,
            "priority": 1,
            "image_policy": "none",
            "reuse_policy": "Use factual headlines and short attributed excerpts only; do not reuse feed images or NASA identifiers."
        },
        {
            "url": "https://www.climate.gov/feeds/news-features/highlights.rss",
            "name": "NOAA Climate.gov",
            "category": "science",
            "language": "en",
            "region": "global",
            "enabled": True,
            "priority": 1,
            "image_policy": "none",
            "reuse_policy": "NOAA Climate.gov permits reuse of content credited to NOAA Climate.gov with attribution; exclude third-party credited material and images, and do not imply NOAA endorsement."
        }
    ]
}


def normalize_url(url: str) -> str:
    """Normalize a publisher URL, accepting only absolute HTTP(S) URLs."""
    if not url or not isinstance(url, str):
        return ""

    try:
        parsed = urlparse(url.strip())
        # Publisher URLs are rendered as clickable links and included in
        # structured data. Reject script/data schemes, relative URLs, and
        # credential-bearing URLs before they enter persistent article data.
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return ""
        if parsed.username is not None or parsed.password is not None:
            return ""
        parsed.port  # Force validation of malformed ports.
    except (TypeError, ValueError):
        return ""

    # Eurostat's official Atom feed links to product pages whose unique
    # identifier is carried in the "code" query parameter. Preserve only
    # that validated parameter; tracking queries remain stripped everywhere.
    query = ""
    if parsed.hostname.casefold() == "ec.europa.eu" and parsed.path.rstrip("/") == "/eurostat/product":
        codes = parse_qs(parsed.query, keep_blank_values=False).get("code", [])
        if len(codes) == 1 and re.fullmatch(r"[A-Za-z0-9-]{1,80}", codes[0]):
            query = "?code=" + quote(codes[0], safe="-")

    normalized = f"{parsed.scheme.lower()}://{parsed.netloc}{parsed.path}"
    return normalized.rstrip("/") + query


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


def normalize_image_url(image_url: Optional[str], base_url: str = "") -> Optional[str]:
    """Resolve image URLs without stripping signed/CDN query parameters."""
    if not image_url or not isinstance(image_url, str):
        return None
    candidate = urljoin(base_url, image_url.strip())
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        return None
    return candidate


def extract_image_from_feed(item) -> Optional[str]:
    """Extract image URLs from RSS/Atom media tags and embedded HTML."""
    candidates = []
    for tag in item.find_all(True):
        local_name = (tag.name or "").lower().split(":")[-1]
        media_type = (tag.get("type") or tag.get("medium") or "").lower()
        if local_name in ("content", "thumbnail", "image", "enclosure"):
            if local_name != "content" or "image" in media_type or tag.get("medium") == "image":
                candidates.extend([tag.get("url"), tag.get("href")])
    for tag in item.find_all(["description", "summary", "content", "encoded"]):
        fragment = BeautifulSoup(tag.get_text() or str(tag), "html.parser")
        for img in fragment.find_all("img"):
            candidates.extend([img.get("src"), img.get("data-src"), img.get("data-original"), img.get("data-lazy-src")])
            srcset = img.get("srcset") or img.get("data-srcset") or ""
            candidates.extend(part.strip().split()[0] for part in srcset.split(",") if part.strip())
    for candidate in candidates:
        if candidate:
            parsed = urlparse(str(candidate).strip())
            if parsed.scheme in ("http", "https") and parsed.netloc:
                return str(candidate).strip()
    return None


def extract_image_from_html(html: str, base_url: str) -> Optional[str]:
    """Extract publisher featured images, including relative and lazy-loaded URLs."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        for attrs in ({"property": "og:image"}, {"property": "og:image:secure_url"},
                      {"name": "twitter:image"}, {"name": "twitter:image:src"},
                      {"itemprop": "image"}):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                resolved = normalize_image_url(tag["content"], base_url)
                if resolved:
                    return resolved
        for img in soup.find_all("img"):
            for attr in ("data-src", "data-lazy-src", "data-original", "src"):
                resolved = normalize_image_url(img.get(attr), base_url)
                if resolved:
                    try:
                        if int(img.get("width", 999)) <= 2 or int(img.get("height", 999)) <= 2:
                            continue
                    except (TypeError, ValueError):
                        pass
                    return resolved
            srcset = img.get("data-srcset") or img.get("srcset") or ""
            for part in srcset.split(","):
                if part.strip():
                    resolved = normalize_image_url(part.strip().split()[0], base_url)
                    if resolved:
                        return resolved
    except Exception as e:
        log(f"Error extracting image from HTML: {e}", "DEBUG")
    return None


def is_public_http_url(url: str) -> bool:
    """Allow only HTTP(S) URLs resolving exclusively to globally routable IPs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        if not addresses:
            return False
        return all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, TypeError, ValueError):
        return False


def fetch_article_image(article_url: str) -> Optional[str]:
    """Best-effort image lookup with SSRF-safe URL and redirect validation."""
    try:
        candidate = normalize_url(article_url)
        if not candidate or not is_public_http_url(candidate):
            return None
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        # Never let HTTPX follow redirects automatically: every redirect target
        # must pass the same public-address check before another request is made.
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0), headers=headers,
                          follow_redirects=False) as client:
            for _ in range(4):
                response = client.get(candidate)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        return None
                    candidate = urljoin(candidate, location)
                    if not is_public_http_url(candidate):
                        return None
                    continue
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    return None
                return extract_image_from_html(response.text, str(response.url))
            return None
    except Exception as e:
        log(f"Image enrichment skipped for {article_url}: {e}", "DEBUG")
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
    """Classify by article text; publisher identity is not a topic label."""
    return classify_article(
        title,
        description,
        source_name=source_name,
        source_category=source_category,
        source_url=source_url,
    )

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
        
        # Preserve publisher dates exactly: collection time is NOT the
        # publication time. Guessing "now" here makes old/undated stories
        # look fresh and defeats the retention policy. Unknown dates stay
        # null, are counted by expire_old_articles(), and remain reviewable.
        date_str = article.get("date")
        published_at = parse_date(date_str) if date_str else None
        date_unverified = published_at is None
        
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
        # Preserve signed/CDN query parameters; image URLs are not article URLs.
        image_url = (
            None if source_config.get("image_policy") == "none"
            else normalize_image_url(article.get("image_url"), normalized_url)
        )
        
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
            "date_unverified": date_unverified,
            "image_url": image_url,
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
            "thin": bool(len(clean_title) < 20 or len(clean_desc.strip()) < 40)
        }
        
        if source_config.get("region"):
            normalized["region"] = source_config["region"]
        if source_config.get("image_policy") == "none":
            normalized["image_policy"] = "none"

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


def _load_removed_articles_file() -> Dict[str, Any]:
    """Load the full tombstone registry (data/removed_articles.json).

    Structure: {"articles": {article_id: {...}}}. Missing or corrupt
    files degrade to an empty registry - existing tombstones are never
    destroyed by a read error.
    """
    if not os.path.exists(REMOVED_ARTICLES_FILE):
        return {"articles": {}}
    try:
        with open(REMOVED_ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("articles"), dict):
            return {"articles": {}}
        return data
    except Exception as e:
        log(f"Error loading removed articles: {e}", "ERROR")
        return {"articles": {}}


def parse_published_datetime(value: Any) -> Optional[datetime]:
    """Timezone-aware parse of an article's published_at value.

    Returns an aware datetime (UTC assumed for naive values) or None
    when the date is missing/unparseable. None must NEVER be guessed
    into an expiry decision.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        dt = None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        if dt is None:
            parsed_iso = parse_date(text)
            if parsed_iso:
                try:
                    dt = datetime.fromisoformat(parsed_iso.replace("Z", "+00:00"))
                except ValueError:
                    return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def expire_old_articles(
    existing_articles: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, Set[str]]:
    """Apply the NEWS_RETENTION_DAYS published-date expiry policy.

    Splits articles into (remaining, expired, no_valid_date_count,
    affected_categories). An article expires only when its ORIGINAL
    published_at parses to a timezone-aware datetime that is at or
    older than `now - NEWS_RETENTION_DAYS`. Articles without a usable
    publication date are kept and counted - never guessed away.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=NEWS_RETENTION_DAYS)

    remaining: List[Dict[str, Any]] = []
    expired: List[Dict[str, Any]] = []
    no_valid_date = 0
    affected_categories: Set[str] = set()

    for article in existing_articles:
        published = parse_published_datetime(article.get("published_at"))
        if published is None:
            no_valid_date += 1
            remaining.append(article)
        elif published <= cutoff:
            expired.append(article)
            if article.get("category"):
                affected_categories.add(str(article["category"]))
        else:
            remaining.append(article)

    return remaining, expired, no_valid_date, affected_categories


def add_expiry_tombstones(expired_articles: List[Dict[str, Any]]) -> int:
    """Write lightweight auto-expire tombstones for expired articles.

    Tombstones hold NO full article content (title/source/url/id only)
    and block re-import of the same story when its RSS publisher sends
    it again. Existing tombstones (manual unpublish/delete/restore) are
    preserved untouched.
    """
    if not expired_articles:
        return 0
    data = _load_removed_articles_file()
    added = 0
    for article in expired_articles:
        article_id = article.get("id")
        if not article_id or article_id in data["articles"]:
            continue
        data["articles"][article_id] = {
            "action": "auto-expire",
            "reason": f"older than {NEWS_RETENTION_DAYS} days (automatic news retention policy)",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "article_id": article_id,
        }
        added += 1
    if added:
        os.makedirs(os.path.dirname(REMOVED_ARTICLES_FILE), exist_ok=True)
        with open(REMOVED_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return added


def load_removed_articles() -> Set[str]:
    """Load hashes of admin-removed (unpublished/deleted) articles.

    These tombstones block re-import of the same article from RSS on the
    next scheduled sync, so a removed article can never reappear.
    Auto-expire tombstones block re-import the same way.
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


# Times of India RSS Terms of Use permit only personal, non-commercial use
# and expressly forbid commercial display/aggregation without written consent.
# Remove its already-collected feed records as well as disabling future fetches.
RESTRICTED_COMMERCIAL_SOURCE_ALIASES = {
    "times of india",
    "times of india bollywood",
    "toi",
}


def _is_restricted_commercial_source(article: Dict[str, Any]) -> bool:
    source = str(article.get("source") or "").strip().casefold()
    return source in RESTRICTED_COMMERCIAL_SOURCE_ALIASES


def load_existing_articles() -> List[Dict[str, Any]]:
    """Load the master feed, recovering from category/latest feeds if it is empty or corrupt."""
    global master_feed_needs_repair
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    master_feed_needs_repair = False

    if os.path.exists(all_articles_file):
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                existing_articles = json.load(f)
            if isinstance(existing_articles, list) and existing_articles:
                permitted_articles = [
                    article for article in existing_articles
                    if isinstance(article, dict) and not _is_restricted_commercial_source(article)
                ]
                removed_count = len(existing_articles) - len(permitted_articles)
                if removed_count:
                    master_feed_needs_repair = True
                    log(
                        f"Removed {removed_count} previously collected Times of India article(s) "
                        "because the publisher's RSS terms prohibit commercial aggregation.",
                        "WARNING",
                    )
                for article in permitted_articles:
                    if article.get("id"):
                        seen_hashes.add(article["id"])
                return permitted_articles
            master_feed_needs_repair = True
            log("Master article feed is empty or invalid; recovering from available feed files.", "WARNING")
        except Exception as e:
            master_feed_needs_repair = True
            log(f"Error loading master article feed; recovering from available feed files: {e}", "WARNING")
    else:
        master_feed_needs_repair = True

    recovered_by_id = {}
    if os.path.isdir(NEWS_JSON_DIR):
        for filename in sorted(os.listdir(NEWS_JSON_DIR)):
            if not filename.endswith(".json") or filename == "all_articles.json":
                continue
            feed_path = os.path.join(NEWS_JSON_DIR, filename)
            try:
                with open(feed_path, "r", encoding="utf-8") as f:
                    feed_articles = json.load(f)
                if not isinstance(feed_articles, list):
                    continue
                for article in feed_articles:
                    if (not isinstance(article, dict) or not article.get("id")
                            or _is_restricted_commercial_source(article)):
                        continue
                    recovered_by_id.setdefault(article["id"], article)
            except (OSError, ValueError) as e:
                log(f"Skipping unreadable recovery feed {filename}: {e}", "WARNING")

    recovered = list(recovered_by_id.values())
    recovered.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    for article in recovered:
        seen_hashes.add(article["id"])
    log(f"Recovered {len(recovered)} articles from secondary feed files.", "INFO")
    return recovered


def save_articles(new_articles: List[Dict[str, Any]], existing_articles: List[Dict[str, Any]],
                  always_write: bool = False,
                  affected_categories: Optional[Set[str]] = None) -> None:
    """Save articles to JSON files with proper limits.

    When `always_write` is true the feeds are rewritten even with zero
    new articles, so the expiry cleanup path can regenerate every output
    on a no-new-articles collector run. `affected_categories` ensures a
    category emptied entirely by expiry gets its stale JSON rewritten
    (as an empty list) instead of keeping expired stories on disk.
    """
    global master_feed_needs_repair
    if not new_articles and not always_write and not master_feed_needs_repair:
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
    unique_articles.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    
    # Apply limits
    if len(unique_articles) > MAX_TOTAL_ARTICLES:
        unique_articles = unique_articles[:MAX_TOTAL_ARTICLES]
    
    # Save all articles
    try:
        all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
        with open(all_articles_file, "w", encoding="utf-8") as f:
            json.dump(unique_articles, f, indent=2, ensure_ascii=False)
        master_feed_needs_repair = False
        log(f"Saved {len(unique_articles)} articles to {all_articles_file}", "INFO")
    except Exception as e:
        log(f"Error saving all articles: {e}", "ERROR")
        return
    
    # Save by category with limits
    categories = set(a["category"] for a in unique_articles)
    for category in categories:
        category_articles = [a for a in unique_articles if a["category"] == category]
        category_articles.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        
        # Apply category limit
        if len(category_articles) > MAX_ARTICLES_PER_CATEGORY:
            category_articles = category_articles[:MAX_ARTICLES_PER_CATEGORY]
        
        category_file = os.path.join(NEWS_JSON_DIR, f"{category}.json")
        try:
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump(category_articles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving {category} articles: {e}", "ERROR")

    # A category emptied entirely by expiry must not keep a stale JSON
    # feed of expired stories on disk: rewrite it as an empty list.
    for category in (affected_categories or set()):
        if not category:
            continue
        category_name = str(category).lower()
        if category_name in {str(c).lower() for c in categories}:
            continue  # already rewritten above
        category_file = os.path.join(NEWS_JSON_DIR, f"{category_name}.json")
        try:
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)
            log(f"Category '{category}' emptied by expiry - feed rewritten as empty", "INFO")
        except Exception as e:
            log(f"Error clearing {category} articles: {e}", "ERROR")
    
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
    log(f"Expired articles removed (>{NEWS_RETENTION_DAYS} days old): {stats.get('expired_articles', 0)}", "INFO")
    if stats.get("articles_without_valid_date"):
        log(f"Articles kept without a valid published_at (review): "
            f"{stats.get('articles_without_valid_date', 0)}", "WARNING")
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
        "expired_articles": 0,
        "articles_without_valid_date": 0,
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

    # ---- Automatic old-news expiry (runs EVERY collector run, even
    # when zero new articles are fetched) -------------------------------
    existing_articles, expired_articles, no_valid_date, expiry_categories = expire_old_articles(existing_articles)
    stats["expired_articles"] = len(expired_articles)
    stats["articles_without_valid_date"] = no_valid_date
    if no_valid_date:
        log(f"{no_valid_date} existing articles have a missing/invalid published_at - "
            f"NOT auto-expired (no guessed dates); logged for review", "WARNING")
    if expired_articles:
        tombstoned = add_expiry_tombstones(expired_articles)
        # Block same-run re-import if an RSS feed sends the story again.
        seen_hashes.update(str(a.get("id", "")) for a in expired_articles if a.get("id"))
        log(f"EXPIRY: removed {len(expired_articles)} articles older than "
            f"{NEWS_RETENTION_DAYS} days (published_at based, UTC)", "INFO")
        log(f"EXPIRY: affected categories: {', '.join(sorted(expiry_categories)) or 'none'}", "INFO")
        log(f"EXPIRY: {tombstoned} tombstone(s) added - re-import of expired stories is blocked", "INFO")
    else:
        log(f"EXPIRY: no articles older than {NEWS_RETENTION_DAYS} days found", "INFO")
    
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
                "url": url,
                "region": feed_info.get("region", ""),
                "image_policy": feed_info.get("image_policy", "allow"),
                "reuse_policy": feed_info.get("reuse_policy", "")
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

    # Repair missing thumbnails on new and existing stories, with bounded network work.
    image_candidates = [
        a for a in normalized_articles + existing_articles
        if not a.get("image_url") and a.get("image_policy") != "none"
    ]
    image_candidates.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    enriched = 0
    for article in image_candidates[:15]:
        image_url = fetch_article_image(article.get("url", ""))
        if image_url:
            article["image_url"] = image_url
            enriched += 1
    if enriched:
        log(f"Recovered {enriched} missing article thumbnails", "INFO")

    # Save articles (always rewrite feeds when expiry removed something,
    # so a zero-new-articles run still regenerates every public output)
    save_articles(
        normalized_articles,
        existing_articles,
        always_write=bool(expired_articles or enriched),
        affected_categories=expiry_categories,
    )
    
    # Print summary
    print_summary()
    
    return stats


if __name__ == "__main__":
    main()



