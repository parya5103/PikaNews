"""Small, deterministic topic rules for the PikaNews collector.

No network calls, model downloads, paid APIs or runtime model dependencies.
Publisher identity is deliberately not treated as article-topic evidence.
"""

import re
from typing import Dict, Iterable, Tuple


TOPIC_RULES: Dict[str, Tuple[str, ...]] = {
    "politics": (
        "election", "parliament", "congress", "senate", "prime minister",
        "president", "government", "cabinet", "minister", "opposition",
        "political party", "campaign", "vote", "voting", "un security council",
        "united nations", "diplomacy", "sanctions", "ceasefire", "summit",
    ),
    "science": (
        "scientist", "scientists", "researchers", "research study", "study finds",
        "nasa", "space agency", "astronomy", "exoplanet", "quantum",
        "particle physics", "archaeology", "fossil", "discovery",
    ),
    "health": (
        "health", "healthcare", "hospital", "doctor", "doctors", "patient",
        "patients", "disease", "outbreak", "vaccine", "vaccination", "who",
        "world health organization", "clinical trial", "medicine", "medical",
    ),
    "climate": (
        "climate", "global warming", "emissions", "carbon", "renewable energy",
        "wildfire", "heatwave", "flood", "flooding", "drought", "biodiversity",
        "environment", "pollution",
    ),
    "technology": (
        "technology", "tech", "artificial intelligence", "ai", "software",
        "cybersecurity", "smartphone", "chip", "semiconductor", "robotics",
        "google", "microsoft", "apple", "samsung", "open source",
    ),
    "business": (
        "business", "economy", "economic", "central bank", "interest rate",
        "inflation", "stock market", "shares", "earnings", "revenue",
        "investment", "investor", "trade deal", "company", "startup",
        "bank", "finance", "currency",
    ),
    "sports": (
        "sports", "football", "soccer", "cricket", "basketball", "tennis",
        "champions league", "premier league", "world cup", "olympics",
        "formula 1", "grand prix", "match", "tournament", "athlete",
    ),
    "gaming": (
        "video game", "video games", "gaming", "playstation", "xbox",
        "nintendo", "switch game", "steam", "esports", "game release",
        "game update", "gta", "minecraft", "fortnite",
    ),
    "bollywood": (
        "bollywood", "hindi cinema", "hindi film", "indian film industry",
    ),
    "hollywood": (
        "hollywood", "oscars", "academy awards", "emmy awards",
    ),
    "entertainment": (
        "entertainment", "movie", "film", "actor", "actress", "celebrity",
        "tv series", "television", "streaming", "netflix", "album", "concert",
        "music", "box office", "film festival",
    ),
}

_TITLE_WEIGHT = 5
_SUMMARY_WEIGHT = 1
_SOURCE_CATEGORY_WEIGHT = 1


def _normalise(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " " + " ".join(text.split()) + " "


def _phrase_hits(text: str, phrases: Iterable[str]) -> int:
    return sum(1 for phrase in phrases if " " + phrase.strip().casefold() + " " in text)


def classify_article(
    title: str,
    description: str = "",
    source_name: str = "",
    source_category: str = "",
    source_url: str = "",
) -> str:
    """Choose a topic from article text; source metadata is only a weak fallback."""
    title_text = _normalise(title)
    summary_text = _normalise(description)
    if not title_text.strip():
        return str(source_category or "world").strip().casefold()

    scores = {}
    for category, phrases in TOPIC_RULES.items():
        title_hits = _phrase_hits(title_text, phrases)
        summary_hits = _phrase_hits(summary_text, phrases)
        score = title_hits * _TITLE_WEIGHT + summary_hits * _SUMMARY_WEIGHT
        if category == str(source_category or "").strip().casefold():
            score += _SOURCE_CATEGORY_WEIGHT
        if score:
            scores[category] = (score, title_hits, summary_hits)

    if scores:
        selected = sorted(
            scores,
            key=lambda category: (
                -scores[category][1],
                -scores[category][0],
                category,
            ),
        )[0]
        # These are world-news subtopics, not standalone public feeds.
        return "world" if selected in {"politics", "health", "climate"} else selected

    fallback = str(source_category or "").strip().casefold()
    return "world" if fallback in {"politics", "health", "climate"} else (fallback or "world")
