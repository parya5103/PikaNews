"""Regression tests for public PikaNews image fallback paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_PAGES = (
    "entertainment.html",
    "gaming.html",
    "sports.html",
    "business.html",
    "latest.html",
    "hollywood.html",
    "technology.html",
)


def test_root_category_pages_use_root_relative_logo_fallbacks():
    for page in CATEGORY_PAGES:
        html = (ROOT / "frontend" / page).read_text(encoding="utf-8")
        assert "images/pikanews-logo.svg" in html, page
        assert "../../images/pikanews-logo.svg" not in html, page


def test_dynamic_article_reader_does_not_hide_broken_image_slots():
    html = (ROOT / "frontend" / "article.html").read_text(encoding="utf-8")
    assert "this.onerror=null;this.src='images/pikanews-logo.svg'" in html
    assert "this.style.display='none'" not in html
