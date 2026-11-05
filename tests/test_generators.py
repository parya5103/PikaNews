#!/usr/bin/env python3
"""
Tests for PikaNews generators (sitemap, RSS).
"""

import os
import sys
import json
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_sitemap_generator():
    """Test sitemap generation."""
    from scripts.generate_sitemap import generate_sitemap, escape_xml
    
    print("Testing sitemap generator...")
    
    # Test XML escaping
    assert escape_xml("Test & text") == "Test &amp; text"
    assert escape_xml("<test>") == "&lt;test&gt;"
    assert escape_xml("'") == "&apos;"
    assert escape_xml('"') == "&quot;"
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up test environment
        original_sitemap_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "sitemap.xml")
        test_sitemap_path = os.path.join(tmpdir, "sitemap.xml")
        
        # Create test news_json directory
        news_json_dir = os.path.join(tmpdir, "news_json")
        os.makedirs(news_json_dir)
        
        # Create test articles
        test_articles = [
            {
                "id": "test1",
                "title": "Test Article 1",
                "category": "technology",
                "published_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "test2",
                "title": "Test Article 2",
                "category": "sports",
                "published_at": "2024-01-02T00:00:00Z"
            }
        ]
        
        with open(os.path.join(news_json_dir, "all_articles.json"), "w") as f:
            json.dump(test_articles, f)
        
        # Mock the paths
        import scripts.generate_sitemap as sitemap_module
        original_news_json_dir = sitemap_module.NEWS_JSON_DIR
        original_sitemap_path = sitemap_module.SITEMAP_PATH
        
        sitemap_module.NEWS_JSON_DIR = news_json_dir
        sitemap_module.SITEMAP_PATH = test_sitemap_path
        
        try:
            # Generate sitemap
            xml_content = generate_sitemap()
            
            # Check file was created
            assert os.path.exists(test_sitemap_path)
            
            # Check XML content
            with open(test_sitemap_path, "r") as f:
                content = f.read()
                assert "<?xml version=" in content
                assert "<urlset" in content
                assert "</urlset>" in content
                assert "index.html" in content
                assert "latest.html" in content
                assert "article.html?id=test1" in content
                assert "article.html?id=test2" in content
            
            print("  ✓ Sitemap generation test passed")
            
        finally:
            # Restore original paths
            sitemap_module.NEWS_JSON_DIR = original_news_json_dir
            sitemap_module.SITEMAP_PATH = original_sitemap_path


def test_rss_generator():
    """Test RSS feed generation."""
    from scripts.generate_rss import generate_rss_feed, escape_xml
    
    print("Testing RSS generator...")
    
    # Test XML escaping
    assert escape_xml("Test & text") == "Test &amp; text"
    assert escape_xml("<test>") == "&lt;test&gt;"
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up test environment
        test_rss_path = os.path.join(tmpdir, "feed.xml")
        
        # Create test news_json directory
        news_json_dir = os.path.join(tmpdir, "news_json")
        os.makedirs(news_json_dir)
        
        # Create test articles
        test_articles = [
            {
                "id": "test1",
                "title": "Test Article 1",
                "summary": "Test summary 1",
                "category": "technology",
                "source": "Test Source",
                "published_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "test2",
                "title": "Test Article 2",
                "summary": "Test summary 2",
                "category": "sports",
                "source": "Test Source 2",
                "published_at": "2024-01-02T00:00:00Z"
            }
        ]
        
        with open(os.path.join(news_json_dir, "all_articles.json"), "w") as f:
            json.dump(test_articles, f)
        
        # Mock the paths
        import scripts.generate_rss as rss_module
        original_news_json_dir = rss_module.NEWS_JSON_DIR
        original_rss_path = rss_module.RSS_PATH
        
        rss_module.NEWS_JSON_DIR = news_json_dir
        rss_module.RSS_PATH = test_rss_path
        
        try:
            # Generate RSS feed
            xml_content = generate_rss_feed()
            
            # Check file was created
            assert os.path.exists(test_rss_path)
            
            # Check XML content
            with open(test_rss_path, "r") as f:
                content = f.read()
                assert "<?xml version=" in content
                assert "<rss version=" in content
                assert "<channel>" in content
                assert "</channel>" in content
                assert "PikaNews" in content
                assert "Test Article 1" in content
                assert "Test Article 2" in content
            
            print("  ✓ RSS generation test passed")
            
        finally:
            # Restore original paths
            rss_module.NEWS_JSON_DIR = original_news_json_dir
            rss_module.RSS_PATH = original_rss_path


def test_url_construction():
    """Test URL construction in generators."""
    from urllib.parse import urljoin
    
    print("Testing URL construction...")
    
    base_url = "https://gogocompany.in/pikanews/"
    
    # Test various URL joins
    assert urljoin(base_url, "article.html?id=test") == "https://gogocompany.in/pikanews/article.html?id=test"
    assert urljoin(base_url, "index.html") == "https://gogocompany.in/pikanews/index.html"
    assert urljoin(base_url, "") == "https://gogocompany.in/pikanews/"
    
    print("  ✓ URL construction test passed")


def run_tests():
    """Run all generator tests."""
    print("=" * 60)
    print("PIKANEWS GENERATOR TESTS")
    print("=" * 60)
    print()
    
    try:
        test_sitemap_generator()
        test_rss_generator()
        test_url_construction()
        
        print()
        print("=" * 60)
        print("ALL GENERATOR TESTS PASSED")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
