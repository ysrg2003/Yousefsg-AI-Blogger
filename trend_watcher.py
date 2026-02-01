# FILE: trend_watcher.py
# ROLE: Real-Time Data Scout (Google Trends & Breakout Queries)
# DESCRIPTION: Fetches actual rising topics using a hybrid approach (PyTrends + AI Search)
#              to ensure the system never runs out of fresh, real-world ideas.

import time
import random
import traceback
from pytrends.request import TrendReq
from config import log
from api_manager import generate_step_strict

def get_trending_topics_pytrends(category_keywords):
    """
    Method A: PyTrends API (Hard Data).
    Attempts to fetch 'Rising' queries directly from Google Trends.
    """
    log("   📈 [Trend Watcher] Pinging Google Trends API (Method A)...")
    try:
        # Initialize TrendReq with timeouts and retries to handle network glitches
        # hl='en-US', tz=360 (US Timezone)
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25), retries=2, backoff_factor=0.1)
        
        # Clean and prepare the keywords list
        # We split by comma and strip whitespace to get clean terms
        kw_list = [k.strip() for k in category_keywords.split(',') if k.strip()]
        
        if not kw_list:
            log("      ⚠️ No keywords provided for PyTrends.")
            return []
        
        # Strategy: Pick ONE random keyword to query at a time.
        # Querying too many at once often triggers Google's 429 (Too Many Requests).
        target_kw = random.choice(kw_list)
        log(f"      🎯 PyTrends Target: '{target_kw}'")
        
        # Build payload for the last 7 days in the US
        pytrends.build_payload([target_kw], cat=0, timeframe='now 7-d', geo='US', gprop='')
        
        # Fetch related queries
        related_queries = pytrends.related_queries()
        
        rising_trends = []
        if related_queries.get(target_kw) and related_queries[target_kw].get('rising') is not None:
            # Extract the 'rising' DataFrame
            df = related_queries[target_kw]['rising']
            
            # We want the top 5 rising queries. 
            # These are usually "Breakout" topics.
            if not df.empty:
                rising_trends = df.head(5)['query'].tolist()
                log(f"      ✅ PyTrends found {len(rising_trends)} rising topics.")
            else:
                log("      ⚠️ PyTrends returned empty rising data.")
        else:
            log("      ⚠️ PyTrends returned no related queries.")
            
        return rising_trends

    except Exception as e:
        # PyTrends often throws 429 errors. We catch them silently and switch to Method B.
        log(f"      ⚠️ PyTrends Blocked/Failed: {e}. Switching to AI Live Scout.")
        return []

def get_trending_topics_ai_scout(category, model_name):
    """
    Method B: AI Live Search (The Backup).
    Uses Gemini with Google Search Tools to perform a manual research scan.
    """
    log("   🔭 [Trend Watcher] Using AI Live Scout (Method B - Search Mode)...")
    
    prompt = f"""
    ROLE: Elite Tech News Scout.
    TASK: Find 5 specific "Breakout" or "Trending" search queries related to: "{category}" from the last 24-48 hours.
    
    INSTRUCTIONS:
    1.  Perform a Google Search for "trending {category} news today" or "latest {category} releases".
    2.  Look for specific Product Updates, Version Releases, Major Announcements, or Viral Controversies.
    3.  AVOID generic broad topics like "Future of AI" or "How to use AI".
    4.  The output must be a list of search queries that users are typing RIGHT NOW.
    
    OUTPUT JSON ONLY:
    {{
        "trends": [
            "Specific Tool V3 release",
            "Company X vs Company Y new benchmark",
            "Software Z pricing controversy"
        ]
    }}
    """
    
    try:
        # We MUST enable use_google_search=True here to get real-time data
        data = generate_step_strict(
            model_name, 
            prompt, 
            "Trend Scout", 
            required_keys=["trends"], 
            use_google_search=True
        )
        
        trends = data.get("trends", [])
        if trends:
            log(f"      ✅ AI Scout found {len(trends)} trends.")
        return trends
        
    except Exception as e:
        log(f"      ❌ AI Scout Failed: {e}")
        return []

def get_verified_trend(category, config):
    """
    The Main Interface Function called by the Orchestrator.
    It orchestrates Method A and Method B to ensure a result.
    """
    model_name = config['settings'].get('model_name')
    
    # Get keywords from config for this category
    cat_keywords = config['categories'][category].get('trending_focus', category)
    
    # 1. Try Method A: PyTrends (Data First Strategy)
    trends = get_trending_topics_pytrends(cat_keywords)
    
    # 2. If Method A fails or returns nothing, trigger Method B: AI Scout
    if not trends:
        trends = get_trending_topics_ai_scout(category, model_name)
    
    # 3. Clean and Validate Trends
    # Remove very short generic words (less than 2 words usually implies broad terms)
    clean_trends = []
    if trends:
        for t in trends:
            if t and isinstance(t, str) and len(t.split()) > 1:
                clean_trends.append(t.strip())
    
    if clean_trends:
        log(f"   🔥 [Trend Watcher] Final Candidates: {clean_trends}")
        return clean_trends
    
    log("   ❄️ [Trend Watcher] No valid trends found via any method.")
    return []
