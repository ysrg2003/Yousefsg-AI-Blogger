# FILE: news_fetcher.py
# ROLE: Fetches raw news links from Google RSS & GNews API with smart vetting.
# CRITICAL FIX (V7.1): Implements aggressive query cleaning to prevent GNews 400 errors.

import requests
import urllib.parse
import feedparser
import datetime
import os
import json
import re
from config import log
from api_manager import generate_step_strict

# ==============================================================================
# 1. SMART REPUTATION SYSTEM (MEMORY & FILTERING)
# ==============================================================================

REPUTATION_FILE = "source_reputation.json"

# Critical Blacklist: Domains that degrade SEO or provide low-value content.
# This list is merged with the dynamic one from the JSON file.
SEED_BLACKLIST = [
    "vocal.media", "aol.com", "msn.com", "yahoo.com", "marketwatch.com", 
    "indiacsr.in", "officechai.com", "analyticsinsight.net", "prweb.com",
    "businesswire.com", "globenewswire.com", "medium.com", "linkedin.com",
    "quora.com", "reddit.com", "youtube.com", "dailymotion.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com"
]

def get_domain_reputation():
    """
    Loads the reputation memory (Whitelist/Blacklist).
    """
    default_rep = {"blacklist": SEED_BLACKLIST, "whitelist": []}
    
    if os.path.exists(REPUTATION_FILE):
        try:
            with open(REPUTATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure seed items are always present for maximum protection
                data['blacklist'] = list(set(data.get('blacklist', []) + SEED_BLACKLIST))
                return data
        except Exception as e:
            log(f"⚠️ Error reading reputation file: {e}")
            return default_rep
    return default_rep

def save_domain_reputation(data):
    """
    Saves new approved/blocked domains to the persistent memory file.
    """
    try:
        with open(REPUTATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except: pass

def ai_vet_sources(items, model_name):
    """
    Uses Gemini AI to audit new domains to determine their quality.
    """
    reputation = get_domain_reputation()
    
    # Group items by domain to minimize API calls
    item_domains = {}
    for item in items:
        try:
            domain = urllib.parse.urlparse(item['link']).netloc.replace('www.', '').lower()
            if domain not in item_domains:
                item_domains[domain] = []
            item_domains[domain].append(item)
        except: continue

    unique_domains = list(item_domains.keys())
    
    # Filter out domains we already have a verdict on
    unknown_domains = [
        d for d in unique_domains 
        if d not in reputation['blacklist'] and d not in reputation['whitelist']
    ]
    
    if unknown_domains:
        log(f"   🕵️‍♂️ AI Auditor: Vetting {len(unknown_domains)} new domains...")
        
        prompt = f"""
        ROLE: Senior Tech Editor & Media Auditor.
        TASK: Evaluate these websites for credibility in covering AI & Tech news.
        
        CANDIDATE DOMAINS: {unknown_domains}
        
        CRITERIA FOR BLACKLIST (Reject):
        - User-Generated Content / Open Publishing (e.g., Vocal, Medium, LinkedIn, Quora).
        - Press Release Aggregators (PRWeb, BusinessWire).
        - General News Aggregators with low original tech reporting (MSN, AOL, Yahoo).
        
        CRITERIA FOR WHITELIST (Accept):
        - Dedicated Tech Publications (The Verge, TechCrunch, Wired, Ars Technica, VentureBeat).
        - Official Company Blogs (OpenAI, Google Blog, Microsoft, HuggingFace).
        - Reputable News Outlets with Tech Desks (Reuters, Bloomberg, NYT, CNBC).

        OUTPUT JSON ONLY:
        {{
          "blacklist": ["bad-site1.com", "spam-site2.com"],
          "whitelist": ["good-site1.com"]
        }}
        """
        try:
            decision = generate_step_strict(model_name, prompt, "Source Vetting")
            
            new_black = decision.get('blacklist', [])
            new_white = decision.get('whitelist', [])
            
            if new_black: log(f"      ⛔ AI Blocked: {new_black}")
            
            # Update and save memory
            reputation['blacklist'].extend(new_black)
            reputation['whitelist'].extend(new_white)
            reputation['blacklist'] = list(set(reputation['blacklist']))
            reputation['whitelist'] = list(set(reputation['whitelist']))
            save_domain_reputation(reputation)
            
        except Exception as e:
            log(f"      ⚠️ Vetting skipped due to API Error.")

    # Final filtering based on the now-updated reputation memory
    approved_items = []
    reputation = get_domain_reputation() 
    
    for domain, domain_items in item_domains.items():
        if domain in reputation['blacklist']:
            continue
        approved_items.extend(domain_items)
        
    return approved_items

# ==============================================================================
# 2. FETCHERS (WITH AGGRESSIVE QUERY CLEANING)
# ==============================================================================

def clean_search_query(query):
    """
    Aggressively cleans a search query to make it compatible with news APIs.
    Removes special characters, operators, and common conversational words.
    """
    # Remove special characters that cause 400 Bad Request errors
    q = re.sub(r'[^\w\s-]', '', query) # Allow words, spaces, and hyphens
    
    # Remove common conversational/search-operator words
    stop_words = [
        "how to", "guide", "news", "update", "review", "analysis", "using", "build", 
        "without", "writing", "code", "when7d", "when1d", "when2d"
    ]
    for sw in stop_words:
        # Case-insensitive replacement
        q = re.sub(r'\b' + re.escape(sw) + r'\b', '', q, flags=re.IGNORECASE)

    # Remove extra whitespace
    return " ".join(q.split())

def get_gnews_api_sources(query, category):
    """
    Fetches news from GNews API (High Reliability).
    """
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing - Skipping API search.")
        return []
    
    # Clean the query for maximum compatibility
    clean_q = clean_search_query(query)
    if not clean_q: clean_q = category # Fallback if cleaning leaves it empty
    
    log(f"   📡 Querying GNews API for: '{clean_q}'...")
    
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(clean_q)}&lang=en&country=us&max=5&apikey={api_key}"
    
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            log(f"      ⚠️ GNews API status: {r.status_code} | Query: {clean_q}")
            return []
        
        data = r.json()
        formatted_items = []
        for art in data.get('articles', []):
            formatted_items.append({
                "title": art.get('title'),
                "link": art.get('url'),
                "date": art.get('publishedAt', str(datetime.date.today())),
                "image": art.get('image')
            })
        
        log(f"      ✅ GNews API found {len(formatted_items)} results.")
        return formatted_items
        
    except Exception as e:
        log(f"      ❌ GNews Connection Failed: {e}")
        return []

def get_real_news_rss(query_keywords, category=None):
    """
    Fetches news from Google News RSS.
    Returns an empty list on failure to allow the main orchestrator to try other methods.
    """
    try:
        base_query = clean_search_query(query_keywords)
        if not base_query: base_query = category
        
        # Google RSS supports the 'when' operator, so we add it back if not present
        if "when:" not in query_keywords.lower():
            full_query = f"{base_query} when:7d"
        else:
            full_query = base_query # Keep original if it already has a time filter

        log(f"   📰 Querying Google News RSS for: '{full_query}'...")
        encoded = urllib.parse.quote(full_query)
        
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        
        if feed.entries:
            for entry in feed.entries[:10]:
                pub = entry.published if 'published' in entry else "Today"
                items.append({
                    "title": entry.title.split(' - ')[0], 
                    "link": entry.link, 
                    "date": pub
                })
            return items 
        
        # Explicitly return empty list on failure to trigger fallback logic in main.py
        log(f"   ⚠️ RSS Empty for '{base_query}'.")
        return []
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
