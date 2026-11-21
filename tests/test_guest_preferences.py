"""Static guardrails for the guest-first PikaNews topic feed."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_guest_preferences_have_no_login_or_server_dependency():
    script = (ROOT / "frontend" / "js" / "preferences.js").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'pikanews.preferences.v1' in script
    assert 'localStorage.getItem' in script
    assert 'localStorage.setItem' in script
    assert 'id="for-you-news"' in page
    assert 'id="preferences-modal"' in page
    assert 'id="preferences-toggle"' in page
    assert 'no account is required' in page
    assert 'js/preferences.js' in page
    assert page.index('js/app.js') < page.index('js/preferences.js')


def test_global_categories_are_discoverable_from_homepage():
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'href="world.html" class="category-card"' in page
    assert 'href="science.html" class="category-card"' in page
    assert 'id="for-you-news"' in page
