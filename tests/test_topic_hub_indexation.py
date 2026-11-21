"""Quality gates for indexable PikaNews topic discovery pages."""

from datetime import datetime, timedelta, timezone

from scripts.generate_article_pages import is_indexable_listing

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def stories(count=12, sources=6, age_days=1):
    published = (NOW - timedelta(days=age_days)).isoformat()
    return [
        {
            "id": f"story-{index}",
            "title": f"A sufficiently descriptive headline for current story {index}",
            "summary": "Verified publisher excerpt. " + ("Context and details. " * 10),
            "source": f"Publisher {index % sources}",
            "url": f"https://publisher-{index % sources}.example/story/{index}",
            "category": "technology",
            "published_at": published,
        }
        for index in range(count)
    ]


def test_latest_topic_hub_requires_twelve_recent_stories_and_five_publishers():
    assert is_indexable_listing(stories(), minimum=12, min_sources=5, now=NOW)
    assert not is_indexable_listing(stories(count=11), minimum=12, min_sources=5, now=NOW)
    assert not is_indexable_listing(stories(sources=4), minimum=12, min_sources=5, now=NOW)


def test_category_topic_hub_can_qualify_with_eight_stories_and_four_publishers():
    assert is_indexable_listing(stories(count=8, sources=4), minimum=8, min_sources=4, now=NOW)
    assert not is_indexable_listing(stories(count=8, sources=3), minimum=8, min_sources=4, now=NOW)


def test_topic_hub_rejects_stale_or_undated_stories():
    assert not is_indexable_listing(stories(age_days=15), minimum=12, min_sources=5, now=NOW)
    undated = stories()
    undated[0]["published_at"] = ""
    assert not is_indexable_listing(undated, minimum=12, min_sources=5, now=NOW)


def test_topic_hub_rejects_short_excerpts_even_when_story_count_is_high():
    short = stories()
    for story in short:
        story["summary"] = "Short excerpt only."
    assert not is_indexable_listing(short, minimum=12, min_sources=5, now=NOW)

def test_topic_hub_sitemap_includes_qualified_latest_and_category_but_not_trending(tmp_path, monkeypatch):
    import json
    from scripts import generate_sitemap as sitemap

    data_dir = tmp_path / "news_json"
    data_dir.mkdir()
    articles = stories()
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    output = tmp_path / "sitemap.xml"
    monkeypatch.setattr(sitemap, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(sitemap, "SITEMAP_PATH", str(output))
    monkeypatch.setattr(sitemap, "CATEGORY_PAGE_FILTERS", {"technology": {"technology"}, "latest": None})
    monkeypatch.setattr(sitemap, "load_removed_hashes", lambda: set())

    xml = sitemap.generate_sitemap()

    assert "https://gogocompany.in/pikanews/latest.html" in xml
    assert "https://gogocompany.in/pikanews/technology.html" in xml
    assert "https://gogocompany.in/pikanews/trending.html" not in xml
    assert "/news/" not in xml


def test_topic_hub_sitemap_rejects_low_quality_category_feed(tmp_path, monkeypatch):
    import json
    from scripts import generate_sitemap as sitemap

    data_dir = tmp_path / "news_json"
    data_dir.mkdir()
    articles = stories()
    for article in articles:
        article["summary"] = "Short excerpt."
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    output = tmp_path / "sitemap.xml"
    monkeypatch.setattr(sitemap, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(sitemap, "SITEMAP_PATH", str(output))
    monkeypatch.setattr(sitemap, "CATEGORY_PAGE_FILTERS", {"technology": {"technology"}, "latest": None})
    monkeypatch.setattr(sitemap, "load_removed_hashes", lambda: set())

    xml = sitemap.generate_sitemap()

    assert "https://gogocompany.in/pikanews/technology.html" not in xml
    assert "https://gogocompany.in/pikanews/latest.html" not in xml

def test_topic_hub_requires_distinct_publisher_domains_not_just_source_labels():
    same_publisher = stories()
    for index, story in enumerate(same_publisher):
        story["source"] = f"Publisher label {index}"
        story["url"] = f"https://same-publisher.example/story/{index}"
    assert not is_indexable_listing(same_publisher, minimum=12, min_sources=5, now=NOW)
