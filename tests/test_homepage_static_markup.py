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


def test_homepage_metadata_describes_publisher_attributed_discovery_feed():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "<title>PikaNews: Global Headlines &amp; Original Sources</title>" in html
    assert "Every story links to its original publisher." in html
    assert '"@type": "WebSite"' in html
    assert '"@type": "NewsMediaOrganization"' not in html
    assert "PikaNews: Global Headlines with Original Source Links" in html


def test_latest_and_terms_descriptions_are_not_truncated_or_too_short():
    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1] / "frontend"
    for page, minimum, maximum in (("latest.html", 70, 160), ("terms.html", 70, 160)):
        html = (root / page).read_text(encoding="utf-8")
        match = re.search(r'<meta name="description" content="([^"]+)"', html)
        assert match, f"{page} is missing a description"
        assert minimum <= len(match.group(1)) <= maximum, f"{page} description length is {len(match.group(1))}"


