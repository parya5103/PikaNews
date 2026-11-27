"""Sitemap indexation validator tests."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_sitemap_indexation.py"
SPEC = importlib.util.spec_from_file_location("validate_sitemap_indexation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sitemap_url_maps_to_static_html_page():
    assert MODULE.local_page_for_url("https://gogocompany.in/pikanews/technology.html").endswith("frontend/technology.html")


def test_sitemap_url_maps_trailing_slash_to_index_html():
    assert MODULE.local_page_for_url("https://gogocompany.in/pikanews/news/example-story/").endswith("frontend/news/example-story/index.html")


def test_sitemap_url_rejects_external_and_path_escape():
    import pytest
    with pytest.raises(ValueError):
        MODULE.local_page_for_url("https://evil.example/pikanews/")
    with pytest.raises(ValueError):
        MODULE.local_page_for_url("https://gogocompany.in/pikanews/../../secret")
