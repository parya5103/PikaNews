"""Static regression checks for untrusted article IDs in frontend event attributes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_has_context_aware_javascript_string_escaping():
    utils = (ROOT / "frontend/js/utils.js").read_text(encoding="utf-8")
    assert "escapeJsString(value)" in utils
    assert "JSON.stringify(String(value ?? ''))" in utils
    assert "return this.escapeHtml(JSON.stringify(String(value ?? '')));" in utils


def test_article_ids_are_not_interpolated_into_quoted_javascript_strings():
    app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
    assert "'\u0024{article.id}'" not in app
    assert "Utils.escapeJsString(article.id)" in app
