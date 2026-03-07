import httpx
import asyncio
from datetime import datetime

class NewsService:
    """
    Fetches real-time macroeconomic and cryptocurrency news.
    Uses free public APIs (CryptoPanic / Alternative.me / Binance News) 
    to inject macro sentiment into the AI LLM rationale.
    """
    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/?limit=1"
        self.last_sentiment = "Neutral"
        self.last_score = 50
        self.last_fetch_time = 0
        self.cache_ttl = 1800 # 30 mins
        
    async def get_macro_sentiment(self) -> str:
        """
        Returns a concise string summarizing current macro sentiment
        suitable for LLM context injection.
        """
        now = datetime.now().timestamp()
        
        # Return cached if valid
        if now - self.last_fetch_time < self.cache_ttl and self.last_fetch_time != 0:
            return f"Macro Sentiment: {self.last_score}/100 ({self.last_sentiment})."

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Fetch Fear and Greed Index
                fg_res = await client.get(self.fear_greed_url)
                if fg_res.status_code == 200:
                    data = fg_res.json()
                    if data and "data" in data and len(data["data"]) > 0:
                        fg_data = data["data"][0]
                        self.last_score = int(fg_data["value"])
                        self.last_sentiment = fg_data["value_classification"]
                        self.last_fetch_time = now

            summary = f"Macro Sentiment: {self.last_score}/100 ({self.last_sentiment})."
            
            # Contextualize extreme sentiment
            if self.last_score <= 25:
                summary += " Extreme Fear often signals heavy selling pressure but historic buy zones."
            elif self.last_score >= 75:
                summary += " Extreme Greed indicates an overheated market prone to sudden corrections."
                
            return summary
            
        except Exception as e:
            print(f"NewsService Error fetching macro data: {e}")
            return "Macro Sentiment: Unknown (API down)."

# Global instance
news_service = NewsService()
