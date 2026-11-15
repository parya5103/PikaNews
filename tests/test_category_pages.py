"""Regression tests for PikaNews category-page SEO markup."""
from html import unescape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("bollywood", "hollywood", "entertainment", "technology", "gaming", "business", "sports", "latest")


def test_category_pages_have_unique_concise_metadata_and_single_intro():
    titles = set()
    for page in PAGES:
        html = (ROOT / "frontend" / f"{page}.html").read_text(encoding="utf-8")
        title_match = re.search(r"<title>(.*?)</title>", html, re.S)
        description_match = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
        assert title_match, f"{page}: missing title"
        assert description_match, f"{page}: missing meta description"
        title = unescape(title_match.group(1)).strip()
        description = unescape(description_match.group(1)).strip()
        assert title not in titles, f"{page}: duplicate title {title!r}"
        titles.add(title)
        assert 40 <= len(title) <= 65, f"{page}: title length {len(title)}"
        assert 120 <= len(description) <= 160, f"{page}: description length {len(description)}"
        assert len(re.findall(r"<h1\\b", html, re.I)) == 1, f"{page}: expected one H1"
        assert len(re.findall(r'<div class="category-intro">', html)) == 1, f"{page}: duplicate/missing intro"
        assert len(re.findall(r'<h2 class="section-title">', html)) == 1, f"{page}: duplicate/missing section heading"
        assert re.search(r'<link rel="canonical" href="https://gogocompany\\.in/pikanews/', html), f"{page}: missing canonical"
