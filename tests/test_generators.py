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
                assert "search.html" in content
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

