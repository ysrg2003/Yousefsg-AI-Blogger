# FILE: news_fetcher.py
# ROLE: Fetches raw news links from Google RSS & GNews API with smart vetting.
# CRITICAL UPDATE: Implements smart query cleaning and explicit failure states to allow logic chaining.

import requests
import urllib.parse
import feedparser
import random
import datetime
import os
import json
from config import log
from api_manager import generate_step_strict

# ==============================================================================
# 1. SMART REPUTATION SYSTEM (MEMORY)
# ==============================================================================

REPUTATION_FILE = "source_reputation.json"

# Critical Blacklist: Domains that degrade SEO or provide low-value content
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
    Combines the persistent JSON file with the emergency SEED_BLACKLIST.
    """
    default_rep = {"blacklist": SEED_BLACKLIST, "whitelist": []}
    
    if os.path.exists(REPUTATION_FILE):
        try:
            with open(REPUTATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure seed items are always present
                data['blacklist'] = list(set(data.get('blacklist', []) + SEED_BLACKLIST))
                return data
        except Exception as e:
            log(f"⚠️ Error reading reputation file: {e}")
            return default_rep
    return default_rep

def save_domain_reputation(data):
    """
    Saves new approved/blocked domains to the persistent memory.
    """
    try:
        with open(REPUTATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except: pass

def ai_vet_sources(items, model_name):
    """
    Uses Gemini AI to audit new domains.
    Determines if a domain is 'Authority News' or 'Spam/UGC'.
    """
    reputation = get_domain_reputation()
    
    # Group items by domain to minimize API calls
    item_domains = {}
    for item in items:
        try:
            # Extract clean domain (e.g., 'techcrunch.com')
            domain = urllib.parse.urlparse(item['link']).netloc.replace('www.', '').lower()
            if domain not in item_domains:
                item_domains[domain] = []
            item_domains[domain].append(item)
        except: continue

    unique_domains = list(item_domains.keys())
    
    # Filter out domains we already know
    unknown_domains = [
        d for d in unique_domains 
        if d not in reputation['blacklist'] and d not in reputation['whitelist']
    ]
    
    # If there are new domains, ask the AI Auditor
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
        - Social Media or Video Platforms.
        
        CRITERIA FOR WHITELIST (Accept):
        - Dedicated Tech Publications (The Verge, TechCrunch, Wired, Ars Technica, VentureBeat).
        - Official Company Blogs (OpenAI, Google Blog, Microsoft, HuggingFace).
        - Reputable News Outlets with Tech Desks (Reuters, Bloomberg, NYT, CNBC).
        - High-Quality Niche AI Blogs.

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
            
            # Update memory
            reputation['blacklist'].extend(new_black)
            reputation['whitelist'].extend(new_white)
            
            # De-duplicate
            reputation['blacklist'] = list(set(reputation['blacklist']))
            reputation['whitelist'] = list(set(reputation['whitelist']))
            
            save_domain_reputation(reputation)
            
        except Exception as e:
            log(f"      ⚠️ Vetting skipped (Error). Assuming safe for now.")

    # Final filtering based on updated reputation
    approved_items = []
    # Reload latest to be sure
    reputation = get_domain_reputation() 
    
    for domain, domain_items in item_domains.items():
        if domain in reputation['blacklist']:
            continue # Drop these items
        approved_items.extend(domain_items)
        
    return approved_items

# ==============================================================================
# 2. STANDARD FETCHERS (ROBUST & CLEANED)
# ==============================================================================

def get_gnews_api_sources(query, category):
    """
    Fetches news from GNews API (High Reliability).
    Cleans query strings to ensure API compatibility.
    """
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing - Skipping API search.")
        return []
    
    # 1. Clean the query
    # GNews API fails with special search operators like 'when:7d' or complex quoting.
    # We strip them to standard keywords.
    clean_query = query.replace('"', '').replace(":", "")
    for term in ["when1d", "when2d", "when3d", "when7d", "news", "update"]:
        clean_query = clean_query.replace(term, "")
        clean_query = clean_query.replace(f" {term}", "") # remove space-prefixed
    
    clean_query = clean_query.strip()
    
    # 2. Add negative filtering to save quota and improve quality
    # Limiting negative sites filter to top 5 to keep URL length managed
    hard_filters = " ".join([f"-site:{site}" for site in SEED_BLACKLIST[:5]])
    final_query = f"{clean_query} {hard_filters}"

    log(f"   📡 Querying GNews API for: '{clean_query}'...")
    
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(final_query)}&lang=en&country=us&max=6&apikey={api_key}"
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if r.status_code != 200:
            # Handle rate limits or errors quietly
            if "forbidden" not in r.text.lower():
                log(f"      ⚠️ GNews API status: {r.status_code}")
            return []
            
        if 'articles' not in data or not data['articles']:
            return []
            
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
    Includes smart fallback logic: if a strict search fails, return Empty
    to allow the Orchestrator to try GNews or AI Search.
    """
    try:
        # 1. Optimize Query for RSS
        # RSS requires specific encoding and hates long complex sentences.
        # Remove keywords that confuse the feed matching logic.
        base_query = query_keywords.replace('"', '').strip()
        base_query = base_query.replace("news update", "").replace("review OR analysis", "").replace("guide", "")
        base_query = " ".join(base_query.split()) # Remove double spaces
        
        # 2. Handle Date Range
        # If no range is specified, default to 7 days to capture Tutorials/Guides (which aren't just 24h news)
        if "when:" not in base_query:
            # Search broadly (last 7 days)
            full_query = f"{base_query} when:7d"
        else:
            full_query = base_query

        log(f"   📰 Querying Google News RSS for: '{full_query}'...")
        encoded = urllib.parse.quote(full_query)
        
        # English US edition
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        
        if feed.entries:
            # Extract valid entries
            for entry in feed.entries[:10]:
                # Extract publication date or default to Today
                pub = entry.published if 'published' in entry else "Today"
                
                # Clean title (remove source name at the end usually)
                title_clean = entry.title.split(' - ')[0]
                
                items.append({
                    "title": title_clean,
                    "link": entry.link, 
                    "date": pub
                })
            
            return items 
        
        # --- CRITICAL CHANGE ---
        # Do NOT fallback to 'Category' search here. 
        # Return empty so main.py knows that *specific* research failed.
        # This triggers GNews or AI Search which are smarter.
        log(f"   ⚠️ RSS Empty for '{base_query}'. Returning empty list to trigger GNews.")
        return []
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
