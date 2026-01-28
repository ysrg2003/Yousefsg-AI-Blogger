# FILE: news_fetcher.py
# ROLE: High-Precision News Fetcher & Quality Gatekeeper.
# DESCRIPTION: Fetches news from Google News RSS & GNews API. 
#              Enforces strict quality control via AI vetting and aggressive query optimization.

import requests
import urllib.parse
import feedparser
import random
import datetime
import os
import json
import re
from config import log
from api_manager import generate_step_strict

# ==============================================================================
# 1. ELITE REPUTATION SYSTEM (MEMORY & FILTERING)
# ==============================================================================

REPUTATION_FILE = "source_reputation.json"

# Critical Blacklist: Domains that degrade SEO, contain UGC, or provide low-value content.
# This list acts as the immune system of the bot.
SEED_BLACKLIST = [
    "vocal.media", "aol.com", "msn.com", "yahoo.com", "marketwatch.com", 
    "indiacsr.in", "officechai.com", "analyticsinsight.net", "prweb.com",
    "businesswire.com", "globenewswire.com", "medium.com", "linkedin.com",
    "quora.com", "reddit.com", "youtube.com", "dailymotion.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "pinterest.com", "tumblr.com", "blogspot.com", "wordpress.com",
    "buzzfeed.com", "softpedia.com", "slashdot.org"
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
                # Ensure seed items are always present for maximum protection
                current_blacklist = set(data.get('blacklist', []))
                seed_set = set(SEED_BLACKLIST)
                data['blacklist'] = list(current_blacklist.union(seed_set))
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
    Uses the AI Engine (via api_manager) to audit new domains.
    Logic:
    1. Pass 'news.google.com' links (Trusted Index - will be resolved later).
    2. Block known bad domains immediately.
    3. Ask AI about unknown domains to build the whitelist/blacklist.
    """
    reputation = get_domain_reputation()
    
    # Group items by domain to minimize API calls
    item_domains = {}
    for item in items:
        try:
            # Handle Google News Redirect links separately (cannot vet domain yet, but source is trusted index)
            if "news.google.com" in item['link']:
                # These are high value because they come directly from Google's Index
                approved_items = item_domains.setdefault("google_news_redirect", [])
                approved_items.append(item)
                continue

            # Extract clean domain (e.g., 'techcrunch.com')
            domain = urllib.parse.urlparse(item['link']).netloc.replace('www.', '').lower()
            
            if domain in reputation['blacklist']:
                continue
            
            if domain not in item_domains:
                item_domains[domain] = []
            item_domains[domain].append(item)
        except: continue

    unique_domains = [d for d in item_domains.keys() if d != "google_news_redirect"]
    
    # Filter out domains we already have a verdict on (Whitelist or Blacklist)
    unknown_domains = [d for d in unique_domains if d not in reputation['whitelist']]
    
    # If there are new, unknown domains, ask the AI Auditor
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
        - Clickbait or Spam Farms.
        
        CRITERIA FOR WHITELIST (Accept):
        - Dedicated Tech Publications (The Verge, TechCrunch, Wired, Ars Technica, VentureBeat).
        - Official Company Blogs (OpenAI, Google Blog, Microsoft, HuggingFace).
        - Reputable News Outlets with Tech Desks (Reuters, Bloomberg, NYT, CNBC, BBC).
        - High-Quality Niche AI Blogs or University Research Pages.

        OUTPUT JSON ONLY:
        {{
          "blacklist": ["bad-site1.com", "spam-site2.com"],
          "whitelist": ["good-site1.com"]
        }}
        """
        try:
            # Using generate_step_strict to leverage Puter/Gemini hybrid logic
            decision = generate_step_strict(model_name, prompt, "Source Vetting")
            
            new_black = decision.get('blacklist', [])
            new_white = decision.get('whitelist', [])
            
            if new_black: log(f"      ⛔ AI Blocked: {new_black}")
            
            # Update memory
            reputation['blacklist'].extend(new_black)
            reputation['whitelist'].extend(new_white)
            
            # De-duplicate lists
            reputation['blacklist'] = list(set(reputation['blacklist']))
            reputation['whitelist'] = list(set(reputation['whitelist']))
            
            save_domain_reputation(reputation)
            
        except Exception as e:
            log(f"      ⚠️ Vetting skipped due to API Error. Proceeding with known safe lists.")

    # Final filtering based on the updated reputation memory
    approved_items = []
    
    # 1. Add Google News Redirects first (High Priority)
    approved_items.extend(item_domains.get("google_news_redirect", []))
    
    # 2. Reload latest reputation to ensure we catch everything
    reputation = get_domain_reputation() 
    
    for domain, items_list in item_domains.items():
        if domain == "google_news_redirect": continue
        
        if domain not in reputation['blacklist']:
            approved_items.extend(items_list)
            
    return approved_items

# ==============================================================================
# 2. QUERY CLEANING & OPTIMIZATION (THE FIXER)
# ==============================================================================

def clean_search_query(query):
    """
    Aggressively cleans a search query to make it compatible with news APIs (GNews/RSS).
    Prevents HTTP 400 Errors and "No Results" returns.
    """
    if not query: return ""

    # 1. Remove special characters that cause 400 Bad Request errors 
    # Keep alphanumeric, spaces, and hyphens only.
    q = re.sub(r'[^\w\s-]', '', query) 
    
    # 2. Remove common conversational words and search operators 
    # These clutter the query and confuse exact-match algorithms in RSS/GNews
    stop_words = [
        "how to", "guide", "news", "update", "review", "analysis", "using", "build", 
        "without", "writing", "code", "when7d", "when1d", "when2d", "when", "latest",
        "tutorial", "learn", "explained", "vs", "versus"
    ]
    
    for sw in stop_words:
        # Case-insensitive replacement of whole words
        q = re.sub(r'\b' + re.escape(sw) + r'\b', '', q, flags=re.IGNORECASE)

    # 3. Collapse multiple spaces into one and strip
    clean_q = " ".join(q.split())
    
    return clean_q

# ==============================================================================
# 3. GNEWS API FETCHER (DIRECT INDEX ACCESS)
# ==============================================================================

def get_gnews_api_sources(query, category):
    """
    Fetches news from GNews API (High Reliability).
    Applies aggressive cleaning to prevent HTTP 400 errors.
    """
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing - Skipping API search.")
        return []
    
    # 1. Clean the query for API compatibility
    clean_q = clean_search_query(query)
    
    # Fallback: If cleaning removed everything (rare), use the Category name
    if not clean_q or len(clean_q) < 3: 
        clean_q = category 
    
    # 2. Add negative filtering to save quota and improve quality
    # Limiting negative sites filter to top 5 to keep URL length managed and avoid 414 URI Too Long
    hard_filters = " ".join([f"-site:{site}" for site in SEED_BLACKLIST[:5]])
    final_query = f"{clean_q} {hard_filters}"

    log(f"   📡 Querying GNews API for: '{clean_q}'...")
    
    # Construct URL with proper encoding and strict English/US filtering
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(final_query)}&lang=en&country=us&max=6&apikey={api_key}"
    
    try:
        r = requests.get(url, timeout=15)
        
        # Handle HTTP Errors Gracefully
        if r.status_code != 200:
            # Don't log expected Forbidden errors if quota is out, otherwise warn
            if "forbidden" not in r.text.lower() and r.status_code != 429:
                log(f"      ⚠️ GNews API status: {r.status_code} | Query: {clean_q}")
            return []
            
        data = r.json()
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

