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


def test_world_politics_health_and_climate_stories_use_visible_world_feed():
    assert classify_article("UN Security Council calls emergency meeting", "") == "world"
    assert classify_article("WHO issues new public health guidance", "") == "world"
    assert classify_article("Global warming accelerates across the Arctic", "") == "world"
    assert classify_article("", "", source_category="health") == "world"


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


def test_world_and_science_category_pages_are_registered_and_noindex():
    from pathlib import Path
    from scripts.generate_article_pages import CATEGORY_PAGE_FILTERS

    root = Path(__file__).resolve().parents[1] / "frontend"
    assert CATEGORY_PAGE_FILTERS["world"] == {"world"}
    assert CATEGORY_PAGE_FILTERS["science"] == {"science"}
    for category in ("world", "science"):
        page = (root / f"{category}.html").read_text(encoding="utf-8")
        assert f'id="{category}-news"' in page
        assert 'content="noindex,follow"' in page
