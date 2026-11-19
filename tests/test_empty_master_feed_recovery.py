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
