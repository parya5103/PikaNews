import pytest
from datetime import datetime
from parsers.feed import FeedParser
from parsers.html import HTMLParser

# Sample RSS feed response Mock
MOCK_RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>Entertainment Feed</title>
    <link>https://www.entertainment.com</link>
    <description>Latest Bollywood and Hollywood News</description>
    <item>
        <title>Mock Film Breaking News</title>
        <link>https://www.entertainment.com/news/mock-film-breaking-news</link>
        <pubDate>Wed, 20 May 2026 12:00:00 GMT</pubDate>
        <description>Exciting mock news about a superstar.</description>
        <category>Celebrity</category>
        <category>Movie</category>
    </item>
</channel>
</rss>
"""

# Sample HTML article Mock
MOCK_HTML_ARTICLE = """<!DOCTYPE html>
<html>
<head>
    <title>Mock Film Breaking News - Entertainment</title>
    <meta property="og:image" content="https://www.entertainment.com/images/mock-featured.jpg" />
    <meta property="article:published_time" content="2026-05-20T12:00:00+00:00" />
</head>
<body>
    <article class="article-content">
        <h1 class="article-title">Mock Film Breaking News</h1>
        <span class="author-name">John Doe</span>
        <div class="content-wrapper">
            <p>Superstar actor is signed for a new action movie franchise.</p>
            <p>Filming is scheduled to start late this summer in Mumbai.</p>
        </div>
        <div class="tags">
            <a href="/tag/bollywood">Bollywood</a>
            <a href="/tag/action">Action</a>
        </div>
        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
    </article>
</body>
</html>
"""

def test_feed_parser():
    source_config = {"name": "test_source", "industry": "bollywood"}
    items = FeedParser.parse(MOCK_RSS_FEED, source_config)
    
    assert len(items) == 1
    assert items[0]["title"] == "Mock Film Breaking News"
    assert items[0]["canonical_url"] == "https://www.entertainment.com/news/mock-film-breaking-news"
    assert isinstance(items[0]["published_at"], datetime)
    assert "Celebrity" in items[0]["tags"]

def test_html_parser_static():
    source_config = {
        "name": "test_source",
        "industry": "bollywood",
        "selectors": {
            "title": "h1.article-title",
            "author": "span.author-name",
            "body_text": ".content-wrapper p",
            "published_at": "meta[property='article:published_time']",
            "featured_image": "meta[property='og:image']"
        }
    }
    
    res = HTMLParser.parse_static(MOCK_HTML_ARTICLE, source_config, "https://www.entertainment.com/news/mock-film-breaking-news")
    
    assert res["title"] == "Mock Film Breaking News"
    assert res["author"] == "John Doe"
    assert "Superstar actor is signed" in res["body_text"]
    assert "Filming is scheduled" in res["body_text"]
    assert res["featured_image_url"] == "https://www.entertainment.com/images/mock-featured.jpg"
    assert len(res["video_embeds"]) == 1
    assert "https://www.youtube.com/embed/dQw4w9WgXcQ" in res["video_embeds"]
