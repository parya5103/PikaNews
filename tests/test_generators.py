#!/usr/bin/env python3
"""
Tests for PikaNews generators (sitemap, RSS, static article pages,
news sitemap, slug contract).
"""

import os
import sys
import json
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LONG_TITLE_1 = "India Wins the Cricket World Cup in a Thrilling Final"
LONG_TITLE_2 = "New AI Model Benchmarks Released by Major Research Labs"


def _article(article_id, title, summary="A sufficiently long summary that "
              "describes the story in enough detail to avoid thin-content "
              "classification."):
    return {
        "id": article_id,
        "title": title,
        "summary": summary,
        "category": "sports" if "Cricket" in title else "technology",
        "source": "Test Source",
        "url": "https://example.com/story",
        "published_at": "2026-01-02T00:00:00Z",
        "collection_timestamp": "2026-01-02T00:10:00Z",
    }


def test_google_news_sitemap_title_limit():
    """Google News sitemap titles must not exceed 110 characters."""
    from scripts.generate_news_sitemap import truncate_news_title

    assert truncate_news_title("Short PikaNews headline") == "Short PikaNews headline"
    long_title = "A very long news headline about an important developing story " * 4
    shortened = truncate_news_title(long_title)
    assert len(shortened) <= 110
    assert shortened.endswith("…")
    assert not shortened.endswith(" ")


def test_sitemap_generator():
    """Test sitemap generation with static article URLs."""
    from scripts.generate_sitemap import generate_sitemap, escape_xml
    from scripts.generate_article_pages import article_slug
    import scripts.generate_article_pages as article_pages_module
    import scripts.generate_sitemap as sitemap_module

    print("Testing sitemap generator...")

    # Test XML escaping
    assert escape_xml("Test & text") == "Test &amp; text"
    assert escape_xml("<test>") == "&lt;test&gt;"
    assert escape_xml("'") == "&apos;"
    assert escape_xml('"') == "&quot;"

    with tempfile.TemporaryDirectory() as tmpdir:
        test_sitemap_path = os.path.join(tmpdir, "sitemap.xml")

        news_json_dir = os.path.join(tmpdir, "news_json")
        os.makedirs(news_json_dir)

        test_articles = [
            _article("test1", LONG_TITLE_1),
            _article("test2", LONG_TITLE_2),
        ]
        with open(os.path.join(news_json_dir, "all_articles.json"), "w") as f:
            json.dump(test_articles, f)

        # Keep the tombstone file isolated from the real repository data.
        original_removed_file = article_pages_module.REMOVED_ARTICLES_FILE
        article_pages_module.REMOVED_ARTICLES_FILE = os.path.join(tmpdir, "removed_articles.json")

        original_news_json_dir = sitemap_module.NEWS_JSON_DIR
        original_sitemap_path = sitemap_module.SITEMAP_PATH
        sitemap_module.NEWS_JSON_DIR = news_json_dir
        sitemap_module.SITEMAP_PATH = test_sitemap_path

        try:
            xml_content = generate_sitemap()

            assert os.path.exists(test_sitemap_path)

            with open(test_sitemap_path, "r") as f:
                content = f.read()
                assert "<?xml version=" in content
                assert "<urlset" in content
                assert "</urlset>" in content
                assert "<loc>https://gogocompany.in/pikanews/</loc>" in content
                assert "https://gogocompany.in/pikanews/index.html" not in content
                assert "latest.html" in content
                assert "search.html" not in content, \
                    "internal search results must not be included in the sitemap"
                assert "sources.html" in content
                assert "editorial-policy.html" in content

                # Article URLs must be static news/<slug>/ pages.
                slug1 = article_slug(LONG_TITLE_1, "test1")
                slug2 = article_slug(LONG_TITLE_2, "test2")
                assert f"news/{slug1}/" in content, "static article URL missing"
                assert f"news/{slug2}/" in content, "static article URL missing"

                # Query-parameter article URLs must never appear.
                assert "article.html?id=" not in content, \
                    "sitemap must not contain query-parameter article URLs"

            print("  ✓ Sitemap generation test passed")

        finally:
            article_pages_module.REMOVED_ARTICLES_FILE = original_removed_file
            sitemap_module.NEWS_JSON_DIR = original_news_json_dir
            sitemap_module.SITEMAP_PATH = original_sitemap_path


