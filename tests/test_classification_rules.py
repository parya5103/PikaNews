"""Deterministic, dependency-free topic classification tests for PikaNews."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.classification_rules import classify_article


def test_specific_title_signal_overrides_publisher_section():
    assert classify_article(
        "NASA discovers a new exoplanet", "The space agency announced the finding.",
        source_name="Variety", source_category="hollywood",
    ) == "science"


def test_topic_is_not_inferred_from_unrelated_publisher_brand():
    assert classify_article(
        "Central bank holds interest rates steady", "Officials cited inflation risks.",
        source_name="TechCrunch", source_category="technology",
    ) == "business"


def test_world_politics_and_health_topics_are_supported():
    assert classify_article("UN Security Council calls emergency meeting", "") == "politics"
    assert classify_article("WHO issues new public health guidance", "") == "health"


def test_sports_and_gaming_are_distinguished():
    assert classify_article("Champions League final ends in dramatic draw", "") == "sports"
    assert classify_article("Nintendo announces a new Switch game", "") == "gaming"


def test_source_category_is_only_a_fallback_when_text_has_no_signal():
    assert classify_article("A major announcement is expected soon", "", source_category="technology") == "technology"


def test_unknown_story_defaults_to_world_not_entertainment_or_trending():
    assert classify_article("Officials confirm an update", "") == "world"


def test_title_signal_outweighs_weak_summary_noise():
    assert classify_article(
        "Scientists publish a new astronomy study on climate",
        "The article mentions a business conference and a film premiere.",
    ) == "science"

def test_global_sources_are_enabled_and_do_not_reuse_remote_images():
    from scripts.fetch_news import RSS_FEEDS

    world = RSS_FEEDS["world"][0]
    science = RSS_FEEDS["science"][0]
    assert world["name"] == "UN Geneva"
    assert world["enabled"] is True
    assert world["region"] == "global"
    assert world["image_policy"] == "none"
    assert science["name"] == "NASA News Releases"
    assert science["enabled"] is True
    assert science["image_policy"] == "none"


def test_eurostat_world_feeds_are_enabled_and_region_tagged():
    from scripts.fetch_news import RSS_FEEDS

    eurostat = RSS_FEEDS["world"][1:]
    assert [source["name"] for source in eurostat] == [
        "Eurostat Press Releases",
        "Eurostat News",
    ]
    assert all(source["enabled"] for source in eurostat)
    assert all(source["region"] == "europe" for source in eurostat)
    assert all(source["image_policy"] == "none" for source in eurostat)
    assert all("CC BY 4.0" in source["reuse_policy"] for source in eurostat)


def test_primary_source_image_policy_is_preserved_during_normalization():
    from scripts import fetch_news

    fetch_news.seen_hashes.clear()
    article = fetch_news.normalize_article(
        {
            "title": "NASA scientists publish a new exoplanet study",
            "url": "https://www.nasa.gov/news-release/example-story/",
            "date": "Fri, 21 Nov 2026 10:00:00 GMT",
            "description": "Researchers describe a new exoplanet observation.",
            "image_url": "https://www.nasa.gov/example.jpg",
        },
        {
            "name": "NASA News Releases",
            "category": "science",
            "url": "https://www.nasa.gov/news-release/feed/",
            "region": "global",
            "image_policy": "none",
        },
    )
    assert article is not None
    assert article["category"] == "science"
    assert article["region"] == "global"
    assert article["image_url"] is None
    assert article["image_policy"] == "none"


def test_category_pages_receive_eligible_stories_beyond_static_article_cap(tmp_path, monkeypatch):
    import json
    from scripts import generate_article_pages as generator

    data_dir = tmp_path / "data"
    news_dir = tmp_path / "frontend" / "news"
    data_dir.mkdir()
    articles = [
        {
            "id": "recent-tech-story",
            "title": "Recent technology story with enough title length",
            "summary": "A sufficiently detailed summary. " + ("Details " * 30),
            "category": "technology",
            "published_at": "2026-11-21T10:00:00+00:00",
            "thin": False,
        },
        {
            "id": "older-world-story",
            "title": "Older world affairs story with enough title length",
            "summary": "A sufficiently detailed international summary. " + ("Details " * 30),
            "category": "world",
            "published_at": "2026-11-18T10:00:00+00:00",
            "thin": False,
        },
    ]
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    monkeypatch.setattr(generator, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(generator, "NEWS_DIR", str(news_dir))
    monkeypatch.setattr(generator, "REMOVED_ARTICLES_FILE", str(tmp_path / "removed_articles.json"))
    monkeypatch.setattr(generator, "MAX_ARTICLES", 1)
    monkeypatch.setattr(generator, "build_page", lambda *args, **kwargs: "<html></html>")
    monkeypatch.setattr(generator, "update_root_listing_robots", lambda items: None)
    captured = {}
    monkeypatch.setattr(
        generator,
        "write_category_pages",
        lambda items, slugs: captured.setdefault("articles", list(items)) and 0,
    )

    assert generator.generate_article_pages() == 2
    assert [article["category"] for article in captured["articles"]] == ["technology", "world"]


def test_world_and_science_category_pages_are_registered_and_noindex():
    from pathlib import Path
    from scripts.generate_article_pages import CATEGORY_PAGE_FILTERS

    root = Path(__file__).resolve().parents[1] / "frontend"
    assert CATEGORY_PAGE_FILTERS["world"] == {"world", "politics", "health", "climate"}
    assert CATEGORY_PAGE_FILTERS["science"] == {"science"}
    for category in ("world", "science"):
        page = (root / f"{category}.html").read_text(encoding="utf-8")
        assert f'id="{category}-news"' in page
        assert 'content="noindex,follow"' in page
