import email.utils
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)

class FeedParser:
    @staticmethod
    def parse(xml_content: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse RSS/Atom feed and return a list of standard item dicts containing titles and URLs."""
        items = []
        if not xml_content:
            return items

        try:
            # Parse XML feed with BeautifulSoup (supports xml feature if lxml is installed, falls back to html)
            try:
                soup = BeautifulSoup(xml_content, features="xml")
            except Exception:
                soup = BeautifulSoup(xml_content, features="html.parser")
            
            # Check RSS format
            rss_items = soup.find_all("item")
            if rss_items:
                for item in rss_items:
                    link_node = item.find("link")
                    title_node = item.find("title")
                    pub_node = item.find("pubDate") or item.find("date")
                    desc_node = item.find("description") or item.find("encoded")
                    
                    if not link_node or not title_node:
                        continue
                        
                    pub_date = None
                    if pub_node:
                        try:
                            # Parse RFC 2822 date
                            parsed_date = email.utils.parsedate_to_datetime(pub_node.text)
                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                            pub_date = parsed_date
                        except Exception:
                            logger.debug("Failed to parse pubDate", text=pub_node.text)

                    # Category mapping
                    categories = [cat.text for cat in item.find_all("category") if cat.text]

                    items.append({
                        "title": title_node.text.strip(),
                        "canonical_url": link_node.text.strip(),
                        "published_at": pub_date or datetime.now(timezone.utc),
                        "tags": categories,
                        "description": desc_node.text.strip() if desc_node else ""
                    })
                
                logger.info("Parsed RSS items successfully", count=len(items), source=source_config["name"])
                return items

            # Check Atom format
            atom_entries = soup.find_all("entry")
            if atom_entries:
                for entry in atom_entries:
                    link_node = entry.find("link")
                    title_node = entry.find("title")
                    pub_node = entry.find("published") or entry.find("updated")
                    summary_node = entry.find("summary") or entry.find("content")

                    if not link_node or not title_node:
                        continue

                    url = link_node.get("href") or link_node.text
                    
                    pub_date = None
                    if pub_node:
                        try:
                            # Parse ISO 8601 date
                            pub_date = datetime.fromisoformat(pub_node.text.replace("Z", "+00:00"))
                        except Exception:
                            logger.debug("Failed to parse Atom datetime", text=pub_node.text)

                    categories = [cat.get("term") for cat in entry.find_all("category") if cat.get("term")]

                    items.append({
                        "title": title_node.text.strip(),
                        "canonical_url": url.strip(),
                        "published_at": pub_date or datetime.now(timezone.utc),
                        "tags": categories,
                        "description": summary_node.text.strip() if summary_node else ""
                    })

                logger.info("Parsed Atom items successfully", count=len(items), source=source_config["name"])
                return items

        except Exception as e:
            logger.error("Error parsing feed XML", error=str(e), source=source_config["name"])

        return items
