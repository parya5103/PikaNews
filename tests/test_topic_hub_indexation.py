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
    assert "https://gogocompany.in/pikanews/latest.html" not in xml

def test_topic_hub_requires_distinct_publisher_domains_not_just_source_labels():
    same_publisher = stories()
    for index, story in enumerate(same_publisher):
        story["source"] = f"Publisher label {index}"
        story["url"] = f"https://same-publisher.example/story/{index}"
    assert not is_indexable_listing(same_publisher, minimum=12, min_sources=5, now=NOW)

def test_topic_hub_rejects_missing_or_invalid_publisher_urls():
    invalid = stories()
    for story in invalid:
        story["url"] = "not-a-valid-publisher-url"
    assert not is_indexable_listing(invalid, minimum=12, min_sources=5, now=NOW)

def test_sitemap_does_not_count_tombstoned_stories_toward_topic_hub_threshold(tmp_path, monkeypatch):
    import json
    from scripts import generate_sitemap as sitemap

    data_dir = tmp_path / "news_json"
    data_dir.mkdir()
    articles = stories()
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    output = tmp_path / "sitemap.xml"
    removed_ids = {article["id"] for article in articles[:5]}
    monkeypatch.setattr(sitemap, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(sitemap, "SITEMAP_PATH", str(output))
    monkeypatch.setattr(sitemap, "CATEGORY_PAGE_FILTERS", {"technology": {"technology"}, "latest": None})
    monkeypatch.setattr(sitemap, "load_removed_hashes", lambda: removed_ids)

    xml = sitemap.generate_sitemap()

    assert "https://gogocompany.in/pikanews/technology.html" not in xml
    assert "https://gogocompany.in/pikanews/latest.html" not in xml

def test_sitemap_script_fallback_import_works_when_run_as_a_file(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    news_dir = tmp_path / "news_json"
    news_dir.mkdir()
    (news_dir / "all_articles.json").write_text("[]", encoding="utf-8")
    sitemap_path = tmp_path / "sitemap.xml"
    code = """
import sys
scripts_dir, repo_root, news_dir, sitemap_path = sys.argv[1:5]
sys.path = [scripts_dir] + [path for path in sys.path if path not in (repo_root, '')]
import generate_sitemap as sitemap
sitemap.NEWS_JSON_DIR = news_dir
sitemap.SITEMAP_PATH = sitemap_path
sitemap.generate_sitemap()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(scripts_dir), str(repo_root), str(news_dir), str(sitemap_path)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert sitemap_path.exists()
    assert "https://gogocompany.in/pikanews/" in sitemap_path.read_text(encoding="utf-8")


def test_sitemap_uses_same_capped_story_window_as_rendered_category_page(tmp_path, monkeypatch):
    import json
    from scripts import generate_sitemap as sitemap

    data_dir = tmp_path / "news_json"
    data_dir.mkdir()
    articles = stories(count=13, sources=4)
    # The first 12 rendered cards cover only three publisher domains. The
    # thirteenth story would make the full feed qualify, but is not rendered.
    for index, article in enumerate(articles[:12]):
        article["source"] = f"Publisher {index % 3}"
        article["url"] = f"https://publisher-{index % 3}.example/story/{index}"
    articles[12]["source"] = "Publisher 3"
    articles[12]["url"] = "https://publisher-3.example/story/12"
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    output = tmp_path / "sitemap.xml"
    monkeypatch.setattr(sitemap, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(sitemap, "SITEMAP_PATH", str(output))
    monkeypatch.setattr(sitemap, "CATEGORY_PAGE_FILTERS", {"technology": {"technology"}, "latest": None})
    monkeypatch.setattr(sitemap, "load_removed_hashes", lambda: set())

    xml = sitemap.generate_sitemap()

    assert "https://gogocompany.in/pikanews/technology.html" not in xml
