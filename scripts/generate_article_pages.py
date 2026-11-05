#!/usr/bin/env python3
"""
PikaNews Static Article Page Generator.

Generates crawlable, indexable static article pages at
frontend/news/<unique-story-slug>/index.html so every article has its own
real HTML content BEFORE JavaScript executes. This replaces the old
query-parameter-only article architecture (article.html?id=... remains as a
dynamic fallback reader and still works).

The slug MUST match the JavaScript pikanewsSlug() helper in
frontend/article.html so the dynamic reader can redirect to the static page:
    lowercase, non-alphanumeric runs -> '-', strip leading '-', truncate to
    60 chars, strip trailing '-', then append '-' + first 8 chars of the id.

Pages are regenerated on every collector run (every 30 minutes):
  - removed/unpublished (tombstoned) articles are skipped
  - thin entries (very short title or summary) are skipped
  - stale slug directories that no longer belong to a current article are
    deleted so unpublish/delete fully removes the public page.
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote, urljoin

# Configuration
BASE_URL = "https://gogocompany.in/pikanews/"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
NEWS_DIR = os.path.join(FRONTEND_DIR, "news")
NEWS_JSON_DIR = os.path.join(REPO_ROOT, "news_json")
REMOVED_ARTICLES_FILE = os.path.join(REPO_ROOT, "data", "removed_articles.json")
LOGO_URL = urljoin(BASE_URL, "images/pikanews-logo.svg")

MAX_ARTICLES = 300          # keep the generated set small and fresh
MAX_RELATED = 4
MIN_TITLE_LEN = 20
MIN_SUMMARY_LEN = 40

CATEGORY_COLORS = {
    "bollywood": "#ec4899",
    "hollywood": "#8b5cf6",
    "entertainment": "#f59e0b",
    "technology": "#3b82f6",
    "gaming": "#10b981",
    "business": "#06b6d4",
    "sports": "#f97316",
    "trending": "#ef4444",
}


def category_color(category):
    return CATEGORY_COLORS.get((category or "").lower(), "#6b7280")


def article_slug(title, article_id):
    """Must match pikanewsSlug() in frontend/article.html."""
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower())
    s = s.lstrip("-")[:60].rstrip("-")
    return s + "-" + str(article_id or "")[:8]


def is_thin(article):
    """Thin = too short to be a useful, indexable story.

    Works even for older entries that predate the 'thin' flag written by
    scripts/fetch_news.py normalize_article().
    """
    title = article.get("title") or ""
    summary = article.get("summary") or ""
    if article.get("thin") is True:
        return True
    return len(title.strip()) < MIN_TITLE_LEN or len(summary.strip()) < MIN_SUMMARY_LEN


def load_removed_hashes():
    """Hashes of admin-removed articles (tombstones). Restore removes them."""
    removed = set()
    if not os.path.exists(REMOVED_ARTICLES_FILE):
        return removed
    try:
        with open(REMOVED_ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for article_id, record in (data.get("articles") or {}).items():
            if isinstance(record, dict) and record.get("action") not in (None, "restore"):
                removed.add(article_id)
    except Exception as e:
        print(f"Warning: could not load removed articles: {e}")
    return removed


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


def format_display_date(value):
    dt = parse_iso(value)
    if dt is None:
        return escape(str(value or ""))
    return dt.strftime("%B %d, %Y")


def truncate(text, length):
    text = (text or "").strip()
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


def esc(text):
    return escape(str(text if text is not None else ""), quote=True)


def domain_of(url):
    m = re.match(r"https?://([^/]+)", str(url or ""))
    if not m:
        return str(url or "")
    return m.group(1).replace("www.", "")


def article_page_exists(articles_by_slug, article):
    return article_slug(article.get("title"), article.get("id")) in articles_by_slug


def link_for(article, generated_slugs):
    """Prefer the static page; fall back to the dynamic reader."""
    slug = article_slug(article.get("title"), article.get("id"))
    if slug in generated_slugs:
        return "news/" + slug + "/"
    return "article.html?id=" + str(article.get("id", ""))


def build_related_block(article, eligible, generated_slugs):
    category = (article.get("category") or "").lower()
    related = [a for a in eligible
               if a.get("id") != article.get("id")
               and (a.get("category") or "").lower() == category][:MAX_RELATED]
    if not related:
        # fall back to newest stories so the page keeps internal links,
        # but clearly label them as latest, not related
        related = [a for a in eligible if a.get("id") != article.get("id")][:MAX_RELATED]
        if not related:
            return '<p class="form-hint">No other stories available right now.</p>'
    cards = []
    for a in related:
        color = category_color(a.get("category"))
        img = ""
        if a.get("image_url"):
            img = ('<img src="' + esc(a["image_url"]) + '" alt="'
                   + esc(truncate(a.get("title"), 100)) + '" loading="lazy" onerror="this.style.display=\'none\'">')
        else:
            img = ('<div class="news-card-placeholder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/><path d="M9 9h6v6H9z"/></svg></div>')
        cards.append(
            '<div class="news-card" style="--category-color: ' + color + '">'
            '<div class="news-card-image">' + img
            + '<span class="news-card-category" style="background-color: var(--category-color);">' + esc(a.get("category")) + '</span></div>'
            '<div class="news-card-content">'
            '<h3 class="news-card-title"><a href="' + esc(link_for(a, generated_slugs)) + '">' + esc(a.get("title")) + '</a></h3>'
            '<p class="news-card-summary">' + esc(truncate(a.get("summary"), 100)) + '</p>'
            '<div class="news-card-meta">'
            '<span class="news-card-source">' + esc(a.get("source")) + '</span>'
            '<span class="news-card-time">' + esc(format_display_date(a.get("published_at"))) + '</span>'
            '</div></div></div>'
        )
    return "\n                ".join(cards)


def build_newsarticle_jsonld(article, canonical_url):
    published = article.get("published_at") or ""
    modified = article.get("collection_timestamp") or published
    node = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": truncate(article.get("title"), 110),
        "url": canonical_url,
        "mainEntityOfPage": canonical_url,
        "datePublished": published,
        "dateModified": modified,
        "publisher": {
            "@type": "Organization",
            "name": "PikaNews, a digital platform by GoGo Company",
            "url": BASE_URL,
            "logo": {"@type": "ImageObject", "url": LOGO_URL},
        },
        "isBasedOn": article.get("url") or canonical_url,
        "image": [article.get("image_url") or LOGO_URL],
        "articleSection": article.get("category") or "",
        "description": truncate(article.get("summary"), 160),
    }
    # Author attribution only when truthful: RSS feeds rarely carry a
    # byline. The originating publisher is credited via isBasedOn and the
    # visible source box, never as a fabricated PikaNews author.
    if article.get("author"):
        node["author"] = {"@type": "Person", "name": article["author"]}
    return json.dumps(node, ensure_ascii=False)


def build_breadcrumb_jsonld(article, canonical_url):
    node = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE_URL},
            {
                "@type": "ListItem",
                "position": 2,
                "name": (article.get("category") or "News").capitalize(),
                "item": urljoin(BASE_URL, (article.get("category") or "index") + ".html"),
            },
            {"@type": "ListItem", "position": 3, "name": truncate(article.get("title"), 90), "item": canonical_url},
        ],
    }
    return json.dumps(node, ensure_ascii=False)


# Page template. Tokens are replaced in build_page(); literal JS in the page
# uses ordinary browser JS only - no template engine, no ${{ }} artifacts.
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="@@DESCRIPTION@@">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="@@OG_TITLE@@">
    <meta property="og:description" content="@@OG_DESCRIPTION@@">
    <meta property="og:type" content="article">
    <meta property="og:url" content="@@CANONICAL@@">
    <meta property="og:image" content="@@OG_IMAGE@@">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="@@OG_TITLE@@">
    <meta name="twitter:description" content="@@OG_DESCRIPTION@@">
    <meta name="twitter:image" content="@@OG_IMAGE@@">
    <link rel="canonical" href="@@CANONICAL@@">
    <link rel="icon" type="image/svg+xml" href="@@REL_PATH@@images/pikanews-logo.svg">
    <link rel="stylesheet" href="@@REL_PATH@@css/styles.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:wght@400;500;600;700&display=swap" rel="stylesheet">
    <title>@@TITLE@@ - PikaNews</title>
    <script type="application/ld+json">@@NEWSARTICLE_JSONLD@@</script>
    <script type="application/ld+json">@@BREADCRUMB_JSONLD@@</script>
</head>
<body>
    <div class="utility-bar">
        <div class="utility-inner">
            <span id="utility-date" class="utility-date">&nbsp;</span>
            <nav class="utility-links" aria-label="Site links">
                <a class="utility-keep" href="@@REL_PATH@@latest.html">Latest</a>
                <a class="utility-keep" href="@@REL_PATH@@trending.html">Trending</a>
                <a href="@@REL_PATH@@about.html">About</a>
                <a href="@@REL_PATH@@sources.html">Sources</a>
                <a href="@@REL_PATH@@editorial-policy.html">Editorial Policy</a>
                <a href="@@REL_PATH@@contact.html">Contact</a>
            </nav>
        </div>
    </div>
    <header class="header"><div class="header-container"><button id="mobile-menu-toggle" class="mobile-menu-toggle" aria-label="Toggle menu"><span class="hamburger"></span></button><a href="@@REL_PATH@@index.html" class="logo"><img src="@@REL_PATH@@images/pikanews-logo.svg" alt="PikaNews Logo" class="logo-img"><span class="logo-text">Pika<span class="logo-accent">News</span></span></a><nav class="main-nav"><ul class="nav-list"><li class="nav-item"><a href="@@REL_PATH@@index.html" class="nav-link">Home</a></li><li class="nav-item"><a href="@@REL_PATH@@latest.html" class="nav-link">Latest</a></li><li class="nav-item"><a href="@@REL_PATH@@trending.html" class="nav-link">Trending</a></li><li class="nav-item dropdown"><a href="#" class="nav-link dropdown-toggle">Entertainment <span class="dropdown-arrow">&#9660;</span></a><ul class="dropdown-menu"><li><a href="@@REL_PATH@@bollywood.html" class="dropdown-link">Bollywood</a></li><li><a href="@@REL_PATH@@hollywood.html" class="dropdown-link">Hollywood</a></li><li><a href="@@REL_PATH@@entertainment.html" class="dropdown-link">Entertainment</a></li></ul></li><li class="nav-item"><a href="@@REL_PATH@@technology.html" class="nav-link">Technology</a></li><li class="nav-item"><a href="@@REL_PATH@@gaming.html" class="nav-link">Gaming</a></li><li class="nav-item"><a href="@@REL_PATH@@business.html" class="nav-link">Business</a></li><li class="nav-item"><a href="@@REL_PATH@@sports.html" class="nav-link">Sports</a></li></ul></nav><div class="header-actions"><button id="search-toggle" class="action-btn search-toggle" aria-label="Search"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg></button><button id="bookmarks-toggle" class="action-btn bookmarks-toggle" aria-label="Bookmarks"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg><span id="bookmark-count" class="badge">0</span></button><button id="theme-toggle" class="action-btn theme-toggle" aria-label="Toggle theme"><svg class="icon sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg><svg class="icon moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button></div></div></header>
<div id="search-modal" class="modal search-modal"><div class="modal-overlay"></div><div class="modal-content"><form id="search-form" class="search-form"><input type="text" id="search-input" class="search-input" placeholder="Search news..." autocomplete="off"><button type="submit" class="search-submit"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg></button></form><div id="search-results" class="search-results"></div></div></div>
<div id="bookmarks-modal" class="modal bookmarks-modal"><div class="modal-overlay"></div><div class="modal-content"><div class="modal-header"><h2>Bookmarked Articles</h2><button class="modal-close">&times;</button></div><div id="bookmarks-list" class="bookmarks-list"></div></div></div>
<main class="main-content">
    <section class="page-header"><div class="container">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="@@REL_PATH@@index.html">Home</a>
            <span class="sep">&rsaquo;</span>
            <a href="@@REL_PATH@@CATEGORY@@.html">@@CATEGORY_LABEL@@</a>
            <span class="sep">&rsaquo;</span>
            <span>@@CRUMB_TITLE@@</span>
        </nav>
    </div></section>
    <section class="article-section"><div class="container">
        <article id="article-detail" class="article-detail-static">
            <div class="article-header">
                <span class="article-category" style="background-color: @@COLOR@@20; color: @@COLOR@@;">@@CATEGORY_LABEL@@</span>
                <h1 class="article-title">@@TITLE@@</h1>
                <div class="article-meta">
                    <div class="article-meta-item"><svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><span>@@SOURCE@@</span></div>
                    <div class="article-meta-item"><svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg><span>Published @@PUBLISHED_DISPLAY@@</span></div>
                    <div class="article-meta-item"><svg class="article-meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>Collected by PikaNews @@COLLECTED_DISPLAY@@</span></div>
                </div>
            </div>
            @@IMAGE_TAG@@
            <div class="article-body">
                @@SUMMARY_PARAGRAPHS@@
            </div>
            <div class="ad-slot" data-ad-slot="article-bottom" hidden>
                <span class="ad-label">Advertisement</span>
                <ins class="adsbygoogle" style="display:block" data-ad-format="auto" data-full-width-responsive="true"></ins>
            </div>
            <div class="article-footer">
                <div class="article-source">
                    <span class="source-tag">Third-party source</span>
                    <span>Originally published by <strong>@@SOURCE@@</strong>@@ORIGINAL_LINK@@</span>
                </div>
                <div class="article-actions">
                    <a class="article-action-btn" href="@@WHATSAPP_URL@@" target="_blank" rel="noopener noreferrer" aria-label="Share on WhatsApp"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg><span>WhatsApp</span></a>
                    <a class="article-action-btn" href="@@FACEBOOK_URL@@" target="_blank" rel="noopener noreferrer" aria-label="Share on Facebook"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg><span>Facebook</span></a>
                    <a class="article-action-btn" href="@@X_URL@@" target="_blank" rel="noopener noreferrer" aria-label="Share on X"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4l16 16M20 4L4 20"/></svg><span>Post</span></a>
                    <a href="@@ORIGINAL_URL@@" target="_blank" rel="noopener noreferrer" class="article-action-btn"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg><span>Read Original at @@ORIGINAL_DOMAIN@@</span></a>
                </div>
                <p class="editorial-note">PikaNews aggregates headlines and short excerpts from third-party publishers and always links to the original report. This excerpt is not original reporting by PikaNews; the full story, photographs and copyright remain with the publisher above. See our <a href="@@REL_PATH@@sources.html">News Sources &amp; Disclaimer</a>.</p>
            </div>
        </article>
    </div></section>
    <section class="related-articles-section"><div class="container">
        <h2 class="section-title">@@RELATED_HEADING@@</h2>
        <div class="news-grid">
            @@RELATED_CARDS@@
        </div>
    </div></section>
</main>
<footer class="footer"><div class="footer-container"><div class="footer-main"><div class="footer-brand"><a href="@@REL_PATH@@index.html" class="logo"><img src="@@REL_PATH@@images/pikanews-logo.svg" alt="PikaNews Logo" class="logo-img"><span class="logo-text">Pika<span class="logo-accent">News</span></span></a><p class="footer-tagline">Your automatic news aggregator, updated every 30 minutes.</p><p class="footer-brand-legal">PikaNews is a digital platform by GoGo Company.</p></div><div class="footer-links"><h3 class="footer-heading">Quick Links</h3><ul class="footer-list"><li><a href="@@REL_PATH@@index.html">Home</a></li><li><a href="@@REL_PATH@@latest.html">Latest News</a></li><li><a href="@@REL_PATH@@trending.html">Trending</a></li><li><a href="@@REL_PATH@@about.html">About Us</a></li><li><a href="@@REL_PATH@@contact.html">Contact</a></li></ul></div><div class="footer-links"><h3 class="footer-heading">Categories</h3><ul class="footer-list"><li><a href="@@REL_PATH@@bollywood.html">Bollywood</a></li><li><a href="@@REL_PATH@@hollywood.html">Hollywood</a></li><li><a href="@@REL_PATH@@entertainment.html">Entertainment</a></li><li><a href="@@REL_PATH@@technology.html">Technology</a></li><li><a href="@@REL_PATH@@gaming.html">Gaming</a></li><li><a href="@@REL_PATH@@business.html">Business</a></li><li><a href="@@REL_PATH@@sports.html">Sports</a></li></ul></div><div class="footer-links"><h3 class="footer-heading">Legal</h3><ul class="footer-list"><li><a href="@@REL_PATH@@privacy.html">Privacy Policy</a></li><li><a href="@@REL_PATH@@terms.html">Terms of Service</a></li><li><a href="@@REL_PATH@@sources.html">News Sources &amp; Disclaimer</a></li><li><a href="@@REL_PATH@@editorial-policy.html">Editorial &amp; Corrections Policy</a></li><li><a href="@@REL_PATH@@feed.xml">RSS Feed</a></li></ul></div></div><div class="footer-bottom"><p>&copy; 2026 PikaNews, a digital platform by GoGo Company. All rights reserved.</p><p>Automatically updated every 30 minutes</p></div></div></footer>
<div id="toast-container" class="toast-container"></div><button id="back-to-top" class="back-to-top" aria-label="Back to top"><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
<script src="@@REL_PATH@@js/data.js"></script><script src="@@REL_PATH@@js/utils.js"></script><script src="@@REL_PATH@@js/app.js"></script><script src="@@REL_PATH@@js/newsroom.js"></script><script src="@@REL_PATH@@js/ads.js"></script>
</body>
</html>
"""


