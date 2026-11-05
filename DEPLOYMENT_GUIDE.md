# PikaNews Deployment Guide

## Overview

PikaNews is a fully automated, self-updating news website that:
- Collects news from multiple reliable RSS feeds every 30 minutes
- Categorizes articles automatically
- Serves a professional, mobile-first responsive website
- Requires **zero manual maintenance** after setup
- Uses **100% free** services (GitHub Pages + GitHub Actions)

## Quick Start

### 1. Enable GitHub Pages

1. Go to your repository on GitHub: https://github.com/parya5103/PikaNews
2. Click **Settings** > **Pages**
3. Under "Source", select **GitHub Actions**
4. Click **Save**

Your site will be live at: `https://parya5103.github.io/PikaNews/`

### 2. Verify the Workflow is Running

1. Go to **Actions** tab in your repository
2. Check that the "PikaNews Automatic News Collector" workflow is running
3. The workflow runs automatically every 30 minutes
4. You can also trigger it manually by clicking **Run workflow** > **Run workflow**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Free)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  News Collector │  │ Sitemap Generator│  │ RSS Generator│ │
│  │  (fetch_news)   │  │(generate_sitemap)│  │(generate_rss)│ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
└───────────┼─────────────────────┼─────────────────────┼─────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 GitHub Repository (Free)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  news_json/     │  │ frontend/       │  │ data/        │ │
│  │  all_articles   │  │ index.html      │  │ stats.json   │ │
│  │  bollywood.json  │  │ latest.html     │  │ failed_      │ │
│  │  hollywood.json  │  │ ...             │  │ sources.json │ │
│  │  ...             │  │ sitemap.xml     │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                 GitHub Pages (Free)                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  https://parya5103.github.io/PikaNews/                 │ │
│  │  - Static HTML/CSS/JS files                             │ │
│  │  - JSON data files                                       │ │
│  │  - XML sitemap and RSS feed                              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## News Sources

PikaNews collects from these verified RSS feeds:

### Bollywood
- Pinkvilla
- Filmfare
- Times of India Bollywood

### Hollywood
- Variety
- Deadline
- Hollywood Reporter

### Entertainment
- Billboard
- Rolling Stone

### Technology
- TechCrunch
- The Verge
- Ars Technica Gadgets

### Gaming
- IGN
- GameSpot
- Polygon

### Business
- Reuters Business
- CNBC

### Sports
- ESPN
- BBC Sport

### Trending
- BuzzFeed World
- Reddit Popular

## Features

### Automatic News Collection
- ✅ Runs every 30 minutes via GitHub Actions
- ✅ Fetches from 20+ reliable RSS feeds
- ✅ Categorizes articles automatically
- ✅ Removes duplicates
- ✅ Handles failures gracefully
- ✅ Retries failed requests

### Professional Website
- ✅ Mobile-first responsive design
- ✅ Light and dark theme
- ✅ 8 news categories
- ✅ Featured stories carousel
- ✅ Search functionality
- ✅ Category filtering
- ✅ Bookmarking (localStorage)
- ✅ Share functionality (Web Share API)
- ✅ Smooth animations

### SEO
- ✅ XML sitemap (auto-generated)
- ✅ RSS feed (auto-generated)
- ✅ robots.txt
- ✅ Open Graph metadata
- ✅ Twitter card metadata
- ✅ Structured data (JSON-LD)
- ✅ Canonical URLs
- ✅ Clean, readable URLs

### Performance & Security
- ✅ Lazy-loaded images
- ✅ No tracking or analytics
- ✅ XSS protection
- ✅ Safe DOM rendering
- ✅ No external API dependencies

## File Structure

```
PikaNews/
├── frontend/                  # Static website files
│   ├── *.html                # HTML pages
│   ├── css/                  # Stylesheets
│   │   └── styles.css        # Main stylesheet
│   ├── js/                   # JavaScript
│   │   ├── app.js            # Main application
│   │   ├── data.js           # Data management
│   │   └── utils.js          # Utility functions
│   ├── images/               # Static images
│   │   ├── pikanews-logo.png
│   │   ├── favicon.png
│   │   └── ...
│   ├── sitemap.xml           # SEO sitemap
│   ├── feed.xml              # RSS feed
│   └── robots.txt           # Crawler instructions
│
├── news_json/                 # Article data
│   ├── all_articles.json     # All articles
│   ├── latest.json           # Latest 100 articles
│   ├── trending.json         # Trending articles
│   ├── bollywood.json        # Bollywood articles
│   ├── hollywood.json        # Hollywood articles
│   ├── entertainment.json    # Entertainment articles
│   ├── technology.json       # Technology articles
│   ├── gaming.json           # Gaming articles
│   ├── business.json         # Business articles
│   └── sports.json           # Sports articles
│
├── data/                      # Metadata
│   ├── stats.json            # Collection statistics
│   └── failed_sources.json    # Failed source tracking
│
├── scripts/                   # Python scripts
│   ├── fetch_news.py         # News collection engine
│   ├── generate_sitemap.py   # Sitemap generator
│   └── generate_rss.py       # RSS feed generator
│
├── .github/workflows/         # GitHub Actions
│   └── news_collector.yml    # Scheduled workflow
│
├── tests/                     # Test suite
│   ├── test_news_collector.py
│   └── test_generators.py
│
├── README.md                  # Project documentation
├── DEPLOYMENT_GUIDE.md        # This file
└── config.yaml                # Configuration (legacy)
```

