import os
import re
import asyncio
import httpx
from typing import Dict, List, Optional, Any
from textblob import TextBlob
from langdetect import detect
import structlog

logger = structlog.get_logger(__name__)

# Initialize spaCy globally (fallback if model not found)
nlp_model = None
try:
    import spacy
    try:
        nlp_model = spacy.load("en_core_web_sm")
    except OSError:
        logger.info("spaCy model 'en_core_web_sm' not found. Attempting to download...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        nlp_model = spacy.load("en_core_web_sm")
except Exception as e:
    logger.warn("Could not initialize spaCy model. Will use fallback entity extractor.", error=str(e))


class NLPProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ollama_host = os.getenv("OLLAMA_HOST") or config.get("ollama", {}).get("host", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL") or config.get("ollama", {}).get("model", "llama3")

    def detect_lang(self, text: str) -> str:
        """Detect language of the text. Fallback to English."""
        if not text or len(text.strip()) < 10:
            return "en"
        try:
            return detect(text[:1000])
        except Exception:
            return "en"

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Perform sentiment analysis using TextBlob."""
        if not text:
            return {"sentiment": "neutral", "score": 0.0}
        
        try:
            blob = TextBlob(text[:2000])  # Scan first 2000 chars
            polarity = blob.sentiment.polarity
            
            if polarity > 0.15:
                sentiment = "positive"
            elif polarity < -0.15:
                sentiment = "negative"
            else:
                sentiment = "neutral"
                
            return {
                "sentiment": sentiment,
                "score": round(polarity, 2)
            }
        except Exception as e:
            logger.warn("Sentiment analysis failed, using neutral fallback", error=str(e))
            return {"sentiment": "neutral", "score": 0.0}

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract movie/TV entities (Actors, Studios, Films) from text using spaCy."""
        entities = {"actors": [], "films": [], "studios": [], "others": []}
        if not text:
            return entities

        # If spaCy loaded successfully
        if nlp_model:
            try:
                doc = nlp_model(text[:5000])  # Process first 5k characters for performance
                for ent in doc.ents:
                    val = ent.text.strip()
                    if len(val) < 2:
                        continue
                    
                    if ent.label_ == "PERSON":
                        if val not in entities["actors"]:
                            entities["actors"].append(val)
                    elif ent.label_ in ["ORG", "NORP"]:
                        if val not in entities["studios"]:
                            entities["studios"].append(val)
                    elif ent.label_ in ["WORK_OF_ART", "EVENT"]:
                        if val not in entities["films"]:
                            entities["films"].append(val)
                    else:
                        if val not in entities["others"]:
                            entities["others"].append(val)
                
                # Limit sizes
                for key in entities:
                    entities[key] = entities[key][:15]
                return entities
            except Exception as e:
                logger.warn("spaCy entity extraction failed", error=str(e))

        # Basic RegEx/Keyword fallback for entity extraction
        # Look for capital letter patterns (names/titles)
        capitalized_words = list(set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text[:2000])))
        entities["others"] = capitalized_words[:10]
        return entities

    def extract_tfidf_fallback(self, title: str, text: str) -> Dict[str, Any]:
        """Generate a 3-sentence extractive summary and 4 tags using pure-Python sentence scoring (TF-IDF approximation)."""
        import re
        from collections import Counter
        
        result = {"summary": None, "tags": []}
        if not text or len(text.strip()) < 100:
            return result

        # Split into sentences using a simple sentence boundary regex
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s+', text.strip())
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        # Define common English stop words
        stop_words = {
            "the", "and", "a", "an", "of", "to", "in", "is", "that", "it", "was", "for", "on", "with", 
            "as", "at", "by", "be", "this", "are", "from", "who", "which", "about", "more", "has", "have", 
            "had", "been", "will", "would", "their", "but", "not", "or", "he", "she", "they", "his", "her",
            "him", "them", "but", "there", "their", "our", "we", "you", "your", "can", "out", "up", "into"
        }
        
        # Tokenize and compute frequencies for the body
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered_words = [w for w in words if w not in stop_words]
        word_freq = Counter(filtered_words)
        
        if not word_freq:
            # Fallback if no words could be tokenized
            summary = " ".join(sentences[:3])
            return {"summary": summary, "tags": []}

        # Score sentences based on word frequency
        sentence_scores = {}
        for idx, sent in enumerate(sentences):
            sent_words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
            if not sent_words:
                sentence_scores[idx] = 0
                continue
            
            # Sum word frequencies and divide by the log of sentence word count to normalize length (soft penalty)
            import math
            score = sum(word_freq.get(w, 0) for w in sent_words)
            sentence_scores[idx] = score / math.log(1 + len(sent_words))

        # Select the top 3 scoring sentences and sort them chronologically
        top_indices = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:3]
        top_indices.sort()
        summary_sentences = [sentences[i] for i in top_indices]
        summary = " ".join(summary_sentences)
        
        # Extract tags (boost words in title)
        title_words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        filtered_title = [w for w in title_words if w not in stop_words]
        title_freq = Counter(filtered_title)
        
        combined_freq = Counter()
        for w, count in word_freq.items():
            combined_freq[w] += count
        for w, count in title_freq.items():
            combined_freq[w] += count * 5  # Give significant boost to title words
            
        tags = [w for w, count in combined_freq.most_common(4)]
        
        return {"summary": summary, "tags": tags}

    async def generate_summary_and_tags_via_ollama(self, title: str, text: str) -> Dict[str, Any]:
        """Call Ollama API with format='json' in a single request, falling back to TF-IDF if offline."""
        if not text or len(text.strip()) < 100:
            return {"summary": None, "tags": []}

        logger.info("Requesting structured summary from local Ollama endpoint", host=self.ollama_host, model=self.ollama_model)
        
        # Prompt requesting JSON output
        prompt = (
            f"You are an expert news aggregator. Read the following article and return a JSON object with a summary and tags.\n"
            f"Output must be a valid JSON object matching this schema:\n"
            f'{{"summary": "A concise 3-sentence TL;DR summary", "tags": ["tag1", "tag2", "tag3", "tag4"]}}\n'
            f"The 'tags' array must contain exactly 4 lowercase relevant topics, actors, movie names, or genres.\n\n"
            f"Title: {title}\n"
            f"Article content:\n{text[:2500]}\n\n"
            f"JSON response:"
        )

        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    raw_response = resp.json().get("response", "").strip()
                    import json
                    data = json.loads(raw_response)
                    
                    summary = data.get("summary")
                    tags = data.get("tags", [])
                    if isinstance(tags, list):
                        tags = [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]
                    else:
                        tags = []
                    
                    logger.info("Successfully received structured Ollama response", tags=tags)
                    return {"summary": summary, "tags": tags[:6]}
                else:
                    logger.warn("Ollama endpoint returned non-200 status", status=resp.status_code)
        except Exception as e:
            logger.warn("Ollama connection failed or timed out. Falling back to native TF-IDF.", error=str(e))
            
        # Trigger TF-IDF fallback if Ollama fails or times out
        logger.info("Executing native TF-IDF summarizer fallback")
        return self.extract_tfidf_fallback(title, text)
