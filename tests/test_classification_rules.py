"""Deterministic, dependency-free topic classification tests for PikaNews."""

from scripts.classification_rules import classify_article


def test_specific_title_signal_overrides_publisher_section():
    assert classify_article(
        "NASA discovers a new exoplanet", "The space agency announced the finding.",
        source_name="Variety", source_category="hollywood",
    ) == "science"


def test_topic_is_not_inferred_from_unrelated_publisher_brand():
    assert classify_article(
        "Central bank holds interest rates steady", "Officials cited inflation risks.",
        source_name="TechCrunch", source_category="technology",
    ) == "business"


def test_world_politics_and_health_topics_are_supported():
    assert classify_article("UN Security Council calls emergency meeting", "") == "politics"
    assert classify_article("WHO issues new public health guidance", "") == "health"


def test_sports_and_gaming_are_distinguished():
    assert classify_article("Champions League final ends in dramatic draw", "") == "sports"
    assert classify_article("Nintendo announces a new Switch game", "") == "gaming"


def test_source_category_is_only_a_fallback_when_text_has_no_signal():
    assert classify_article("A major announcement is expected soon", "", source_category="technology") == "technology"


def test_unknown_story_defaults_to_world_not_entertainment_or_trending():
    assert classify_article("Officials confirm an update", "") == "world"


def test_title_signal_outweighs_weak_summary_noise():
    assert classify_article(
        "Scientists publish a new climate study",
        "The article mentions a business conference and a film premiere.",
    ) == "science"
