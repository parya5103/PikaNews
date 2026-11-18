"""Indexation and structured-data policy for PikaNews articles."""

import json
from pathlib import Path

from scripts.generate_article_pages import (
    BASE_URL,
    article_slug,
    build_newsarticle_jsonld,
    build_page,
    build_category_cards,
    is_indexable_article,
)


def aggregated_article():
    return {
        "id": "agg123456789",
        "title": "A sufficiently descriptive third-party headline about a current event",
        "summary": "A third-party publisher provides this short excerpt about the event, with the original story linked for further reading.",
        "category": "technology",
        "source": "Example Publisher",
        "url": "https://publisher.example/story",
        "published_at": "2026-11-18T10:00:00+00:00",
        "collection_timestamp": "2026-11-19T10:00:00+00:00",
        "image_url": "https://images.example/story.jpg",
    }


def original_editorial_article():
    return {
        **aggregated_article(),
        "id": "edit123456789",
        "content_type": "original_editorial",
        "editorial_reviewed": True,
        "editorial_content": ("PikaNews original editorial analysis. " * 40),
        "author": "PikaNews Editorial Desk",
        "author_type": "Organization",
    }





def test_dynamic_article_fallback_stays_noindex_and_reserves_image_space():
    template = Path("frontend/article.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, follow">' in template
    assert 'class="article-image" width="1200" height="675" loading="eager" fetchpriority="high"' in template
    assert 'width="640" height="360" loading="lazy"' in template

def test_homepage_first_featured_image_is_eager_and_all_cards_reserve_space():
    app_js = Path("frontend/js/app.js").read_text(encoding="utf-8")
    assert 'width="640" height="360"' in app_js
    assert "index === 0 ? 'eager' : 'lazy'" in app_js
    assert 'fetchpriority="high"' in app_js
    assert 'decoding="async"' in app_js

def test_news_images_reserve_dimensions_and_prioritize_first_visible_image():
    cards = build_category_cards(
        [
            {"title": "First story", "category": "technology", "image_url": "https://images.example/first.jpg"},
            {"title": "Second story", "category": "technology", "image_url": "https://images.example/second.jpg"},
        ],
        set(),
    )
    assert 'width="640" height="360" loading="eager" fetchpriority="high"' in cards
    assert 'width="640" height="360" loading="lazy"' in cards


def test_article_hero_image_is_eager_and_has_reserved_dimensions():
    page = build_page(aggregated_article(), [aggregated_article()], set())
    assert 'width="1200" height="675" fetchpriority="high"' in page
    assert 'loading="eager"' in page

def test_third_party_aggregated_excerpt_is_not_indexable_or_newsarticle():
    article = aggregated_article()
    assert not is_indexable_article(article)
    assert build_newsarticle_jsonld(article, BASE_URL + "news/example/") == ""


def test_original_editorial_requires_review_substantial_body_author_and_date():
    article = original_editorial_article()
    assert is_indexable_article(article)
    no_rss_summary = {**article, "summary": "", "thin": True}
    assert is_indexable_article(no_rss_summary)
    assert not is_indexable_article({**article, "editorial_reviewed": False})
    assert not is_indexable_article({**article, "editorial_content": "too short"})
    assert not is_indexable_article({**article, "author": ""})
    assert not is_indexable_article({**article, "author_type": "Unknown"})
    assert not is_indexable_article({**article, "published_at": "not-a-date"})


def test_newsarticle_schema_uses_editorial_modified_date_not_collection_time():
    article = original_editorial_article()
    schema = json.loads(build_newsarticle_jsonld(article, BASE_URL + "news/editorial/"))
    assert schema["@type"] == "NewsArticle"
    assert schema["author"]["name"] == "PikaNews Editorial Desk"
    assert schema["author"]["@type"] == "Organization"
    assert schema["datePublished"] == article["published_at"]
    assert "dateModified" not in schema
    article["modified_at"] = "2026-11-19T09:00:00+00:00"
    schema = json.loads(build_newsarticle_jsonld(article, BASE_URL + "news/editorial/"))
    assert schema["dateModified"] == article["modified_at"]
    article["modified_at"] = "2026-11-17T09:00:00+00:00"
    schema = json.loads(build_newsarticle_jsonld(article, BASE_URL + "news/editorial/"))
    assert "dateModified" not in schema


def test_aggregated_article_page_is_noindex_and_discloses_source():
    article = aggregated_article()
    page = build_page(article, [article], {article_slug(article["title"], article["id"])})
    assert '<meta name="robots" content="noindex, follow">' in page
    assert "Third-party source" in page
    assert "not original reporting by PikaNews" in page
    assert '"@type": "NewsArticle"' not in page
    assert '<script type="application/ld+json"></script>' not in page


def test_original_editorial_page_uses_editorial_body_and_does_not_claim_third_party_source():
    article = original_editorial_article()
    page = build_page(article, [article], {article_slug(article["title"], article["id"])})
    assert '<meta name="robots" content="index, follow">' in page
    assert article["editorial_content"] in page
    assert "Original editorial content by PikaNews" in page
    assert "PikaNews Editorial" in page
    assert "Third-party source" not in page
    assert "Read Original at" not in page
    assert "Collected" not in page
