import pytest
from pipelines.db import DatabasePipeline
from pipelines.nlp import NLPProcessor

def test_db_hash_generation():
    config = {}
    db = DatabasePipeline(config)
    
    title1 = "Breaking News! Superstar spotted in Mumbai"
    url1 = "https://variety.com/breaking-news-superstar?ref=tracker"
    
    title2 = "BREAKING NEWS! superstar spotted in mumbai"
    url2 = "https://variety.com/breaking-news-superstar"
    
    hash1 = db.calculate_hash(title1, url1)
    hash2 = db.calculate_hash(title2, url2)
    
    # Assert hash is normalized (case insensitive, alphanumeric only, strips query params)
    assert hash1 == hash2
    assert len(hash1) == 64

def test_tfidf_fallback_summarizer():
    processor = NLPProcessor({})
    title = "Shah Rukh Khan and Deepika Padukone Spotted in Mumbai for Pathaan Shoot"
    text = (
        "Superstar Shah Rukh Khan and actress Deepika Padukone were spotted in Mumbai. "
        "The stars are busy preparing for the high-octane action shoot of their upcoming film Pathaan. "
        "Fans gathered in large numbers to get a glimpse of their favorite celebrities. "
        "Security was tightened around the studio premises to avoid any disruption. "
        "Pathaan is one of the most anticipated films of the year and promises massive box office success. "
        "Directed by Siddharth Anand, the film also stars John Abraham in a pivotal role."
    )
    
    result = processor.extract_tfidf_fallback(title, text)
    assert result["summary"] is not None
    assert isinstance(result["tags"], list)
    
    # Summary should be extractive from the sentences
    assert "Shah Rukh Khan" in result["summary"] or "Pathaan" in result["summary"]
    # Tags should include high frequency / title terms (case insensitive matching)
    tags_lower = [t.lower() for t in result["tags"]]
    assert any("pathaan" in t or "shah" in t or "deepika" in t for t in tags_lower)

@pytest.mark.asyncio
async def test_ollama_fallback_to_tfidf():
    # Use invalid host to trigger immediate fallback connection error
    processor = NLPProcessor({"ollama": {"host": "http://invalid-ollama-host:9999", "model": "llama3"}})
    title = "Alia Bhatt Wins Best Actress Award"
    text = (
        "Alia Bhatt won the Best Actress award at the recent film festival. "
        "Her performance in the movie was highly acclaimed by critics and audiences alike. "
        "She thanked her director and the entire crew during her acceptance speech. "
        "This award marks another milestone in her successful career."
    )
    
    result = await processor.generate_summary_and_tags_via_ollama(title, text)
    assert result["summary"] is not None
    assert len(result["tags"]) > 0
    assert "Alia" in result["summary"] or "award" in result["summary"] or "Bhatt" in result["summary"]

