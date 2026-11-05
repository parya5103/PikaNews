#!/usr/bin/env python3
"""
PikaNews Sitemap Generator
Generates XML sitemap for SEO purposes.
"""

import os
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://gogocompany.in/pikanews/"
SITEMAP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "sitemap.xml")
NEWS_JSON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_json")

# Static pages
STATIC_PAGES = [
    {"url": "index.html", "priority": 1.0, "changefreq": "daily"},
    {"url": "latest.html", "priority": 0.9, "changefreq": "hourly"},
    {"url": "trending.html", "priority": 0.9, "changefreq": "hourly"},
    {"url": "bollywood.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "hollywood.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "entertainment.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "technology.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "gaming.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "business.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "sports.html", "priority": 0.8, "changefreq": "hourly"},
    {"url": "about.html", "priority": 0.5, "changefreq": "monthly"},
    {"url": "contact.html", "priority": 0.5, "changefreq": "monthly"},
    {"url": "privacy.html", "priority": 0.3, "changefreq": "yearly"},
    {"url": "terms.html", "priority": 0.3, "changefreq": "yearly"},
]

# Categories
CATEGORIES = ["bollywood", "hollywood", "entertainment", "technology", "gaming", "business", "sports", "trending"]


def escape_xml(text):
    """Escape XML special characters."""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&apos;")
            .replace('"', "&quot;"))


def generate_sitemap():
    """Generate XML sitemap."""
    # Collect all article URLs
    article_urls = []
    
    # Load all articles
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    if os.path.exists(all_articles_file):
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
                for article in articles:
                    article_url = f"article.html?id={article.get('id', '')}"
                    article_urls.append({
                        "url": article_url,
                        "priority": 0.7,
                        "changefreq": "daily",
                        "lastmod": article.get("published_at", "")
                    })
        except Exception as e:
            print(f"Error loading articles: {e}")
    
    # Generate XML
    xml_parts = []
    
    # XML header
    xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Add static pages
    for page in STATIC_PAGES:
        url = urljoin(BASE_URL, page["url"])
        if url.endswith("/"):
            url = url[:-1]
        
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{escape_xml(url)}</loc>')
        xml_parts.append(f'    <changefreq>{page["changefreq"]}</changefreq>')
        xml_parts.append(f'    <priority>{page["priority"]}</priority>')
        xml_parts.append('  </url>')
    
    # Add article URLs
    for article in article_urls[:1000]:  # Limit to 1000 articles
        url = urljoin(BASE_URL, article["url"])
        
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{escape_xml(url)}</loc>')
        xml_parts.append(f'    <changefreq>{article["changefreq"]}</changefreq>')
        xml_parts.append(f'    <priority>{article["priority"]}</priority>')
        if article.get("lastmod"):
            xml_parts.append(f'    <lastmod>{article["lastmod"][:10]}</lastmod>')
        xml_parts.append('  </url>')
    
    # XML footer
    xml_parts.append('</urlset>')
    
    # Write to file
    xml_content = "\n".join(xml_parts) + "\n"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(SITEMAP_PATH), exist_ok=True)
    
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(xml_content)
    
    print(f"Sitemap generated: {SITEMAP_PATH}")
    print(f"Total URLs: {len(STATIC_PAGES) + len(article_urls[:1000])}")
    
    return xml_content


if __name__ == "__main__":
    generate_sitemap()
