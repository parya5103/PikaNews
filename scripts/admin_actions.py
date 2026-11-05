#!/usr/bin/env python3
"""
PikaNews News Admin Actions.

Manual, admin-only news management executed through the GitHub Actions
workflow .github/workflows/news-admin.yml (workflow_dispatch requires write
access to the repository - that is the admin gate). This script never runs on
a schedule.

Actions:
  unpublish  Hide an article from all public pages WITHOUT destroying its
             record. The full article is stored inside the tombstone so it
             can be restored later. The article is removed from all JSON
             feeds, its static page is deleted and all sitemaps/RSS are
             regenerated. fetch_news.py blocks re-import via the same hash.
  restore    Undo an unpublish: the article returns to all feeds, its static
             page is regenerated. Permanent deletes cannot be restored.
  delete     PERMANENT removal. The article is removed from all JSON feeds
             and its static page deleted. The tombstone keeps ONLY the
             minimal audit fields required for accountability (action,
             reason, timestamp, title, source, original URL, article id).

Deletion propagation (all actions):
  - news_json/all_articles.json, <category>.json, latest.json, trending.json
  - frontend/news/<slug>/ static page (via generate_article_pages.py rebuild)
  - frontend/sitemap.xml, frontend/news-sitemap.xml, frontend/feed.xml

Every action requires a reason and is appended to data/admin_audit.md.

Security/legal note: PikaNews cannot delete content from the original
publisher's website or from search-engine caches; only from PikaNews pages.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

try:
    from scripts.generate_article_pages import article_slug
except ImportError:
    from generate_article_pages import article_slug

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_JSON_DIR = os.path.join(REPO_ROOT, "news_json")
DATA_DIR = os.path.join(REPO_ROOT, "data")
REMOVED_FILE = os.path.join(DATA_DIR, "removed_articles.json")
AUDIT_FILE = os.path.join(DATA_DIR, "admin_audit.md")

MAX_TOTAL_ARTICLES = 2000
MAX_PER_CATEGORY = 500
LATEST_LIMIT = 100
TRENDING_LIMIT = 50

MIN_REASON_LEN = 10

AUDIT_KEYS = ["action", "reason", "timestamp_utc", "title", "source", "url", "article_id"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: could not parse {path}: {e}")
        sys.exit(1)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_removed():
    data = load_json(REMOVED_FILE, {"articles": {}})
    if not isinstance(data, dict) or not isinstance(data.get("articles"), dict):
        print(f"ERROR: {REMOVED_FILE} has an unexpected structure.")
        sys.exit(1)
    return data


def parse_ids(raw):
    ids = [t.strip() for t in raw.replace(",", " ").replace(";", " ").split()]
    ids = [t for t in ids if t]
    if not ids:
        print("ERROR: no article IDs provided.")
        sys.exit(1)
    return ids


def find_articles(all_articles, ids):
    by_id = {}
    for a in all_articles:
        if isinstance(a, dict) and a.get("id"):
            by_id[a["id"]] = a
    found, missing = [], []
    for i in ids:
        if i in by_id:
            found.append(by_id[i])
        else:
            missing.append(i)
    return found, missing


def append_audit(action, reason, records):
    line_date = now_iso()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(
                f"- {line_date} | {action} | id={rec.get('article_id', '')} | "
                f"source={rec.get('source', '')} | title={rec.get('title', '')} | "
                f"reason={reason}\n"
            )


def rewrite_feeds(all_articles, affected_categories):
    """Rewrite all JSON feeds after an insert/remove (mirrors save_articles)."""
    all_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    all_articles = all_articles[:MAX_TOTAL_ARTICLES]
    save_json(os.path.join(NEWS_JSON_DIR, "all_articles.json"), all_articles)

    for category in affected_categories:
        category_articles = [
            a for a in all_articles if (a.get("category") or "").lower() == category.lower()
        ]
        category_articles = category_articles[:MAX_PER_CATEGORY]
        save_json(os.path.join(NEWS_JSON_DIR, f"{category.lower()}.json"), category_articles)

    save_json(os.path.join(NEWS_JSON_DIR, "latest.json"), all_articles[:LATEST_LIMIT])
    save_json(os.path.join(NEWS_JSON_DIR, "trending.json"), all_articles[:TRENDING_LIMIT])


def regenerate_outputs():
    """Rebuild static pages, sitemaps and RSS so removals fully propagate."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    for script in (
        "generate_article_pages.py",
        "generate_sitemap.py",
        "generate_news_sitemap.py",
        "generate_rss.py",
    ):
        result = subprocess.run(
            [sys.executable, os.path.join(scripts_dir, script)],
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            print(f"ERROR: {script} failed with exit code {result.returncode}.")
            sys.exit(1)


def action_unpublish(ids, reason):
    all_articles = load_json(os.path.join(NEWS_JSON_DIR, "all_articles.json"), [])
    found, missing = find_articles(all_articles, ids)
    if missing:
        print(f"ERROR: article IDs not found: {', '.join(missing)}")
        sys.exit(1)
    if not found:
        print("ERROR: no matching articles.")
        sys.exit(1)

    removed = load_removed()

    print("Unpublishing the following articles:")
    for a in found:
        print(f"  - [{a.get('source', '')}] {a.get('title', '')}")
        print(f"    id={a.get('id', '')} url={a.get('url', '')}")

    target_ids = {a["id"] for a in found}
    remaining = [a for a in all_articles if a.get("id") not in target_ids]
    affected = {a.get("category", "") for a in found if a.get("category")}

    for a in found:
        removed["articles"][a["id"]] = {
            "action": "unpublish",
            "reason": reason,
            "timestamp_utc": now_iso(),
            "article": a,  # full record retained for restore
        }
    save_json(REMOVED_FILE, removed)
    rewrite_feeds(remaining, affected)
    append_audit(
        "unpublish", reason,
        [{k: a.get(k) for k in AUDIT_KEYS if k in a} | {"article_id": a.get("id")}
         for a in found],
    )
    print(f"Unpublished {len(found)} article(s). Tombstones block RSS re-import.")


def action_restore(ids, reason):
    removed = load_removed()
    restored, not_restorable, missing = [], [], []
    records = []
    for i in ids:
        entry = removed["articles"].get(i)
        if entry is None:
            missing.append(i)
        elif not entry.get("article"):
            not_restorable.append(i)
        else:
            records.append(entry["article"])
            restored.append(i)

    if missing:
        print(f"ERROR: no tombstone found for IDs: {', '.join(missing)}")
        sys.exit(1)
    if not_restorable:
        print(f"ERROR: permanently deleted articles cannot be restored: {', '.join(not_restorable)}")
        sys.exit(1)
    if not restored:
        print("ERROR: nothing to restore.")
        sys.exit(1)

    for i in restored:
        removed["articles"].pop(i, None)
    save_json(REMOVED_FILE, removed)

    all_articles = load_json(os.path.join(NEWS_JSON_DIR, "all_articles.json"), [])
    existing_ids = {a.get("id") for a in all_articles}
    for rec in records:
        if rec.get("id") not in existing_ids:
            all_articles.append(rec)
    affected = {r.get("category", "") for r in records if r.get("category")}

    rewrite_feeds(all_articles, affected)
    append_audit(
        "restore", reason,
        [{k: r.get(k) for k in AUDIT_KEYS if k in r} | {"article_id": r.get("id")}
         for r in records],
    )
    print(f"Restored {len(restored)} article(s).")


def action_delete(ids, reason):
    all_articles = load_json(os.path.join(NEWS_JSON_DIR, "all_articles.json"), [])
    found, missing = find_articles(all_articles, ids)
    if missing:
        print(f"ERROR: article IDs not found: {', '.join(missing)}")
        sys.exit(1)
    if not found:
        print("ERROR: no matching articles.")
        sys.exit(1)

    removed = load_removed()

    print("PERMANENTLY DELETING the following articles (record kept for audit only):")
    for a in found:
        print(f"  - [{a.get('source', '')}] {a.get('title', '')}")
        print(f"    id={a.get('id', '')} url={a.get('url', '')}")

    target_ids = {a["id"] for a in found}
    remaining = [a for a in all_articles if a.get("id") not in target_ids]
    affected = {a.get("category", "") for a in found if a.get("category")}

    for a in found:
        # Minimal audit record only - the full article is NOT retained.
        removed["articles"][a["id"]] = {
            "action": "delete",
            "reason": reason,
            "timestamp_utc": now_iso(),
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
            "article_id": a.get("id", ""),
        }
    save_json(REMOVED_FILE, removed)
    rewrite_feeds(remaining, affected)
    append_audit(
        "delete", reason,
        [{k: a.get(k) for k in AUDIT_KEYS if k in a} | {"article_id": a.get("id")}
         for a in found],
    )
    print(
        f"Permanently deleted {len(found)} article(s) from all public pages and feeds. "
        "PikaNews cannot remove the original publisher's page or search-engine caches."
    )


def main():
    parser = argparse.ArgumentParser(description="PikaNews admin news management")
    parser.add_argument("--action", required=True,
                        choices=["unpublish", "restore", "delete"])
    parser.add_argument("--article-ids", required=True,
                        help="Article IDs, comma or space separated")
    parser.add_argument("--reason", required=True,
                        help="Mandatory reason (copyright / privacy / correction / spam / other)")
    args = parser.parse_args()

    reason = (args.reason or "").strip()
    if len(reason) < MIN_REASON_LEN:
        print(f"ERROR: a reason of at least {MIN_REASON_LEN} characters is mandatory.")
        sys.exit(1)

    ids = parse_ids(args.article_ids)

    if args.action == "unpublish":
        action_unpublish(ids, reason)
    elif args.action == "restore":
        action_restore(ids, reason)
    else:
        action_delete(ids, reason)

    regenerate_outputs()
    print("All feeds, static pages, sitemaps and RSS regenerated.")


if __name__ == "__main__":
    main()