def build_page(article, eligible, generated_slugs):
    slug = article_slug(article.get("title"), article.get("id"))
    canonical_url = urljoin(BASE_URL, "news/" + slug + "/")
    rel_path = "../../"  # pages live at news/<slug>/index.html

    title = article.get("title") or "News story"
    summary = (article.get("summary") or "").strip() or \
        "No excerpt available. Open the original story for the full report."
    category = (article.get("category") or "news").lower()
    color = category_color(category)
    source = article.get("source") or "Unknown source"
    original_url = article.get("url") or ""

    og_image = article.get("image_url") or LOGO_URL
    description = truncate(summary, 160)

    # Summary as readable paragraphs (RSS excerpts are short; split on
    # sentence boundaries only when the excerpt is long enough).
    paragraphs = []
    if len(summary) > 320:
        parts = re.split(r"(?<=[.!?])\s+", summary)
        buf = ""
        for part in parts:
            if len(buf) + len(part) + 1 > 300 and buf:
                paragraphs.append(buf)
                buf = part
            else:
                buf = (buf + " " + part).strip()
        if buf:
            paragraphs.append(buf)
    else:
        paragraphs.append(summary)
    summary_paragraphs = "\n                ".join(
        "<p>" + esc(p) + "</p>" for p in paragraphs
    )

    image_tag = ""
    if article.get("image_url"):
        image_tag = (
            '<img src="' + esc(article["image_url"]) + '"'
            ' alt="' + esc(truncate(title, 120)) + '"'
            ' class="article-image"'
            ' loading="eager"'
            ' onerror="this.style.display=\'none\'">'
        )

    original_link = ""
    if original_url:
        original_link = (' - <a href="' + esc(original_url) + '" target="_blank" rel="noopener noreferrer">read the full report at '
                          + esc(domain_of(original_url)) + ' &#8599;</a>')

    related_block = build_related_block(article, eligible, generated_slugs)

    page = PAGE_TEMPLATE
    replacements = {
        "@@REL_PATH@@": rel_path,
        "@@CANONICAL@@": canonical_url,
        "@@OG_TITLE@@": esc(title),
        "@@TITLE@@": esc(title),
        "@@OG_DESCRIPTION@@": esc(description),
        "@@DESCRIPTION@@": esc(description),
        "@@OG_IMAGE@@": esc(og_image),
        "@@CATEGORY@@": esc(category),
        "@@CATEGORY_LABEL@@": esc(category.capitalize()),
        "@@COLOR@@": color,
        "@@CRUMB_TITLE@@": esc(truncate(title, 60)),
        "@@SOURCE@@": esc(source),
        "@@PUBLISHED_DISPLAY@@": esc(format_display_date(article.get("published_at"))),
        "@@COLLECTED_DISPLAY@@": esc(format_display_date(article.get("collection_timestamp"))),
        "@@IMAGE_TAG@@": image_tag,
        "@@SUMMARY_PARAGRAPHS@@": summary_paragraphs,
        "@@ORIGINAL_LINK@@": original_link,
        "@@ORIGINAL_URL@@": esc(original_url),
        "@@ORIGINAL_DOMAIN@@": esc(domain_of(original_url)),
        "@@WHATSAPP_URL@@": "https://wa.me/?text=" + quote(title + " - " + canonical_url, safe=""),
        "@@FACEBOOK_URL@@": "https://www.facebook.com/sharer/sharer.php?u=" + quote(canonical_url, safe=""),
        "@@X_URL@@": "https://twitter.com/intent/tweet?text=" + quote(title, safe="") + "&url=" + quote(canonical_url, safe=""),
        "@@RELATED_HEADING@@": "Related Stories",
        "@@RELATED_CARDS@@": related_block,
        "@@NEWSARTICLE_JSONLD@@": build_newsarticle_jsonld(article, canonical_url),
        "@@BREADCRUMB_JSONLD@@": build_breadcrumb_jsonld(article, canonical_url),
    }
    for token, value in replacements.items():
        page = page.replace(token, value)
    return page