## Configuration

### News Collection
The news collector is configured in `scripts/fetch_news.py` with:
- **RSS_FEEDS**: List of feeds to fetch from
- **CATEGORY_KEYWORDS**: Keywords for categorization
- **MAX_ARTICLES_PER_CATEGORY**: Limit per category (500)
- **MAX_TOTAL_ARTICLES**: Total limit (2000)

### GitHub Actions
The workflow is configured in `.github/workflows/news_collector.yml`:
- **Schedule**: Every 30 minutes (`*/30 * * * *`)
- **Permissions**: Read/write to repository
- **Lock mechanism**: Prevents overlapping runs

## Manual Operations

### Force News Collection
```bash
# Run locally
python scripts/fetch_news.py

# Or trigger via GitHub Actions
# Go to Actions > News Collector > Run workflow
```

### Regenerate Sitemap
```bash
python scripts/generate_sitemap.py
```

### Regenerate RSS Feed
```bash
python scripts/generate_rss.py
```

### Run Tests
```bash
# Run all tests
python tests/test_news_collector.py
python tests/test_generators.py

# Or run individually
python -m pytest tests/ -v
```

## Customization

### Add a New News Source
Edit `scripts/fetch_news.py` and add to `RSS_FEEDS`:

```python
RSS_FEEDS = {
    # ... existing categories ...
    "new_category": [
        {
            "url": "https://example.com/feed",
            "name": "Example News",
            "category": "new_category",
            "language": "en",
            "enabled": True,
            "priority": 1
        }
    ]
}
```

### Add a New Category
1. Add to `RSS_FEEDS` dictionary
2. Add keywords to `CATEGORY_KEYWORDS`
3. Create a new HTML page in `frontend/`

### Change Theme Colors
Edit CSS variables in `frontend/css/styles.css`:

```css
:root {
    --color-primary: #2563eb;
    --color-secondary: #7c3aed;
    /* ... */
}
```

## Troubleshooting

### GitHub Pages Not Deploying
1. Check **Settings > Pages** - ensure GitHub Actions is selected
2. Check **Actions** tab for workflow errors
3. Ensure the workflow has **write** permissions

### News Not Updating
1. Check **Actions** tab for workflow runs
2. Look for errors in the workflow logs
3. Check `data/failed_sources.json` for failed feeds
4. Run `python scripts/fetch_news.py` locally to test

### Missing Images
- Some news sources don't provide images in their RSS feeds
- The system gracefully handles missing images with placeholders
- To improve: Add image extraction from article content

### Categorization Issues
- The categorization is keyword-based
- Edit `CATEGORY_KEYWORDS` in `scripts/fetch_news.py` to improve
- Add more keywords for better matching

## Monitoring

### Check Latest Collection
```bash
# View collection stats
cat data/stats.json

# View failed sources
cat data/failed_sources.json

# View article count
python -c "import json; print(len(json.load(open('news_json/all_articles.json'))))"
```

### View Workflow Logs
1. Go to **Actions** tab
2. Click on the latest workflow run
3. Expand each step to see logs

## Performance Tips

### Reduce Repository Size
```bash
# Remove old logs
rm -rf logs/

# Remove old data backups
rm -f data/*.backup

# GitHub automatically handles large files
# But keeping data files small helps
```

### Optimize Images
- The system doesn't download or store images
- Images are loaded directly from source URLs
- This keeps the repository lightweight

## Security

### No Secrets Required
- PikaNews doesn't use any API keys
- All data comes from public RSS feeds
- No authentication needed

### Safe Content Handling
- All content is sanitized before display
- XSS protection is built-in
- No `innerHTML` with untrusted content

## Cost

**$0.00** - PikaNews uses only free services:
- GitHub Pages (Free)
- GitHub Actions (Free for public repos)
- RSS feeds (Free, public)

## Support

For issues or questions:
1. Check this deployment guide
2. Review the workflow logs in GitHub Actions
3. Run tests locally to identify issues
4. Open an issue on GitHub with details

## License

PikaNews is free and open source. Feel free to use, modify, and distribute.

---

**Enjoy your automatic news website!** 🎉

The site will automatically update every 30 minutes with fresh news from all configured sources.
