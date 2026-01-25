# FILE: news_fetcher.py
# DESCRIPTION: Fetches news articles from GNews API and Google News RSS.

import os
import requests
import urllib.parse
import feedparser
import datetime
from config import log

def get_gnews_api_sources(query, category):
    """Fetches news using GNews.io API."""
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing/not loaded. Skipping.")
        return []

    log(f"   📡 Querying GNews API for: '{query}'...")
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(query)}&lang=en&country=us&max=5&apikey={api_key}"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200 or 'articles' not in data:
            return []
        formatted_items = []
        for art in data.get('articles', []):
            formatted_items.append({
                "title": art.get('title'),
                "link": art.get('url'),
                "date": art.get('publishedAt', str(datetime.date.today())),
                "image": art.get('image')
            })
        log(f"   ✅ GNews found {len(formatted_items)} articles.")
        return formatted_items
    except Exception as e:
        log(f"   ❌ GNews Connection Failed: {e}")
        return []

def get_real_news_rss(query):
    """Fetches news using Google News RSS as a fallback."""
    try:
        log(f"   📰 Querying Google News RSS for: '{query}'...")
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        items = []
        if feed.entries:
            for entry in feed.entries[:8]:
                items.append({
                    "title": entry.title.split(' - ')[0],
                    "link": entry.link,
                    "date": entry.published if 'published' in entry else "Today"
                })
        return items
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
