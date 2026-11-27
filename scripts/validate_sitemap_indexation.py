#!/usr/bin/env python3
"""Verify every URL advertised by PikaNews sitemaps is locally indexable."""
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

BASE_URL = "https://gogocompany.in/pikanews/"
FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
SITEMAPS = [
    os.path.join(FRONTEND, "sitemap.xml"),
    os.path.join(FRONTEND, "news-sitemap.xml"),
]


def local_page_for_url(url):
    parsed = urlparse(url)
    base = urlparse(BASE_URL)
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
        raise ValueError(f"URL is outside the PikaNews canonical host: {url}")
    prefix = base.path.rstrip("/") + "/"
    if not parsed.path.startswith(prefix):
        raise ValueError(f"URL is outside the PikaNews path: {url}")
    relative = unquote(parsed.path[len(prefix):])
    if not relative:
        relative = "index.html"
    elif relative.endswith("/"):
        relative += "index.html"
    frontend_root = os.path.realpath(FRONTEND)
    path = os.path.realpath(os.path.join(FRONTEND, relative))
    if os.path.commonpath([frontend_root, path]) != frontend_root:
        raise ValueError(f"URL resolves outside frontend: {url}")
    return path


def validate_sitemaps():
    failures = []
    checked = 0
    for sitemap in SITEMAPS:
        seen = set()
        if not os.path.isfile(sitemap):
            failures.append(f"Missing sitemap: {sitemap}")
            continue
        try:
            root = ET.parse(sitemap).getroot()
        except ET.ParseError as exc:
            failures.append(f"Invalid XML in {sitemap}: {exc}")
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
                continue
            url = node.text.strip()
            if url in seen:
                failures.append(f"Duplicate sitemap URL: {url}")
                continue
            seen.add(url)
            try:
                page_path = local_page_for_url(url)
            except ValueError as exc:
                failures.append(str(exc))
                continue
            if not os.path.isfile(page_path):
                failures.append(f"Sitemap URL has no generated page: {url}")
                continue
            with open(page_path, encoding="utf-8") as handle:
                page_html = handle.read()
            robots = re.search(r"<meta\s+name=['\"]robots['\"]\s+content=['\"]([^'\"]+)", page_html, re.I)
            if robots and "noindex" in robots.group(1).casefold():
                failures.append(f"Sitemap URL is marked noindex: {url}")
            canonical = re.search(r"<link\s+rel=['\"]canonical['\"]\s+href=['\"]([^'\"]+)", page_html, re.I)
            if not canonical:
                failures.append(f"Sitemap page has no canonical link: {url}")
            elif canonical.group(1).strip().rstrip("/") != url.rstrip("/"):
                failures.append(f"Canonical does not match sitemap URL: {url} -> {canonical.group(1)}")
            checked += 1
    if failures:
        for item in failures:
            print("ERROR:", item)
        raise RuntimeError(f"Sitemap indexation validation failed: {len(failures)} issue(s), {checked} URL(s) checked")
    print(f"Sitemap indexation validation passed: {checked} URL(s) checked.")
    return checked


if __name__ == "__main__":
    try:
        validate_sitemaps()
    except Exception as exc:
        print(f"Sitemap validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