def generate_article_pages():
    all_articles_file = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    if not os.path.exists(all_articles_file):
        print(f"No articles file at {all_articles_file}; nothing to generate.")
        return 0

    with open(all_articles_file, "r", encoding="utf-8") as f:
        articles = json.load(f)

    removed = load_removed_hashes()
    eligible = []
    for a in articles:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        if a.get("id") in removed:
            continue
        if is_thin(a):
            continue
        eligible.append(a)

    # all_articles.json is newest-first; keep that order and cap the set.
    eligible = eligible[:MAX_ARTICLES]
    generated_slugs = {article_slug(a.get("title"), a.get("id")) for a in eligible}

    os.makedirs(NEWS_DIR, exist_ok=True)

    # Remove stale slug directories (unpublished/deleted/aged-out articles).
    removed_count = 0
    for entry in os.listdir(NEWS_DIR):
        entry_path = os.path.join(NEWS_DIR, entry)
        if os.path.isdir(entry_path) and entry not in generated_slugs:
            shutil.rmtree(entry_path)
            removed_count += 1

    written = 0
    for article in eligible:
        slug = article_slug(article.get("title"), article.get("id"))
        page_dir = os.path.join(NEWS_DIR, slug)
        os.makedirs(page_dir, exist_ok=True)
        html = build_page(article, eligible, generated_slugs)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        written += 1

    print(f"Static article pages generated: {written} (stale dirs removed: {removed_count})")
    print(f"Output directory: {NEWS_DIR}")
    return written


if __name__ == "__main__":
    generate_article_pages()