# ==============================================================================
# 4. GOOGLE NEWS RSS FETCHER (THE GOLD STANDARD)
# ==============================================================================

def get_real_news_rss(query_keywords, category=None):
    """
    Fetches news from Google News RSS.
    Returns an EMPTY list on failure to allow the main orchestrator to trigger fallbacks.
    """
    try:
        # 1. Optimize Query for RSS
        base_query = clean_search_query(query_keywords)
        
        # If query is too short or empty after cleaning, fallback to category to ensure SOME results
        if not base_query or len(base_query) < 3: 
            base_query = category
        
        # 2. Handle Date Range
        # Google RSS supports 'when:7d' operator. We add it if not present.
        # Note: clean_search_query removes 'when7d', so we add it back here cleanly.
        if "when:" not in query_keywords.lower():
            full_query = f"{base_query} when:7d"
        else:
            full_query = base_query # Respect original time window if present

        log(f"   📰 Querying Google News RSS for: '{full_query}'...")
        encoded = urllib.parse.quote(full_query)
        
        # English US edition (gl=US, ceid=US:en) ensures high quality sources
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        
        if feed.entries:
            # Extract valid entries (Limit to 10)
            for entry in feed.entries[:10]:
                # Extract publication date or default to Today
                pub = entry.published if 'published' in entry else "Today"
                
                # Clean title (remove source name at the end usually, e.g. " - The Verge")
                title_clean = entry.title.split(' - ')[0]
                
                items.append({
                    "title": title_clean,
                    "link": entry.link, 
                    "date": pub
                })
            
            return items 
        
        # --- CRITICAL BEHAVIOR ---
        # Explicitly return empty list if no results found.
        # This signals main.py to try GNews or AI Research instead.
        log(f"   ⚠️ RSS Empty for '{base_query}'.")
        return []
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