def test_sitemap_skips_tombstoned_and_thin_articles():
    """Removed (tombstoned) and thin articles must not be in the sitemap."""
    from scripts.generate_sitemap import generate_sitemap
    from scripts.generate_article_pages import article_slug
    import scripts.generate_article_pages as article_pages_module
    import scripts.generate_sitemap as sitemap_module

    print("Testing sitemap tombstone/thin filtering...")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_sitemap_path = os.path.join(tmpdir, "sitemap.xml")
        news_json_dir = os.path.join(tmpdir, "news_json")
        os.makedirs(news_json_dir)

        good = _article("keepme00000001", LONG_TITLE_1)
        removed_article = _article("removeme00001", LONG_TITLE_2)
        thin = {
            "id": "thinme0000001",
            "title": "Too short",
            "summary": "tiny",
            "category": "sports",
            "published_at": "2026-01-02T00:00:00Z",
        }
        with open(os.path.join(news_json_dir, "all_articles.json"), "w") as f:
            json.dump([good, removed_article, thin], f)

        removed_file = os.path.join(tmpdir, "removed_articles.json")
        with open(removed_file, "w") as f:
            json.dump({"articles": {removed_article["id"]: {
                "action": "delete", "reason": "test removal",
            }}}, f)

        original_removed_file = article_pages_module.REMOVED_ARTICLES_FILE
        original_news_json_dir = sitemap_module.NEWS_JSON_DIR
        original_sitemap_path = sitemap_module.SITEMAP_PATH
        article_pages_module.REMOVED_ARTICLES_FILE = removed_file
        sitemap_module.NEWS_JSON_DIR = news_json_dir
        sitemap_module.SITEMAP_PATH = test_sitemap_path

        try:
            generate_sitemap()
            with open(test_sitemap_path, "r") as f:
                content = f.read()
                assert f"news/{article_slug(good['title'], good['id'])}/" in content
                assert f"news/{article_slug(removed_article['title'], removed_article['id'])}/" not in content, \
                    "tombstoned article must not be in the sitemap"
                assert f"news/{article_slug(thin['title'], thin['id'])}/" not in content, \
                    "thin article must not be in the sitemap"

            print("  ✓ Sitemap tombstone/thin filtering test passed")

        finally:
            article_pages_module.REMOVED_ARTICLES_FILE = original_removed_file
            sitemap_module.NEWS_JSON_DIR = original_news_json_dir
            sitemap_module.SITEMAP_PATH = original_sitemap_path


def test_rss_generator():
    """Test RSS feed generation."""
    from scripts.generate_rss import generate_rss_feed, escape_xml
    import scripts.generate_article_pages as article_pages_module
    import scripts.generate_rss as rss_module

    print("Testing RSS generator...")

    assert escape_xml("Test & text") == "Test &amp; text"
    assert escape_xml("<test>") == "&lt;test&gt;"

    with tempfile.TemporaryDirectory() as tmpdir:
        test_rss_path = os.path.join(tmpdir, "feed.xml")

        news_json_dir = os.path.join(tmpdir, "news_json")
        os.makedirs(news_json_dir)

        test_articles = [
            _article("test1", LONG_TITLE_1),
            _article("test2", LONG_TITLE_2),
        ]
        with open(os.path.join(news_json_dir, "all_articles.json"), "w") as f:
            json.dump(test_articles, f)

        original_removed_file = article_pages_module.REMOVED_ARTICLES_FILE
        original_news_json_dir = rss_module.NEWS_JSON_DIR
        original_rss_path = rss_module.RSS_PATH
        article_pages_module.REMOVED_ARTICLES_FILE = os.path.join(tmpdir, "removed_articles.json")
        rss_module.NEWS_JSON_DIR = news_json_dir
        rss_module.RSS_PATH = test_rss_path

        try:
            generate_rss_feed()

            assert os.path.exists(test_rss_path)

            with open(test_rss_path, "r") as f:
                content = f.read()
                assert "<?xml version=" in content
                assert "<rss version=" in content
                assert "<channel>" in content
                assert "</channel>" in content
                assert "PikaNews" in content
                assert LONG_TITLE_1 in content
                assert LONG_TITLE_2 in content

            print("  ✓ RSS generation test passed")

        finally:
            article_pages_module.REMOVED_ARTICLES_FILE = original_removed_file
            rss_module.NEWS_JSON_DIR = original_news_json_dir
            rss_module.RSS_PATH = original_rss_path


