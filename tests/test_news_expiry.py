#!/usr/bin/env python3
"""
Regression tests for the automatic old-news expiry policy
(NEWS_RETENTION_DAYS = 30, published_at based, timezone-aware UTC).

Covered:
- 29-day-old article remains.
- 30-day boundary expires consistently (published_at <= now - 30 days).
- 31-day-old article expires.
- Missing / invalid publication dates are never guessed: the article is
  kept and counted for review.
- A zero-new-articles collector run still performs cleanup and rewrites
  every public feed (all_articles, category, latest, trending).
- A category emptied entirely by expiry gets its stale feed rewritten
  as an empty list.
- Expired stories cannot be re-imported from RSS (auto-expire tombstone)
  and tombstones hold no full article content.
- Admin restore refuses auto-expired tombstones (no accidental
  re-publish of a stale story).
- Existing manual unpublish / restore behaviour remains correct.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fixed "now" so expiry decisions are deterministic in tests.
NOW = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)


def _article(article_id, published_at, category="sports"):
    return {
        "id": article_id,
        "title": f"Test story {article_id}",
        "summary": "A sufficiently long summary describing the story.",
        "category": category,
        "source": "Test Source",
        "url": f"https://example.com/{article_id}",
        "published_at": published_at,
        "collection_timestamp": "2026-11-06T00:10:00Z",
    }


def _days_ago(days):
    return (NOW - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Boundary behaviour of expire_old_articles
# ---------------------------------------------------------------------------

def test_29_day_old_article_remains():
    from scripts.fetch_news import expire_old_articles

    article = _article("a29", _days_ago(29))
    remaining, expired, no_valid_date, affected = expire_old_articles([article], now=NOW)

    assert len(remaining) == 1 and remaining[0]["id"] == "a29"
    assert expired == []
    assert no_valid_date == 0
    assert affected == set()


def test_30_day_old_article_expires():
    """Boundary: an article exactly at the cutoff expires consistently."""
    from scripts.fetch_news import expire_old_articles, NEWS_RETENTION_DAYS

    assert NEWS_RETENTION_DAYS == 30
    article = _article("a30", _days_ago(30))
    remaining, expired, no_valid_date, affected = expire_old_articles([article], now=NOW)

    assert remaining == []
    assert [a["id"] for a in expired] == ["a30"]
    assert no_valid_date == 0
    assert affected == {"sports"}


def test_31_day_old_article_expires():
    from scripts.fetch_news import expire_old_articles

    article = _article("a31", _days_ago(31))
    remaining, expired, no_valid_date, affected = expire_old_articles([article], now=NOW)

    assert remaining == []
    assert [a["id"] for a in expired] == ["a31"]
    assert affected == {"sports"}


def test_expiry_uses_published_at_not_collection_date():
    """A 40-day-old story collected today must still expire."""
    from scripts.fetch_news import expire_old_articles

    article = _article("a40", _days_ago(40))
    article["collection_timestamp"] = NOW.isoformat()  # collected moments ago
    remaining, expired, no_valid_date, _ = expire_old_articles([article], now=NOW)

    assert remaining == []
    assert [a["id"] for a in expired] == ["a40"]


def test_missing_and_invalid_dates_are_not_guessed():
    from scripts.fetch_news import expire_old_articles

    missing = _article("m1", None)
    empty = _article("m2", "")
    invalid = _article("m3", "not-a-date")
    remaining, expired, no_valid_date, affected = expire_old_articles(
        [missing, empty, invalid], now=NOW
    )

    # Nothing is deleted on a guessed date; all three are kept and counted.
    assert len(remaining) == 3
    assert {a["id"] for a in remaining} == {"m1", "m2", "m3"}
    assert no_valid_date == 3
    assert expired == []
    assert affected == set()


# ---------------------------------------------------------------------------
# Cleanup + feed regeneration on a zero-new-articles collector run
# ---------------------------------------------------------------------------

def _patched_fetch_news(tmpdir):
    """Point fetch_news paths at a temp dir; returns the module."""
    import scripts.fetch_news as fetch_news

    originals = {
        "NEWS_JSON_DIR": fetch_news.NEWS_JSON_DIR,
        "DATA_DIR": fetch_news.DATA_DIR,
        "REMOVED_ARTICLES_FILE": fetch_news.REMOVED_ARTICLES_FILE,
    }
    fetch_news.NEWS_JSON_DIR = os.path.join(tmpdir, "news_json")
    fetch_news.DATA_DIR = os.path.join(tmpdir, "data")
    fetch_news.REMOVED_ARTICLES_FILE = os.path.join(tmpdir, "data", "removed_articles.json")
    os.makedirs(fetch_news.NEWS_JSON_DIR)
    os.makedirs(fetch_news.DATA_DIR)
    return fetch_news, originals


def _restore_fetch_news(fetch_news, originals):
    for key, value in originals.items():
        setattr(fetch_news, key, value)


def _write_feed(news_json_dir, name, articles):
    with open(os.path.join(news_json_dir, name), "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def _read_feed(news_json_dir, name):
    with open(os.path.join(news_json_dir, name), "r", encoding="utf-8") as f:
        return json.load(f)


def test_zero_new_articles_run_still_cleans_every_feed():
    """Collector run with 0 new articles must still expire old stories
    and rewrite all_articles/category/latest/trending feeds."""
    import scripts.fetch_news as fetch_news

    with tempfile.TemporaryDirectory() as tmpdir:
        fetch_news, originals = _patched_fetch_news(tmpdir)
        try:
            old = _article("old1", _days_ago(31))
            fresh = _article("fresh1", _days_ago(1))

            # Feeds as they exist before the cleanup run.
            for feed in ("all_articles.json", "sports.json",
                         "latest.json", "trending.json"):
                _write_feed(fetch_news.NEWS_JSON_DIR, feed, [old, fresh])

            # The collector's expiry step (runs even with zero new items).
            remaining, expired, no_valid_date, affected = fetch_news.expire_old_articles(
                [old, fresh], now=NOW
            )
            assert [a["id"] for a in expired] == ["old1"]
            fetch_news.add_expiry_tombstones(expired)

            # save_articles with ZERO new articles but always_write=True
            # (exactly what main() does when articles expired this run).
            fetch_news.stats.update({
                "timestamp": NOW.isoformat(),
                "total_fetched": 0,
                "new_articles": 0,
                "duplicates": 0,
                "errors": 0,
                "expired_articles": 1,
                "articles_without_valid_date": 0,
                "by_source": {},
                "by_category": {},
            })
            fetch_news.save_articles(
                [], remaining, always_write=True, affected_categories=affected
            )

            for feed in ("all_articles.json", "sports.json",
                         "latest.json", "trending.json"):
                ids = [a["id"] for a in _read_feed(fetch_news.NEWS_JSON_DIR, feed)]
                assert "old1" not in ids, f"{feed} still contains the expired story"
                assert "fresh1" in ids, f"{feed} lost the fresh story"
        finally:
            _restore_fetch_news(fetch_news, originals)


def test_category_emptied_by_expiry_gets_empty_feed():
    """A category whose only articles expired must not keep a stale JSON
    feed of expired stories on disk."""
    import scripts.fetch_news as fetch_news

    with tempfile.TemporaryDirectory() as tmpdir:
        fetch_news, originals = _patched_fetch_news(tmpdir)
        try:
            old_sports = _article("old-s", _days_ago(35), category="sports")
            fresh_tech = _article("new-t", _days_ago(1), category="technology")
            _write_feed(fetch_news.NEWS_JSON_DIR, "sports.json", [old_sports])

            remaining, expired, no_valid_date, affected = fetch_news.expire_old_articles(
                [old_sports, fresh_tech], now=NOW
            )
            assert affected == {"sports"}
            assert [a["id"] for a in expired] == ["old-s"]

            fetch_news.stats.update({"new_articles": 0})
            fetch_news.save_articles(
                [], remaining, always_write=True, affected_categories=affected
            )

            # sports.json must be rewritten as an empty list, not left stale.
            assert _read_feed(fetch_news.NEWS_JSON_DIR, "sports.json") == []
            tech_ids = [a["id"] for a in _read_feed(fetch_news.NEWS_JSON_DIR, "technology.json")]
            assert tech_ids == ["new-t"]
        finally:
            _restore_fetch_news(fetch_news, originals)


# ---------------------------------------------------------------------------
# Re-import protection via auto-expire tombstones
# ---------------------------------------------------------------------------

def test_expired_article_cannot_be_reimported():
    """Auto-expire tombstones must block a later RSS re-import of the same
    story, and must not retain full article content."""
    import scripts.fetch_news as fetch_news

    with tempfile.TemporaryDirectory() as tmpdir:
        fetch_news, originals = _patched_fetch_news(tmpdir)
        try:
            expired = [_article("gone1", _days_ago(40))]
            added = fetch_news.add_expiry_tombstones(expired)
            assert added == 1

            # Re-import of the same story is blocked on the next sync.
            blocked = fetch_news.load_removed_articles()
            assert "gone1" in blocked

            # Tombstone is lightweight: id/title/source/url only.
            with open(fetch_news.REMOVED_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            tombstone = data["articles"]["gone1"]
            assert tombstone["action"] == "auto-expire"
            assert "article" not in tombstone  # no full record
            assert "summary" not in tombstone
            assert tombstone.get("url") == "https://example.com/gone1"

            # Adding the same expired article again must not duplicate.
            assert fetch_news.add_expiry_tombstones(expired) == 0
        finally:
            _restore_fetch_news(fetch_news, originals)


def test_existing_manual_tombstones_are_preserved_by_expiry():
    """Auto-expiry must never overwrite manual unpublish/delete tombstones."""
    import scripts.fetch_news as fetch_news

    with tempfile.TemporaryDirectory() as tmpdir:
        fetch_news, originals = _patched_fetch_news(tmpdir)
        try:
            manual = {
                "articles": {
                    "manual1": {
                        "action": "unpublish",
                        "reason": "copyright takedown request",
                        "timestamp_utc": NOW.isoformat(),
                        "article": _article("manual1", _days_ago(2)),
                    }
                }
            }
            os.makedirs(os.path.dirname(fetch_news.REMOVED_ARTICLES_FILE), exist_ok=True)
            with open(fetch_news.REMOVED_ARTICLES_FILE, "w", encoding="utf-8") as f:
                json.dump(manual, f)

            # A different story auto-expires; manual tombstone stays intact.
            assert fetch_news.add_expiry_tombstones([_article("gone2", _days_ago(40))]) == 1

            with open(fetch_news.REMOVED_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["articles"]["manual1"]["action"] == "unpublish"
            assert "article" in data["articles"]["manual1"]
            assert data["articles"]["gone2"]["action"] == "auto-expire"

            # Both block re-import.
            blocked = fetch_news.load_removed_articles()
            assert "manual1" in blocked and "gone2" in blocked
        finally:
            _restore_fetch_news(fetch_news, originals)


# ---------------------------------------------------------------------------
# Admin actions stay correct
# ---------------------------------------------------------------------------

def _patched_admin(tmpdir):
    """Point admin_actions paths at a temp dir; returns the module."""
    import scripts.admin_actions as admin

    originals = {
        "NEWS_JSON_DIR": admin.NEWS_JSON_DIR,
        "DATA_DIR": admin.DATA_DIR,
        "REMOVED_FILE": admin.REMOVED_FILE,
        "AUDIT_FILE": admin.AUDIT_FILE,
    }
    admin.NEWS_JSON_DIR = os.path.join(tmpdir, "news_json")
    admin.DATA_DIR = os.path.join(tmpdir, "data")
    admin.REMOVED_FILE = os.path.join(tmpdir, "data", "removed_articles.json")
    admin.AUDIT_FILE = os.path.join(tmpdir, "data", "admin_audit.md")
    os.makedirs(admin.NEWS_JSON_DIR)
    os.makedirs(admin.DATA_DIR)
    return admin, originals


def _restore_admin(admin, originals):
    for key, value in originals.items():
        setattr(admin, key, value)


def test_admin_restore_refuses_auto_expired():
    """Normal admin restore must not resurrect an auto-expired story."""
    import scripts.admin_actions as admin

    with tempfile.TemporaryDirectory() as tmpdir:
        admin, originals = _patched_admin(tmpdir)
        try:
            tombstones = {
                "articles": {
                    "gone1": {
                        "action": "auto-expire",
                        "reason": "older than 30 days (automatic news retention policy)",
                        "timestamp_utc": NOW.isoformat(),
                        "title": "Test story gone1",
                        "source": "Test Source",
                        "url": "https://example.com/gone1",
                        "article_id": "gone1",
                    }
                }
            }
            with open(admin.REMOVED_FILE, "w", encoding="utf-8") as f:
                json.dump(tombstones, f)

            try:
                admin.action_restore(["gone1"], "restore after review")
                raised = False
            except SystemExit:
                raised = True
            assert raised, "restore of an auto-expired article must fail"

            # Tombstone untouched after the refused restore.
            with open(admin.REMOVED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "gone1" in data["articles"]
            assert data["articles"]["gone1"]["action"] == "auto-expire"
        finally:
            _restore_admin(admin, originals)


def test_manual_unpublish_and_restore_still_work():
    """Manual unpublish keeps the full record restorable and restore
    puts the article back into every feed."""
    import scripts.admin_actions as admin

    reason = "manual review takedown"
    with tempfile.TemporaryDirectory() as tmpdir:
        admin, originals = _patched_admin(tmpdir)
        try:
            article = _article("keep1", _days_ago(2))
            with open(os.path.join(admin.NEWS_JSON_DIR, "all_articles.json"), "w",
                      encoding="utf-8") as f:
                json.dump([article], f)

            # Unpublish: article leaves the feeds, tombstone keeps it.
            admin.action_unpublish(["keep1"], reason)
            assert _read_feed(admin.NEWS_JSON_DIR, "all_articles.json") == []
            with open(admin.REMOVED_FILE, "r", encoding="utf-8") as f:
                removed = json.load(f)
            assert removed["articles"]["keep1"]["action"] == "unpublish"
            assert removed["articles"]["keep1"]["article"]["id"] == "keep1"

            # Restore: article returns to the feeds, tombstone is removed.
            admin.action_restore(["keep1"], "restore after review")
            restored_ids = [a["id"] for a in _read_feed(admin.NEWS_JSON_DIR, "all_articles.json")]
            assert restored_ids == ["keep1"]
            with open(admin.REMOVED_FILE, "r", encoding="utf-8") as f:
                removed = json.load(f)
            assert "keep1" not in removed["articles"]
        finally:
            _restore_admin(admin, originals)


def test_manual_permanent_delete_is_not_restorable():
    """Permanent delete keeps only the audit record; restore must fail."""
    import scripts.admin_actions as admin

    with tempfile.TemporaryDirectory() as tmpdir:
        admin, originals = _patched_admin(tmpdir)
        try:
            article = _article("del1", _days_ago(2))
            with open(os.path.join(admin.NEWS_JSON_DIR, "all_articles.json"), "w",
                      encoding="utf-8") as f:
                json.dump([article], f)

            admin.action_delete(["del1"], "permanent removal test")
            assert _read_feed(admin.NEWS_JSON_DIR, "all_articles.json") == []
            with open(admin.REMOVED_FILE, "r", encoding="utf-8") as f:
                removed = json.load(f)
            tombstone = removed["articles"]["del1"]
            assert tombstone["action"] == "delete"
            assert "article" not in tombstone  # full record NOT retained

            try:
                admin.action_restore(["del1"], "restore after review")
                raised = False
            except SystemExit:
                raised = True
            assert raised, "permanently deleted articles must not be restorable"
        finally:
            _restore_admin(admin, originals)


if __name__ == "__main__":
    for name, fn in sorted(
        (n, f) for n, f in list(globals().items())
        if n.startswith("test_") and callable(f)
    ):
        fn()
        print(f"PASS: {name}")
    print("All news expiry regression tests passed.")
