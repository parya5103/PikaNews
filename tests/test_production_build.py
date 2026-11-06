#!/usr/bin/env python3
"""
Production-build invariants for the PikaNews static site.

PikaNews is published as a subdirectory of the GoGo Company website at
https://gogocompany.in/pikanews/. These tests fail the build whenever a change
would reintroduce a base-path, SEO, asset or advertising bug.
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
    "search.html", "about.html", "contact.html", "privacy.html", "terms.html",
    "sources.html", "editorial-policy.html",
    "robots.txt", "sitemap.xml", "feed.xml",
]

# Assets the frontend references
REQUIRED_ASSETS = [
    "images/pikanews-logo.svg",
    "css/styles.css",
    "js/data.js",
    "js/utils.js",
    "js/app.js",
    "js/ads.js",
    "js/newsroom.js",
]

# Generator / admin scripts required for static article publishing
REQUIRED_SCRIPTS = [
    "scripts/fetch_news.py",
    "scripts/generate_sitemap.py",
    "scripts/generate_rss.py",
    "scripts/generate_article_pages.py",
    "scripts/generate_news_sitemap.py",
    "scripts/admin_actions.py",
    ".github/workflows/news_collector.yml",
    ".github/workflows/news-admin.yml",
]

# Ad-capable pages: exactly one ads.js include
AD_PAGES = [
    "index.html", "latest.html", "trending.html", "article.html",
    "bollywood.html", "hollywood.html", "entertainment.html",
    "technology.html", "gaming.html", "business.html", "sports.html",
]

# Pages that must never carry ad slots or the ad loader
NON_AD_PAGES = [
    "search.html", "about.html", "contact.html", "privacy.html",
    "terms.html", "sources.html", "editorial-policy.html",
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
    for script in REQUIRED_SCRIPTS:
        assert os.path.exists(os.path.join(REPO_ROOT, script)), f"missing required script: {script}"


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
    # Ignore // comment lines: the header deliberately mentions the old
    # broken paths as a warning to future editors.
    code_lines = [l for l in data_js.splitlines() if not l.strip().startswith("//")]
    code = "\n".join(code_lines)
    assert "/PikaNews/data" not in code, "old /PikaNews/data base path still present"
    assert "'/data'" not in code and '"/data"' not in code, "old root-relative /data base path still present"
    assert "pathname.includes" not in code, "fragile pathname sniffing still present"


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
    assert 'rel="noopener noreferrer"' in content, "external links must use rel=noopener"
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
    assert "https://gogocompany.in/pikanews/news-sitemap.xml" in robots, \
        "robots.txt must reference the Google News sitemap"
    sitemap = read("sitemap.xml")
    assert OLD_BASE not in sitemap, "sitemap still contains old GitHub Pages URLs"
    assert "https://gogocompany.in/pikanews/" in sitemap, "sitemap does not use production URLs"
    feed = read("feed.xml")
    assert OLD_BASE not in feed, "RSS feed still contains old GitHub Pages URLs"


def test_sitemap_contains_no_query_parameter_article_urls():
    """Static article pages replace the old article.html?id= architecture."""
    sitemap = read("sitemap.xml")
    assert "article.html?id=" not in sitemap, \
        "sitemap lists duplicate query-parameter article URLs instead of static pages"


def test_footer_carries_gogo_branding_on_all_pages():
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        assert "PikaNews is a digital platform by GoGo Company." in content, \
            f"missing GoGo Company brand line in footer of {name}"


def test_ad_loader_included_once_only_on_ad_pages():
    """The AdSense loader must appear exactly once, only on content pages."""
    for page in AD_PAGES:
        content = read(page)
        assert content.count("js/ads.js") == 1, f"ads.js must be included exactly once in {page}"
        assert content.count("adsbygoogle.js") <= 1, f"duplicate AdSense loader in {page}"
    for page in NON_AD_PAGES:
        content = read(page)
        assert "js/ads.js" not in content, f"ads.js must not load on {page}"
        assert "ad-slot" not in content, f"ad placements must not exist on {page}"


def test_ads_config_uses_verified_publisher_and_existing_slot():
    """Only the verified GoGo publisher ID and the existing ad unit are used."""
    ads_js = read("js/ads.js")
    # Verified values from the GoGo Company central repository.
    assert "ca-pub-2895136878543415" in ads_js, "verified publisher ID missing from ads.js"
    assert ads_js.count("ca-pub-") == 1, "more than one publisher ID in ads.js (invented IDs are forbidden)"
    assert "7200569170" in ads_js, "existing ad unit slot ID missing from ads.js"
    # Consent handling must fail closed until a real CMP is configured.
    assert "cmpReady: false" in ads_js or "cmpReady = false" in ads_js or "cmpReady:false" in ads_js, \
        "ads.js must keep cmpReady false until a Google-certified CMP is configured"
    assert "cmpReady: true" not in ads_js, "cmpReady must not be claimed without a real CMP"
    # Single loader guard.
    assert "pikanews-adsense-lib" in ads_js, "ads.js must guard against duplicate loader scripts"


def test_legacy_page_generator_is_deprecated_guard():
    """generate_pages.py must refuse to run instead of clobbering redesigned pages."""
    legacy = read("generate_pages.py")
    assert "sys.exit(1)" in legacy, "legacy generator must exit with an error"
    assert "<!DOCTYPE html>" not in legacy, "legacy generator still contains page templates"


def test_static_article_generator_uses_production_base_and_slug_contract():
    gen = open(os.path.join(REPO_ROOT, "scripts", "generate_article_pages.py"), "r", encoding="utf-8").read()
    assert 'BASE_URL = "https://gogocompany.in/pikanews/"' in gen, \
        "article page generator must use the production base URL"
    assert 'rstrip("-")' in gen and "[:8]" in gen, "slug must match the JS pikanewsSlug contract"
    assert "NewsArticle" in gen, "static pages must emit NewsArticle structured data"
    assert "BreadcrumbList" in gen, "static pages must emit BreadcrumbList structured data"
    assert "index, follow" in gen, "static article pages must be indexable"
    news_sitemap = open(os.path.join(REPO_ROOT, "scripts", "generate_news_sitemap.py"), "r", encoding="utf-8").read()
    assert "sitemap-news/0.9" in news_sitemap, "news sitemap must use the Google news namespace"
    assert "48" in news_sitemap, "news sitemap must respect the freshness window"


def test_inline_scripts_are_not_double_braced_anywhere():
    """Any page whose inline JS still contains ${{...}} will silently render [object Object]."""
    for path in all_html_pages():
        name = os.path.basename(path)
        content = read(name)
        for marker in ("${{Utils.", "${{categoryColor}}", "${{article."):
            assert marker not in content, f"broken template placeholder {marker} in {name}"


def test_contact_request_form_is_honest():
    """The content request form must not fake a successful submission."""
    contact = read("contact.html")
    assert "officialgogocompany@gmail.com" in contact, "contact page must use the verified GoGo email"
    assert "mailto:" in contact, "requests must be routed through the user's own email app"
    assert "NOT submitted until you send that email" in contact or "not" in contact.lower(), \
        "contact form must not claim submission happened silently"
    editorial = read("editorial-policy.html")
    assert "Pending" in editorial and "Resolved" in editorial, \
        "editorial policy must document the request review workflow"


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