def test_article_metadata_stays_within_search_snippet_limits():
    """Generated article metadata is concise even when source text needs HTML escaping."""
    from scripts.generate_article_pages import build_page

    article = _article(
        "metadata01",
        "A Very Long Headline With Apostrophes, Quotations and More Words Than a Search Title Should Carry",
        """A publisher's report says the "new" plan will change readers' options. """ * 4,
    )
    html = build_page(article, [article], set())
    import re
    title_match = re.search(r"<title>(.*?)</title>", html, re.S)
    description_match = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
    assert title_match, "generated page must have a title"
    assert description_match, "generated page must have a description"
    assert len(title_match.group(1)) <= 55, "SEO title plus brand must fit within 55 escaped characters"
    assert len(description_match.group(1)) <= 150, "meta description must fit within 150 escaped characters"
    assert "A Very Long Headline" in html, "full article headline must remain visible in the page body"


def test_static_article_images_use_nested_logo_fallback():
    """Broken remote images on nested static pages must show the local logo."""
    from scripts.generate_article_pages import build_page

    article = _article("image0001", LONG_TITLE_1)
    article["image_url"] = "https://cdn.example.com/story.jpg"
    related = _article("image0002", LONG_TITLE_2)
    related["image_url"] = "https://cdn.example.com/related.jpg"
    html = build_page(article, [article, related], set())

    fallback = "this.onerror=null;this.src='../../images/pikanews-logo.svg'"
    assert html.count(fallback) >= 2, "hero and related article images need a working local fallback"
    assert "this.style.display=\\'none\\'" not in html, "broken images must not leave blank image slots"


def test_homepage_news_cards_have_accessible_bookmark_labels_and_contrast():
    """Dynamic home-page cards expose a name for icon-only bookmark controls."""
    frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    with open(os.path.join(frontend, "js", "app.js"), "r", encoding="utf-8") as f:
        app_js = f.read()
    with open(os.path.join(frontend, "css", "styles.css"), "r", encoding="utf-8") as f:
        css = f.read()
    assert 'aria-label="Bookmark ${Utils.escapeHtml(article.title)}"' in app_js
    assert "background-color: #111827 !important;" in css
    assert "border-left: 3px solid var(--category-color" in css


def test_category_pages_have_static_intro_and_correct_heading_hierarchy():
    """News category/listing pages expose useful copy before JavaScript loads."""
    frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    pages = {
        "bollywood.html": "Latest Bollywood stories",
        "business.html": "Latest business stories",
        "entertainment.html": "Latest entertainment stories",
        "gaming.html": "Latest gaming stories",
        "hollywood.html": "Latest Hollywood stories",
        "sports.html": "Latest sports stories",
        "technology.html": "Latest technology stories",
        "latest.html": "Latest PikaNews reports",
        "trending.html": "Trending PikaNews stories",
    }
    for filename, heading in pages.items():
        with open(os.path.join(frontend, filename), "r", encoding="utf-8") as f:
            html = f.read()
        assert 'class="category-intro"' in html, filename + " is missing static intro copy"
        assert "<h2" in html and heading in html, filename + " is missing its section heading"

    with open(os.path.join(frontend, "search.html"), "r", encoding="utf-8") as f:
        search_html = f.read()
    assert '<meta name="robots" content="noindex, follow">' in search_html
    assert "Articles matching your search" in search_html


def test_article_slug_matches_js_contract():
    """Python slug must match pikanewsSlug() in frontend/article.html."""
    from scripts.generate_article_pages import article_slug

    print("Testing article slug contract...")

    # lowercase, non-alphanumeric runs collapse to '-', max 60 chars,
    # then '-' + first 8 chars of the id.
    s = article_slug("Big Bollywood Release Delayed To Next Year!!", "a" * 64)
    assert s == "big-bollywood-release-delayed-to-next-year-aaaaaaaa", s

    s2 = article_slug("UPPER CASE Title With Spaces", "deadbeef1234")
    assert s2 == "upper-case-title-with-spaces-deadbeef", s2

    long_title = "word " * 30  # 150 chars -> slug part must cap at 60
    s3 = article_slug(long_title, "id123456")
    slug_part = s3.rsplit("-", 1)[0]
    assert len(slug_part) <= 60, "slug part must be capped at 60 chars"
    assert s3.endswith("-id123456"), s3

    # Non-ASCII / punctuation runs collapse to a single dash.
    s4 = article_slug("Cricket: India vs Australia!!!", "abcd1234")
    assert s4 == "cricket-india-vs-australia-abcd1234", s4

    print("  ✓ Article slug contract test passed")


def test_thin_detection():
    """Thin articles (short title or summary) must be flagged."""
    from scripts.generate_article_pages import is_thin

    print("Testing thin-content detection...")

    assert is_thin({"title": "short", "summary": "x" * 100}) is True
    assert is_thin({"title": "x" * 40, "summary": "too small"}) is True
    assert is_thin({"title": LONG_TITLE_1, "summary": "x" * 60}) is False
    # The 'thin' flag written by fetch_news must be honoured even for
    # entries with a long title and summary.
    assert is_thin({"title": LONG_TITLE_1, "summary": "x" * 60, "thin": True}) is True

    print("  ✓ Thin-content detection test passed")


