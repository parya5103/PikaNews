#!/usr/bin/env python3
"""Validate generated PikaNews article HTML before publishing it."""

import json
import os
import re
import sys

from scripts.generate_article_pages import (
    NEWS_DIR,
    NEWS_JSON_DIR,
    article_slug,
    is_indexable_article,
    is_thin,
    load_removed_hashes,
)


def validate_generated_page(article, page):
    """Return concrete policy/template violations for one generated page."""
    errors = []
    indexable = is_indexable_article(article)
    expected_robots = "index, follow" if indexable else "noindex, follow"
    robots = re.search(
        r'<meta\s+name=["\']robots["\']\s+content=["\']([^"\']+)["\']',
        page,
        re.IGNORECASE,
    )
    if not robots or robots.group(1).strip().lower() != expected_robots:
        errors.append(
            f"robots directive must be {expected_robots!r} for "
            f"{'original editorial' if indexable else 'aggregated content'}"
        )

    has_newsarticle = bool(re.search(
        r'"@type"\s*:\s*"NewsArticle"', page, re.IGNORECASE
    ))
    if indexable and not has_newsarticle:
        errors.append("original editorial page is missing NewsArticle schema")
    if not indexable and has_newsarticle:
        errors.append("aggregated page must not contain NewsArticle schema")

    category = re.sub(
        r"[^a-z0-9-]+", "", str(article.get("category") or "news").lower()
    ) or "news"
    breadcrumb = re.search(
        r'<nav\s+class=["\']breadcrumbs["\'][^>]*>(.*?)</nav>',
        page,
        re.IGNORECASE | re.DOTALL,
    )
    expected_href = f'../../{category}.html'
    if not breadcrumb or expected_href not in breadcrumb.group(1):
        errors.append(
            f"category breadcrumb must link to {expected_href!r}"
        )

    unresolved = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", page)))
    if unresolved:
        errors.append("unresolved template token(s): " + ", ".join(unresolved))
    return errors


def validate_generated_articles():
    source = os.path.join(NEWS_JSON_DIR, "all_articles.json")
    if not os.path.isfile(source):
        raise RuntimeError(f"Missing article data file: {source}")
    with open(source, "r", encoding="utf-8") as handle:
        articles = json.load(handle)
    if not isinstance(articles, list):
        raise RuntimeError("all_articles.json must contain a JSON array")

    removed = load_removed_hashes()
    by_slug = {}
    for article in articles:
        if not isinstance(article, dict) or not article.get("id"):
            continue
        if article["id"] in removed or is_thin(article):
            continue
        by_slug[article_slug(article.get("title"), article.get("id"))] = article

    checked = 0
    failures = []
    if not os.path.isdir(NEWS_DIR):
        raise RuntimeError(f"Generated article directory does not exist: {NEWS_DIR}")
    for name in sorted(os.listdir(NEWS_DIR)):
        page_path = os.path.join(NEWS_DIR, name, "index.html")
        if not os.path.isfile(page_path):
            continue
        article = by_slug.get(name)
        if article is None:
            failures.append(f"{page_path}: generated page has no current source record")
            continue
        with open(page_path, "r", encoding="utf-8") as handle:
            page = handle.read()
        checked += 1
        failures.extend(
            f"{page_path}: {message}"
            for message in validate_generated_page(article, page)
        )

    if failures:
        for failure in failures:
            print("ERROR:", failure)
        raise RuntimeError(
            f"Generated article validation failed: {len(failures)} issue(s) "
            f"across {checked} page(s)"
        )
    print(f"Generated article validation passed: {checked} page(s) checked.")
    return checked


if __name__ == "__main__":
    try:
        validate_generated_articles()
    except Exception as exc:
        print(f"Generated article validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
