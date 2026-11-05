#!/usr/bin/env python3
"""
PikaNews RSS Feed Generator
Generates RSS feed for PikaNews articles.
"""

import os
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://gogocompany.in/pikanews/"
RSS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "feed.xml")
NEWS_JSON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_json")


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


def generate_rss_feed():
    """Generate RSS 2.0 feed."""
    # Load all articles
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    articles = []
    
    if os.path.exists(all_articles_file):
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
        except Exception as e:
            print(f"Error loading articles: {e}")
    
    # Sort by published_at (newest first)
    articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    
    # Limit to 50 most recent articles
    recent_articles = articles[:50]
    
    # Generate XML
    xml_parts = []
    
    # XML header
    xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_parts.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    xml_parts.append('  <channel>')
    xml_parts.append(f'    <title>PikaNews - Latest News Aggregator</title>')
    xml_parts.append(f'    <link>{BASE_URL}</link>')
    xml_parts.append(f'    <description>Your daily dose of Bollywood, Hollywood, Technology, Gaming, Business, and Sports news. Automatically updated every 30 minutes.</description>')
    xml_parts.append(f'    <language>en-us</language>')
    # Anchor channel dates to the newest article so the feed only changes when content changes.
    build_date = datetime.now(timezone.utc)
    if recent_articles:
        try:
            build_date = datetime.fromisoformat(recent_articles[0].get("published_at", "").replace("Z", "+00:00"))
        except Exception:
            pass
    build_date_str = build_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml_parts.append(f'    <pubDate>{build_date_str}</pubDate>')
    xml_parts.append(f'    <lastBuildDate>{build_date_str}</lastBuildDate>')
    xml_parts.append(f'    <ttl>30</ttl>')
    xml_parts.append(f'    <atom:link href="{urljoin(BASE_URL, "feed.xml")}" rel="self" type="application/rss+xml"/>')
    
    # Add items
    for article in recent_articles:
        article_id = article.get("id", "")
        title = article.get("title", "Untitled")
        description = article.get("summary", "")
        link = urljoin(BASE_URL, f"article.html?id={article_id}")
        pub_date = article.get("published_at", "")
        category = article.get("category", "")
        source = article.get("source", "")
        source_url = article.get("url", "")
        
        # Format pubDate for RSS
        try:
            pub_date_obj = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            pub_date_str = pub_date_obj.strftime("%a, %d %b %Y %H:%M:%S GMT")
        except Exception:
            pub_date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        xml_parts.append('    <item>')
        xml_parts.append(f'      <title>{escape_xml(title)}</title>')
        xml_parts.append(f'      <link>{escape_xml(link)}</link>')
        xml_parts.append(f'      <description><![CDATA[{escape_xml(description)}]]></description>')
        xml_parts.append(f'      <pubDate>{pub_date_str}</pubDate>')
        xml_parts.append(f'      <category>{escape_xml(category)}</category>')
        xml_parts.append(f'      <source url="{escape_xml(source_url)}">{escape_xml(source)}</source>')
        xml_parts.append(f'      <guid>{escape_xml(link)}</guid>')
        xml_parts.append('    </item>')
    
    # XML footer
    xml_parts.append('  </channel>')
    xml_parts.append('</rss>')
    
    # Write to file
    xml_content = "\n".join(xml_parts) + "\n"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(RSS_PATH), exist_ok=True)
    
    with open(RSS_PATH, "w", encoding="utf-8") as f:
        f.write(xml_content)
    
    print(f"RSS feed generated: {RSS_PATH}")
    print(f"Total articles: {len(recent_articles)}")
    
    return xml_content


if __name__ == "__main__":
    generate_rss_feed()
