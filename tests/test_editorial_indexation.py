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
    assert "PikaNews original editorial analysis." in page.split("<div class=\"article-body\">", 1)[1]
    assert "Original editorial content by PikaNews" in page
    assert "PikaNews Editorial" in page
    assert "Third-party source" not in page
    assert "Read Original at" not in page
    assert "Collected" not in page



def test_dynamic_article_fallback_keeps_aggregated_items_noindex_without_newsarticle_schema():
    from pathlib import Path

    fallback = (Path(__file__).resolve().parents[1] / "frontend" / "article.html").read_text(encoding="utf-8")
    assert "function isIndexableOriginalEditorial(article)" in fallback
    assert "indexableEditorial ? 'index, follow' : 'noindex, follow'" in fallback
    assert "if (indexableEditorial) injectArticleSchema(article)" in fallback
    assert "if (!isIndexableOriginalEditorial(article)) return;" in fallback
    assert "article.editorial_content" in fallback


def test_homepage_is_indexable_and_uses_pikanews_channel_only():
    from pathlib import Path

    homepage = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="index,follow">' in homepage
    assert "https://whatsapp.com/channel/0029Vb5zVwjICVfnQ95zT10F" in homepage
    assert "https://whatsapp.com/channel/0029VbE1ulAAjPXQZiUbbu1Z" not in homepage
    assert "Follow on WhatsApp" in homepage


def test_generated_and_dynamic_story_pages_offer_pikanews_follow_link():
    from pathlib import Path

    article = aggregated_article()
    generated = build_page(article, [article], {article_slug(article["title"], article["id"])})
    fallback = (Path(__file__).resolve().parents[1] / "frontend" / "article.html").read_text(encoding="utf-8")
    channel = "https://whatsapp.com/channel/0029Vb5zVwjICVfnQ95zT10F"
    assert channel in generated
    assert 'aria-label="Follow PikaNews on WhatsApp"' in generated
    assert channel in fallback
    assert 'aria-label="Follow PikaNews on WhatsApp"' in fallback


def test_root_listing_robots_never_noindexes_the_discovery_homepage(tmp_path):
    from scripts.generate_article_pages import update_root_listing_robots

    homepage = tmp_path / "index.html"
    trending = tmp_path / "trending.html"
    homepage.write_text('<html><head><meta name="robots" content="index,follow"></head></html>', encoding="utf-8")
    trending.write_text('<html><head><meta name="robots" content="index,follow"></head></html>', encoding="utf-8")

    update_root_listing_robots([], frontend_dir=str(tmp_path))

    assert 'content="index,follow"' in homepage.read_text(encoding="utf-8")
    assert 'content="noindex,follow"' in trending.read_text(encoding="utf-8")


def test_category_cards_beyond_base_cap_get_unique_static_article_pages(tmp_path, monkeypatch):
    import json
    from scripts import generate_article_pages as generator

    data_dir = tmp_path / "data"
    frontend_dir = tmp_path / "frontend"
    news_dir = frontend_dir / "news"
    data_dir.mkdir()
    frontend_dir.mkdir()
    articles = [
        {
            "id": "tech00000001",
            "title": "Recent technology story with a sufficiently long headline",
            "summary": "A sufficiently detailed summary for the technology story. " + ("Details " * 8),
            "category": "technology",
            "source": "Tech Publisher",
            "url": "https://example.com/tech",
            "published_at": "2026-11-21T10:00:00+00:00",
        },
        {
            "id": "world0000002",
            "title": "Older international affairs story with a sufficiently long headline",
            "summary": "A sufficiently detailed summary for the world story. " + ("Details " * 8),
            "category": "world",
            "source": "World Publisher",
            "url": "https://example.com/world",
            "published_at": "2026-11-18T10:00:00+00:00",
        },
    ]
    (data_dir / "all_articles.json").write_text(json.dumps(articles), encoding="utf-8")
    (frontend_dir / "world.html").write_text(
        '<html><head><meta name="robots" content="noindex,follow"></head>'
        '<body><div id="world-news"></div></body></html>',
        encoding="utf-8",
    )
    monkeypatch.setattr(generator, "NEWS_JSON_DIR", str(data_dir))
    monkeypatch.setattr(generator, "NEWS_DIR", str(news_dir))
    monkeypatch.setattr(generator, "REMOVED_ARTICLES_FILE", str(tmp_path / "removed.json"))
    monkeypatch.setattr(generator, "MAX_ARTICLES", 1)
    monkeypatch.setattr(generator, "MAX_CATEGORY_STATIC_ARTICLES", 1)
    monkeypatch.setattr(generator, "CATEGORY_PAGE_FILTERS", {"world": {"world"}})
    monkeypatch.setattr(generator, "update_root_listing_robots", lambda articles: None)

    assert generator.generate_article_pages() == 2
    slug = generator.article_slug(articles[1]["title"], articles[1]["id"])
    assert (news_dir / slug / "index.html").is_file()
    category_html = (frontend_dir / "world.html").read_text(encoding="utf-8")
    assert f'href="news/{slug}/"' in category_html
    assert "article.html?id=world0000002" not in category_html

