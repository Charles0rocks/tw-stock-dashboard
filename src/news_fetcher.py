import feedparser
import urllib.parse
from datetime import datetime, timedelta

def fetch_stock_news(symbol: str, stock_name: str = "", max_results: int = 5) -> list:
    """
    Fetch recent 24-48 hours news for a stock symbol using Google News RSS.
    Returns list of dicts: [{'title': ..., 'published': ..., 'link': ..., 'source': ...}]
    """
    code = symbol.split(".")[0]
    query_str = f"{code} {stock_name}".strip()
    encoded_query = urllib.parse.quote(query_str)
    
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    news_items = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:max_results]:
            title = entry.get("title", "無標題")
            link = entry.get("link", "#")
            published = entry.get("published", "最新新聞")
            
            # Extract source title if present
            source_name = "財經新聞"
            if hasattr(entry, "source") and isinstance(entry.source, dict):
                source_name = entry.source.get("title", source_name)
            elif " - " in title:
                # Often title ends with " - SourceName"
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source_name = parts[1]
                
            news_items.append({
                "title": title.strip(),
                "published": published,
                "link": link,
                "source": source_name
            })
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        
    return news_items
