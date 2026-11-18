"""Regression tests for PikaNews search snippets and static image fallbacks."""
import os


def test_category_pages_never_hide_broken_remote_images():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    pages = (
        "article.html", "bollywood.html", "hollywood.html", "entertainment.html",
        "business.html", "technology.html", "gaming.html", "sports.html",
        "latest.html", "trending.html",
    )
    for page in pages:
        with open(os.path.join(root, page), encoding="utf-8") as stream:
            html = stream.read()
        assert "this.style.display='none'" not in html, (
            f"{page} hides failed images instead of showing a local fallback"
        )
        if "onerror=" in html:
            assert "pikanews-logo.svg" in html, (
                f"{page} has an image error handler without the local logo fallback"
            )


def test_generated_article_title_and_description_fit_search_snippets():
    from scripts.generate_article_pages import build_page
    import re

    article = {
        "id": "seo-test-001",
        "title": "A Very Long Headline About Technology, Business, Entertainment and Sports News",
        "summary": "A short but meaningful publisher summary that should be expanded with the headline for search snippets.",
        "category": "technology",
        "source": "Example Publisher",
        "url": "https://example.com/story",
        "published_at": "2026-11-18T10:00:00Z",
        "collection_timestamp": "2026-11-18T10:10:00Z",
    }
    html = build_page(article, [article], set())
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    description = re.search(r'<meta name="description" content="(.*?)">', html, re.S).group(1)
    assert len(title) <= 50
    assert 70 <= len(description) <= 140
    assert "<h1" in html and article["title"] in html
