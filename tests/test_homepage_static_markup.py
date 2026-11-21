from pathlib import Path


def test_homepage_has_one_renderable_discovery_section():
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")

    assert html.count('<section class="news-discovery"') == 1
    assert html.count('id="news-discovery-title"') == 1
    assert r'\n        <section class="news-discovery"' not in html


def test_homepage_does_not_leak_escaped_newline_tokens_into_markup():
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")

    assert r"</p>\n                    <p" not in html


def test_shared_frontend_loads_the_gogo_analytics_container():
    app = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert "GTM-TH4NX8MH" in app
    assert "event: 'gtm.js'" in app
