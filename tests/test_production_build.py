#!/usr/bin/env python3
"""
Production-build invariants for the PikaNews static site.

PikaNews is published as a subdirectory of the GoGo Company website at
https://gogocompany.in/pikanews/. These tests fail the build whenever a change
would reintroduce a base-path, SEO or asset bug.
"""

import os
import glob

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")

PROD_BASE = "https://gogocompany.in/pikanews/"
OLD_BASE = "parya5103.github.io/PikaNews"

# Pages that must exist in the published site
REQUIRED_PAGES = [
    "index.html", "latest.html", "trending.html", "article.html",
    "bollywood.html", "hollywood.html", "entertainment.html",
    "technology.html", "gaming.html", "business.html", "sports.html",
    "about.html", "contact.html", "privacy.html", "terms.html",
    "robots.txt", "sitemap.xml", "feed.xml",
]

# Assets the frontend references
REQUIRED_ASSETS = [
    "images/pikanews-logo.svg",
    "css/styles.css",
    "js/data.js",
    "js/utils.js",
    "js/app.js",
]


def all_html_pages():
    return sorted(glob.glob(os.path.join(FRONTEND, "*.html")))


def read(relative_path):
    with open(os.path.join(FRONTEND, relative_path), "r", encoding="utf-8") as f:
        return f.read()


def test_required_pages_and_assets_exist():
    for page in REQUIRED_PAGES:
        assert os.path.exists(os.path.join(FRONTEND, page)), f"missing required file: {page}"
    for asset in REQUIRED_ASSETS:
        assert os.path.exists(os.path.join(FRONTEND, asset)), f"missing required asset: {asset}"


def test_no_root_relative_navigation_links():
    """Root-relative links would escape the /pikanews/ subdirectory."""
    for path in all_html_pages():
        content = read(os.path.basename(path))
        assert 'href="/"' not in content, f"root-relative href found in {path}"
        assert 'href="/PikaNews' not in content, f"old absolute PikaNews href in {path}"


def test_no_github_pages_urls_remain():
    """SEO URLs must use the production domain, not the old GitHub Pages URLs."""
    targets = [os.path.basename(p) for p in all_html_pages()]
    targets += ["robots.txt", "sitemap.xml", "feed.xml", "js/data.js", "js/app.js", "js/utils.js"]
    for name in targets:
        if not os.path.exists(os.path.join(FRONTEND, name)):
            continue
        content = read(name)
        assert OLD_BASE not in content, f"old GitHub Pages URL still referenced in {name}"


def test_every_page_declares_production_canonical():
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        assert 'rel="canonical" href="https://gogocompany.in/pikanews/' in content, \
            f"page {name} does not declare a production canonical URL"


def test_every_page_declares_og_image_and_twitter_image():
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        assert 'property="og:image"' in content, f"missing og:image in {name}"
        assert 'name="twitter:image"' in content, f"missing twitter:image in {name}"
        assert 'name="twitter:card"' in content, f"missing twitter:card in {name}"


def test_data_module_uses_relative_paths():
    data_js = read("js/data.js")
    assert "baseUrl: 'data'" in data_js, "DataManager must use the relative 'data' prefix"
    assert "/PikaNews/data" not in data_js, "old /PikaNews/data base path still present"
    assert "'/data'" not in data_js, "old root-relative /data base path still present"
    assert "pathname.includes" not in data_js, "fragile pathname sniffing still present"


def test_app_module_home_link_stays_inside_site():
    app_js = read("js/app.js")
    assert '<li><a href="index.html" class="mobile-menu-link">Home</a></li>' in app_js, \
        "mobile menu Home link must not point at the site root"


def test_no_unrendered_template_artifacts():
    """article.html was once committed with raw {{ }} template braces that broke its JS."""
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        assert "${{" not in content, "unrendered template artifact in " + name
        # Single stray {{ in an inline script context (function bodies) is a
        # strong signal of the same bug; CSS/HTML never needs it in these files.
        assert "function loadArticle() {{" not in content, f"unrendered function body in {name}"


def test_image_references_resolve_to_existing_assets():
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        assert "pikanews-logo.png" not in content, f"missing .png logo referenced in {name}"
        assert "favicon.png" not in content, f"missing favicon.png referenced in {name}"
        assert "hero-news.jpg" not in content, f"missing hero-news.jpg referenced in {name}"


def test_article_reader_loads_real_data_and_escapes_output():
    content = read("article.html")
    assert "getArticleById" in content, "article page must load articles from collected JSON"
    assert "Utils.escapeHtml" in content, "article page must escape rendered article fields"
    assert "rel=\"noopener noreferrer\"" in content, "external links must use rel=noopener"
    assert "NewsArticle" in content, "article page must emit NewsArticle structured data"


def test_rendering_code_escapes_article_fields():
    app_js = read("js/app.js")
    assert "Utils.escapeHtml(article.title)" in app_js, "card titles must be escaped"
    assert "Utils.escapeHtml(article.summary" in app_js or "escapeHtml(Utils.truncate(article.summary" in app_js, \
        "card summaries must be escaped"
    utils_js = read("js/utils.js")
    assert "&#" in utils_js and "039" in utils_js, "escapeHtml must escape single quotes too"


def test_robots_and_sitemap_use_production_urls():
    robots = read("robots.txt")
    assert "https://gogocompany.in/pikanews/sitemap.xml" in robots, "robots.txt sitemap URL is wrong"
    sitemap = read("sitemap.xml")
    assert OLD_BASE not in sitemap, "sitemap still contains old GitHub Pages URLs"
    assert "https://gogocompany.in/pikanews/" in sitemap, "sitemap does not use production URLs"
    feed = read("feed.xml")
    assert OLD_BASE not in feed, "RSS feed still contains old GitHub Pages URLs"


def test_inline_scripts_are_not_double_braced_anywhere():
    """Any page whose inline JS still contains ${{...}} will silently render [object Object]."""
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        for marker in ("${{Utils.", "${{categoryColor}}", "${{article."):
            assert marker not in content, f"broken template placeholder {marker} in {name}"


if __name__ == "__main__":
    failures = 0
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]:
        try:
            fn()
            print(f"  OK {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failures += 1
    print(f"production-build tests: {'PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    raise SystemExit(0 if failures == 0 else 1)
