"""Regression tests for generated PikaNews static article HTML."""

from scripts.generate_article_pages import article_slug, build_page
from scripts.validate_generated_articles import validate_generated_page


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
    article = aggregated_article()
    article.update({
        "id": "edit123456789",
        "content_type": "original_editorial",
        "editorial_reviewed": True,
        "editorial_content": "PikaNews original editorial analysis with verified context. " * 30,
        "author": "PikaNews Editorial Desk",
        "author_type": "Organization",
    })
    return article


def build(article):
    slug = article_slug(article["title"], article["id"])
    return build_page(article, [article], {slug})


def test_generated_aggregated_article_is_noindex_and_has_no_newsarticle_schema():
    article = aggregated_article()
    errors = validate_generated_page(article, build(article))
    assert errors == []


def test_generated_original_editorial_has_indexable_newsarticle_schema():
    article = original_editorial_article()
    errors = validate_generated_page(article, build(article))
    assert errors == []


def test_validator_detects_legacy_aggregate_schema_and_broken_category_breadcrumb():
    article = aggregated_article()
    stale = build(article)
    stale = stale.replace('content="noindex, follow"', 'content="index, follow"')
    stale = stale.replace('../../technology.html', '../../CATEGORY@@.html')
    stale = stale.replace(
        '</head>',
        '<script type="application/ld+json">{"@type":"NewsArticle"}</script></head>',
    )
    errors = validate_generated_page(article, stale)
    assert any("robots" in error.lower() for error in errors)
    assert any("newsarticle" in error.lower() for error in errors)
    assert any("breadcrumb" in error.lower() for error in errors)

def test_related_article_links_resolve_from_nested_article_directory():
    article = aggregated_article()
    related = aggregated_article()
    related.update({
        "id": "related123456",
        "title": "Another sufficiently descriptive related headline for navigation",
    })
    generated = {
        article_slug(article["title"], article["id"]),
        article_slug(related["title"], related["id"]),
    }
    html = build_page(article, [article, related], generated)

    assert f'href="../{article_slug(related["title"], related["id"])}/"' in html
    assert 'href="news/' not in html
