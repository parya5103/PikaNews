"""Regression tests for the upgraded feed transport, health and format support."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.feed_engine import (
    discover_feed_urls,
    fetch_feed,
    feed_health_snapshot,
    extract_reading_text,
    parse_json_feed,
    rank_feed_candidates,
)


def response(status=200, text="<rss/>", headers=None):
    item = Mock()
    item.status_code = status
    item.text = text
    item.headers = headers or {}
    item.raise_for_status = Mock()
    return item


def test_fetch_feed_uses_etag_and_cached_body_on_not_modified(tmp_path):
    cache_dir = tmp_path / "cache"
    state_path = tmp_path / "health.json"
    first = response(200, "<rss><channel/></rss>", {"ETag": '"v1"', "Last-Modified": "Wed, 26 Nov 2026 10:00:00 GMT"})
    with patch("scripts.feed_engine.is_public_http_url", return_value=True), patch("scripts.feed_engine.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.return_value = first
        body, status = fetch_feed("https://news.example/rss", cache_dir, state_path, sleep=lambda _: None)
    assert body == "<rss><channel/></rss>"
    assert status == "updated"

    second = response(304, "", {})
    with patch("scripts.feed_engine.is_public_http_url", return_value=True), patch("scripts.feed_engine.httpx.Client") as client:
        session = client.return_value.__enter__.return_value
        session.get.return_value = second
        body, status = fetch_feed("https://news.example/rss", cache_dir, state_path, sleep=lambda _: None)
        request_headers = session.get.call_args.kwargs["headers"]
    assert status == "not_modified"
    assert body == "<rss><channel/></rss>"
    assert request_headers["If-None-Match"] == '"v1"'
    assert request_headers["If-Modified-Since"] == "Wed, 26 Nov 2026 10:00:00 GMT"


def test_fetch_feed_persists_failure_streak_and_retry_after(tmp_path):
    state_path = tmp_path / "health.json"
    bad = response(503, "", {"Retry-After": "60"})
    bad.raise_for_status.side_effect = Exception("503")
    with patch("scripts.feed_engine.is_public_http_url", return_value=True), patch("scripts.feed_engine.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.return_value = bad
        body, status = fetch_feed("https://news.example/rss", tmp_path / "cache", state_path, max_retries=1, sleep=lambda _: None)
    assert body is None
    assert status == "failed"
    record = feed_health_snapshot(state_path)["https://news.example/rss"]
    assert record["consecutive_failures"] == 1
    assert record["last_status"] == 503
    assert record["next_retry_at"]


def test_private_redirect_is_rejected_before_following(tmp_path):
    redirect = response(302, "", {"Location": "http://127.0.0.1/admin"})
    with patch("scripts.feed_engine.is_public_http_url", side_effect=lambda url: url.startswith("https://")), patch("scripts.feed_engine.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.return_value = redirect
        body, status = fetch_feed("https://news.example/rss", tmp_path / "cache", tmp_path / "health.json", max_retries=1, sleep=lambda _: None)
    assert body is None
    assert status == "failed"
    client.return_value.__enter__.return_value.get.assert_called_once()


def test_json_feed_is_normalized_to_collector_article_shape():
    articles = parse_json_feed(json.dumps({
        "version": "https://jsonfeed.org/version/1.1",
        "items": [{
            "id": "story-1", "url": "https://news.example/story",
            "title": "A useful headline", "content_text": "A useful summary",
            "date_published": "2026-11-26T10:00:00Z",
            "authors": [{"name": "Reporter"}],
            "tags": ["science"],
            "image": "https://news.example/image.jpg",
        }]
    }), "https://news.example/feed.json")
    assert articles[0]["url"] == "https://news.example/story"
    assert articles[0]["description"] == "A useful summary"
    assert articles[0]["author"] == "Reporter"
    assert articles[0]["categories"] == ["science"]
    assert articles[0]["image_url"] == "https://news.example/image.jpg"


def test_feed_autodiscovery_finds_only_supported_public_feed_links():
    html = """
    <link rel="alternate" type="application/rss+xml" href="/rss.xml">
    <link rel="alternate" type="application/atom+xml" href="https://news.example/atom.xml">
    <link rel="alternate" type="application/feed+json" href="/feed.json">
    <link rel="alternate" type="text/html" href="/latest">
    """
    with patch("scripts.feed_engine.is_public_http_url", return_value=True):
        found = discover_feed_urls(html, "https://news.example/")
    assert found == [
        "https://news.example/rss.xml",
        "https://news.example/atom.xml",
        "https://news.example/feed.json",
    ]


def test_source_ranking_is_stable_and_prefers_healthy_high_priority_feeds():
    candidates = [
        {"name": "slow", "priority": 2, "health": {"consecutive_failures": 4}},
        {"name": "primary", "priority": 1, "health": {"consecutive_failures": 0}},
    ]
    assert [x["name"] for x in rank_feed_candidates(candidates)] == ["primary", "slow"]



def test_permanent_http_error_is_not_retried(tmp_path):
    import httpx
    request = httpx.Request("GET", "https://news.example/rss")
    bad = response(404, "")
    bad.raise_for_status.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=httpx.Response(404, request=request)
    )
    with patch("scripts.feed_engine.is_public_http_url", return_value=True), patch("scripts.feed_engine.httpx.Client") as client:
        client.return_value.__enter__.return_value.get.return_value = bad
        body, status = fetch_feed("https://news.example/rss", tmp_path / "cache", tmp_path / "health.json", max_retries=3, sleep=lambda _: None)
    assert body is None
    assert status == "failed"
    assert client.return_value.__enter__.return_value.get.call_count == 1


def test_reading_context_extractor_removes_navigation_and_scripts():
    html = """
    <nav>Navigation noise</nav><script>tracking()</script>
    <article><p>First useful paragraph.</p><p>Second useful paragraph.</p></article>
    """
    result = extract_reading_text(html)
    assert result == "First useful paragraph. Second useful paragraph."
    assert "Navigation noise" not in result
    assert "tracking" not in result