def test_url_construction():
    """Test URL construction in generators."""
    from urllib.parse import urljoin

    print("Testing URL construction...")

    base_url = "https://gogocompany.in/pikanews/"

    assert urljoin(base_url, "news/some-story-ab12cd34/") == \
        "https://gogocompany.in/pikanews/news/some-story-ab12cd34/"
    assert urljoin(base_url, "index.html") == "https://gogocompany.in/pikanews/index.html"
    assert urljoin(base_url, "") == "https://gogocompany.in/pikanews/"

    print("  ✓ URL construction test passed")


def run_tests():
    """Run all generator tests."""
    print("=" * 60)
    print("PIKANEWS GENERATOR TESTS")
    print("=" * 60)
    print()

    try:
        test_sitemap_generator()
        test_sitemap_skips_tombstoned_and_thin_articles()
        test_rss_generator()
        test_article_slug_matches_js_contract()
        test_article_metadata_stays_within_search_snippet_limits()
        test_thin_detection()
        test_url_construction()

        print()
        print("=" * 60)
        print("ALL GENERATOR TESTS PASSED")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)




def test_category_pages_prerender_source_attributed_stories(tmp_path):
    """Category listings expose article links and summaries before JavaScript runs."""
    from scripts.generate_article_pages import (
        article_slug, write_category_pages,
    )

    article = _article(
        "category01",
        "A Detailed Report on a New Technology Release",
        "The publisher reports a new technology release with details about features, availability and the company announcement.",
    )
    article.update({
        "category": "technology",
        "source": "Example Publisher",
        "published_at": "2026-11-14T10:00:00+00:00",
        "url": "https://publisher.example/story",
    })
    slug = article_slug(article["title"], article["id"])
    page = tmp_path / "technology.html"
    page.write_text(
        '<main><div id="technology-news" class="news-grid">'
        '<div class="loading-placeholder">Loading...</div></div></main>',
        encoding="utf-8",
    )

    updated = write_category_pages([article], {slug}, frontend_dir=str(tmp_path))
    html = page.read_text(encoding="utf-8")

    assert updated == 1
    assert "A Detailed Report on a New Technology Release" in html
    assert 'href="news/' + slug + '/"' in html
    assert "Example Publisher" in html
    assert "publisher.example" not in html
    assert "Loading..." not in html
    assert '<time class="news-card-time" datetime="2026-11-14T10:00:00+00:00">' in html


def test_category_page_prerender_keeps_other_page_markup(tmp_path):
    """Updating one category grid does not remove headings or intro content."""
    from scripts.generate_article_pages import (
        article_slug, write_category_pages,
    )

    article = _article("category02", "A Useful Business Update With Details",
                       "A publisher summary that explains the business update and its relevance to readers.")
    article["category"] = "business"
    article["source"] = "Business Desk"
    article["published_at"] = "2026-11-14T10:00:00+00:00"
    slug = article_slug(article["title"], article["id"])
    page = tmp_path / "business.html"
    page.write_text(
        '<section><h1>Business News</h1><div class="category-intro">Original guidance</div>'
        '<div id="business-news" class="news-grid"><div class="loading-placeholder">Loading</div></div>'
        '</section>',
        encoding="utf-8",
    )
    write_category_pages([article], {slug}, frontend_dir=str(tmp_path))
    html = page.read_text(encoding="utf-8")
    assert "<h1>Business News</h1>" in html
    assert "Original guidance" in html
    assert "Business Desk" in html


def test_client_loader_preserves_static_story_fallbacks():
    """Empty/error API responses must not erase server-rendered story cards."""
    frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    with open(os.path.join(frontend, "js", "app.js"), "r", encoding="utf-8") as f:
        app_js = f.read()
    assert "if (!latestNewsEl.querySelector('.news-card'))" in app_js
    assert "if (!newsEl.querySelector('.news-card'))" in app_js


def test_homepage_has_clear_source_context_and_no_meta_keywords():
    """The homepage explains aggregation and attribution in crawlable HTML."""
    frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    with open(os.path.join(frontend, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()

    normalized = content.lower()
    assert 'name="keywords"' not in normalized
    assert "original publisher remains responsible" in normalized
    assert "publication time" in normalized
    assert 'href="sources.html"' in normalized
    assert 'href="editorial-policy.html"' in normalized
    assert 'href="latest.html"' in normalized
    assert 'href="trending.html"' in normalized
