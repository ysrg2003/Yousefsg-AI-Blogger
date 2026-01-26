import requests
import urllib.parse
import feedparser
import random
import datetime
import os
from config import log

def get_gnews_api_sources(query, category):
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key: return []
    clean_query = query.replace(" when:2d", "").replace(" when:1d", "")
    log(f"   📡 Querying GNews API for: '{clean_query}'...")
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(clean_query)}&lang=en&country=us&max=5&apikey={api_key}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200 or 'articles' not in data: return []
        formatted = []
        for art in data.get('articles', []):
            formatted.append({
                "title": art.get('title'),
                "link": art.get('url'),
                "date": art.get('publishedAt', str(datetime.date.today())),
                "image": art.get('image')
            })
        return formatted
    except: return []

def get_real_news_rss(query_keywords, category=None):
    try:
        base_query = query_keywords.strip()
        if "," in base_query:
            topics = [t.strip() for t in base_query.split(',') if t.strip()]
            base_query = random.choice(topics)
            log(f"   🎯 Targeted Search Focus: '{base_query}'")

        if "when:" not in base_query:
            full_query = f"{base_query} when:2d"
        else:
            full_query = base_query

        log(f"   📰 Querying Google News RSS for: '{full_query}'...")
        encoded = urllib.parse.quote(full_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        
        if feed.entries:
            for entry in feed.entries[:10]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        
        elif category:
            log(f"   ⚠️ RSS Empty. Fallback to Category: {category}")
            fb = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fb)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({"title": entry.title, "link": entry.link, "date": "Today"})
            return items
            
        return []
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
