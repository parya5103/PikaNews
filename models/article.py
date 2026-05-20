from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator

class Article(BaseModel):
    title: str = Field(..., description="Normalized title of the article")
    subtitle: Optional[str] = Field(None, description="Article subtitle or subheading")
    author: Optional[str] = Field("Unknown", description="Author of the article")
    published_at: datetime = Field(..., description="Timezone-aware ISO 8601 published date")
    source: str = Field(..., description="Scraping source name (e.g. pinkvilla, variety)")
    category: str = Field("movie", description="Category: movie/TV/celebrity/award/box-office")
    industry: str = Field(..., description="Industry: bollywood/hollywood")
    tags: List[str] = Field(default_factory=list, description="Extracted or source tags")
    body_text: str = Field(..., description="Clean plain text body of the article")
    body_html: Optional[str] = Field(None, description="Original safe HTML structure of the body")
    featured_image_url: Optional[HttpUrl] = Field(None, description="Featured main image URL")
    gallery_urls: List[HttpUrl] = Field(default_factory=list, description="List of image URLs in media galleries")
    video_embeds: List[str] = Field(default_factory=list, description="List of video embed links (YouTube, Vimeo etc.)")
    canonical_url: HttpUrl = Field(..., description="Canonical source URL of the article")
    
    # Computed metrics
    word_count: int = Field(0, description="Word count of plain body text")
    reading_time_min: int = Field(0, description="Estimated reading time in minutes")
    
    # NLP enrichment
    entities: Dict[str, List[str]] = Field(
        default_factory=lambda: {"actors": [], "films": [], "studios": [], "others": []},
        description="Extracted Named Entities"
    )
    sentiment: str = Field("neutral", description="Sentiment buzz: positive/neutral/negative")
    sentiment_score: float = Field(0.0, description="Compound sentiment score")
    summary: Optional[str] = Field(None, description="Ollama-generated 3-sentence TL;DR summary")
    language: str = Field("en", description="Auto-detected language code (e.g., en, hi)")

    # Perceptual hashes for featured image
    image_phash: Optional[str] = Field(None, description="Perceptual hash of the featured image")
    local_image_paths: Dict[str, str] = Field(
        default_factory=dict, 
        description="Local storage paths for image variants (thumbnail, medium, full)"
    )

    @field_validator("published_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Any) -> datetime:
        if isinstance(v, str):
            # Parse ISO string
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                # Try fallback standard parse
                dt = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("published_at must be an ISO datetime string or datetime object")
        
        if dt.tzinfo is None:
            import pytz
            dt = pytz.utc.localize(dt)
        return dt

    @field_validator("title", "body_text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    def calculate_reading_time(self) -> None:
        """Calculate word count and estimated reading time (200 WPM average)."""
        words = self.body_text.split()
        self.word_count = len(words)
        self.reading_time_min = max(1, round(self.word_count / 200))
