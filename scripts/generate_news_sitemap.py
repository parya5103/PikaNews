#!/usr/bin/env python3
"""
PikaNews Google News Sitemap Generator.

Emits a valid Google News sitemap (news namespace) at
frontend/news-sitemap.xml containing only eligible articles:
  - published within the last 48 hours (Google News freshness window)
  - having a generated static page at frontend/news/<slug>/index.html
  - not thin and not admin-removed (tombstoned)

The file is regenerated on every collector run, right after
scripts/generate_article_pages.py, so it never lists pages that do not
exist. robots.txt references it alongside the regular sitemap.
"""

import json
import os
from datetime import datetime, timezone

try:
    from scripts.generate_article_pages import (
        NEWS_DIR, article_slug, is_thin, load_removed_hashes,
    )
except ImportError:
    from generate_article_pages import (
        NEWS_DIR, article_slug, is_thin, load_removed_hashes,
    )

# Configuration
BASE_URL = "https://gogocompany.in/pikanews/"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
NEWS_SITEMAP_PATH = os.path.join(FRONTEND_DIR, "news-sitemap.xml")
NEWS_JSON_DIR = os.path.join(REPO_ROOT, "news_json")

MAX_URLS = 1000          # Google sitemap limit
MAX_AGE_HOURS = 48       # Google News recency expectation


def escape_xml(text):
    """Escape XML special characters."""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&apos;")
            .replace('"', "&quot;"))


def parse_iso(value):
    if not value:
        return None
    try:
        v = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def generate_news_sitemap():
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    articles = []
    if os.path.exists(all_articles_file):
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
        except Exception as e:
            print(f"Warning: could not load articles: {e}")

    removed = load_removed_hashes()
    now = datetime.now(timezone.utc)

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">',
    ]

    included = 0
    for article in articles:
        if included >= MAX_URLS:
            break
        if not isinstance(article, dict) or not article.get("id"):
            continue
        if article.get("id") in removed or is_thin(article):
            continue

        published = parse_iso(article.get("published_at"))
        if published is None:
            continue
        age_hours = (now - published).total_seconds() / 3600.0
        if age_hours < 0 or age_hours > MAX_AGE_HOURS:
            continue

        slug = article_slug(article.get("title"), article.get("id"))
        page_path = os.path.join(NEWS_DIR, slug, "index.html")
        if not os.path.exists(page_path):
            # Never list URLs without a real, generated page.
            continue

        loc = BASE_URL + "news/" + slug + "/"
        title = article.get("title") or ""

        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{escape_xml(loc)}</loc>")
        xml_parts.append("    <news:news>")
        xml_parts.append("      <news:publication>")
        xml_parts.append("        <news:name>PikaNews</news:name>")
        xml_parts.append("        <news:language>en</news:language>")
        xml_parts.append("      </news:publication>")
        xml_parts.append(f"      <news:publication_date>{escape_xml(article.get('published_at'))}</news:publication_date>")
        xml_parts.append(f"      <news:title>{escape_xml(title)}</news:title>")
        xml_parts.append("    </news:news>")
        xml_parts.append("  </url>")
        included += 1

    xml_parts.append("</urlset>")

    xml_content = "\n".join(xml_parts) + "\n"

    os.makedirs(os.path.dirname(NEWS_SITEMAP_PATH), exist_ok=True)
    with open(NEWS_SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"Google News sitemap generated: {NEWS_SITEMAP_PATH}")
    print(f"News URLs: {included}")
    return xml_content


if __name__ == "__main__":
    generate_news_sitemap()

