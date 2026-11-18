"""Indexation and structured-data policy for PikaNews articles."""

import json

from scripts.generate_article_pages import (
    BASE_URL,
    article_slug,
    build_newsarticle_jsonld,
    build_page,
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
    }


def original_editorial_article():
    return {
        **aggregated_article(),
        "id": "edit123456789",
        "content_type": "original_editorial",
        "editorial_reviewed": True,
        "editorial_content": ("PikaNews original editorial analysis. " * 20),
        "author": "PikaNews Editorial Desk",
    }


def test_third_party_aggregated_excerpt_is_not_indexable_or_newsarticle():
    article = aggregated_article()
    assert not is_indexable_article(article)
    assert build_newsarticle_jsonld(article, BASE_URL + "news/example/") == ""


def test_original_editorial_requires_review_substantial_body_author_and_date():
    article = original_editorial_article()
    assert is_indexable_article(article)
    assert not is_indexable_article({**article, "editorial_reviewed": False})
    assert not is_indexable_article({**article, "editorial_content": "too short"})
    assert not is_indexable_article({**article, "author": ""})
    assert not is_indexable_article({**article, "published_at": "not-a-date"})


def test_newsarticle_schema_uses_editorial_modified_date_not_collection_time():
    article = original_editorial_article()
    schema = json.loads(build_newsarticle_jsonld(article, BASE_URL + "news/editorial/"))
    assert schema["@type"] == "NewsArticle"
    assert schema["author"]["name"] == "PikaNews Editorial Desk"
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
