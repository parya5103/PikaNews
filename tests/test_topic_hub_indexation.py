"""Quality gates for indexable PikaNews topic discovery pages."""

from datetime import datetime, timedelta, timezone

from scripts.generate_article_pages import is_indexable_listing

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def stories(count=12, sources=6, summary_length=150, age_days=1):
    published = (NOW - timedelta(days=age_days)).isoformat()
    return [
        {
            "id": f"story-{index}",
            "title": f"A sufficiently descriptive headline for current story {index}",
            "summary": "Verified publisher excerpt. " + ("Context and details. " * 10),
            "source": f"Publisher {index % sources}",
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
