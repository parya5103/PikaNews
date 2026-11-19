import json

from scripts import fetch_news


def article(article_id, category):
    return {
        "id": article_id,
        "title": f"Useful {category} story with enough detail",
        "summary": "A complete summary with enough characters to pass the article minimum length.",
        "category": category,
        "published_at": "2026-11-18T10:00:00+00:00",
        "source": "Example Publisher",
        "url": f"https://example.com/{article_id}",
    }


def test_empty_master_feed_recovers_articles_from_latest_and_category_files(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_news, "NEWS_JSON_DIR", str(tmp_path))
    (tmp_path / "all_articles.json").write_text("", encoding="utf-8")
    latest = article("latest-story", "technology")
    category = article("category-story", "gaming")
    (tmp_path / "latest.json").write_text(json.dumps([latest]), encoding="utf-8")
    (tmp_path / "gaming.json").write_text(json.dumps([category]), encoding="utf-8")
    fetch_news.seen_hashes.clear()

    recovered = fetch_news.load_existing_articles()

    assert {item["id"] for item in recovered} == {"latest-story", "category-story"}


def test_no_new_articles_repairs_empty_master_feed_from_recovered_records(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_news, "NEWS_JSON_DIR", str(tmp_path))
    (tmp_path / "all_articles.json").write_text("", encoding="utf-8")
    story = article("existing-story", "technology")
    (tmp_path / "latest.json").write_text(json.dumps([story]), encoding="utf-8")
    fetch_news.seen_hashes.clear()
    fetch_news.stats["new_articles"] = 0

    recovered = fetch_news.load_existing_articles()
    fetch_news.save_articles([], recovered, always_write=False)

    repaired = json.loads((tmp_path / "all_articles.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in repaired] == ["existing-story"]


def test_load_existing_articles_removes_commercially_restricted_source(tmp_path, monkeypatch):
    import json
    import scripts.fetch_news as fetch_news

    monkeypatch.setattr(fetch_news, "NEWS_JSON_DIR", str(tmp_path))
    monkeypatch.setattr(fetch_news, "seen_hashes", set())
    monkeypatch.setattr(fetch_news, "master_feed_needs_repair", False)
    (tmp_path / "all_articles.json").write_text(json.dumps([
        {"id": "toi-1", "source": "Times of India Bollywood", "title": "Restricted story"},
        {"id": "toi-2", "source": "Times of India", "title": "Restricted alias"},
        {"id": "cnbc-1", "source": "CNBC", "title": "Permitted source record"},
    ]), encoding="utf-8")

    loaded = fetch_news.load_existing_articles()

    assert [article["id"] for article in loaded] == ["cnbc-1"]
    assert fetch_news.master_feed_needs_repair is True
    assert fetch_news.seen_hashes == {"cnbc-1"}
