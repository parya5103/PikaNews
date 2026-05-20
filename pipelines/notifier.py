import os
import httpx
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger(__name__)

class AlertNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = os.getenv("WEBHOOK_URL") or config.get("app", {}).get("webhook_url", "")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.discord_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.slack_url = os.getenv("SLACK_WEBHOOK_URL")
        
        # User defined keywords for real-time alerts (case-insensitive)
        self.alert_keywords = ["srk", "marvel", "oscar", "salman khan", "avatar", "harrison ford", "spiderman", "batman", "bollywood"]

    async def notify_all(self, article: Dict[str, Any]):
        """Check for keyword match and dispatch notifications to active channels."""
        title = article.get("title", "")
        body = article.get("body_text", "")
        content = f"{title} {body}".lower()

        # Check keyword matching
        matched_keywords = [kw for kw in self.alert_keywords if kw in content]
        if not matched_keywords:
            return

        logger.info("Alert keywords matched", keywords=matched_keywords, title=title)
        
        # Prepare payload message
        message = (
            f"🚨 *PIKANEWS ALERT* 🚨\n"
            f"Keywords: {', '.join(matched_keywords).upper()}\n"
            f"Title: *{title}*\n"
            f"Source: {article.get('source')} ({article.get('industry')})\n"
            f"Summary: {article.get('summary') or 'No summary available.'}\n"
            f"Link: {article.get('canonical_url')}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Telegram
            if self.telegram_token and self.telegram_chat_id:
                try:
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                    payload = {
                        "chat_id": self.telegram_chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                    await client.post(url, json=payload)
                except Exception as e:
                    logger.error("Failed to send Telegram alert", error=str(e))

            # 2. Discord
            if self.discord_url:
                try:
                    payload = {"content": message}
                    await client.post(self.discord_url, json=payload)
                except Exception as e:
                    logger.error("Failed to send Discord alert", error=str(e))

            # 3. Slack
            if self.slack_url:
                try:
                    payload = {"text": message}
                    await client.post(self.slack_url, json=payload)
                except Exception as e:
                    logger.error("Failed to send Slack alert", error=str(e))

            # 4. Custom webhook POST
            if self.webhook_url:
                try:
                    payload = {
                        "event": "alert_keyword_matched",
                        "keywords": matched_keywords,
                        "article": {
                            "title": title,
                            "source": article.get("source"),
                            "industry": article.get("industry"),
                            "canonical_url": str(article.get("canonical_url")),
                            "summary": article.get("summary")
                        }
                    }
                    await client.post(self.webhook_url, json=payload)
                except Exception as e:
                    logger.error("Failed to post custom webhook", error=str(e))
