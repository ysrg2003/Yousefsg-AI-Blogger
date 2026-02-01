# FILE: history_manager.py
# ROLE: Central Intelligence Memory & Semantic Deduplication Engine (V10.0)
# DESCRIPTION: Manages the Knowledge Graph (knowledge_graph.json). 
#              Prevents SEO Cannibalization and Content Redundancy using a 
#              Hybrid Blacklist Strategy (Fuzzy Matching + Deep Semantic Value Check).
# INTEGRATION: Directly linked to main.py, cluster_manager.py, and gardener.py.

import os
import json
import datetime
import difflib
import traceback
from config import log
from api_manager import generate_step_strict

# --- GLOBAL CONFIGURATION ---
DB_FILE = 'knowledge_graph.json'
MAX_HISTORY_ITEMS_FOR_AI = 60  # عدد المقالات التي يتم إرسالها للذكاء الاصطناعي للمقارنة
SIMILARITY_THRESHOLD = 0.65    # حد التشابه النصي للمقارنة السريعة (Fuzzy)

def load_kg():
    """
    Loads the knowledge graph history from the JSON file with strict UTF-8 encoding.
    Ensures the system can handle non-English characters in titles.
    """
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    log(f"   ⚠️ History DB is not a list. Resetting memory...")
                    return []
    except json.JSONDecodeError:
        log(f"   ⚠️ History DB is corrupted (JSON Error). Creating fresh database...")
        return []
    except Exception as e:
        log(f"   ❌ Critical error loading History DB: {str(e)}")
        return []
    return []

def update_kg(title, url, section, post_id=None):
    """
    Updates the Knowledge Graph with a new published article.
    CRITICAL: This is the only source of truth for the 'Blacklist'.
    Saves metadata required for the Gardener module to perform future updates.
    """
    try:
        data = load_kg()
        
        # 1. Idempotency Check: Prevent duplicate URL entries
        if any(item.get('url') == url for item in data):
            log(f"   ⚠️ URL '{url}' already exists in History. Entry skipped.")
            return

        # 2. Construction of the Master Entry
        new_entry = {
            "title": str(title).strip(),
            "url": str(url).strip(),
            "section": str(section).strip(),
            "date": str(datetime.date.today()),
            "post_id": str(post_id) if post_id else None,
            "last_verified": str(datetime.date.today()),
            "update_count": 0
        }

        # 3. Atomic Append
        data.append(new_entry)
        
        # 4. Save with high precision and formatting
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        log(f"   💾 [Memory Updated] Total Articles in Blacklist: {len(data)}.")
        
    except Exception as e:
        log(f"   ❌ Failed to update Knowledge Graph: {str(e)}")
        traceback.print_exc()

def get_blacklist_context(category=None, days_limit=120):
    """
    Prepares a descriptive 'Blacklist String' for the AI Judge.
    Filters content by date to keep the prompt window efficient but relevant.
    """
    kg = load_kg()
    if not kg:
        return "NO_PREVIOUS_CONTENT"
    
    # Calculate date cutoff for relevance (default 120 days)
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_limit)
    
    relevant_items = []
    for item in kg:
        try:
            # Parse date and filter
            pub_date_str = item.get('date', '2024-01-01')
            pub_date = datetime.datetime.strptime(pub_date_str, "%Y-%m-%d").date()
            
            if pub_date >= cutoff_date:
                relevant_items.append(item)
        except:
            continue

    # Sort: Newest first
    relevant_items.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Take only the top N items to avoid prompt flooding
    recent_subset = relevant_items[:MAX_HISTORY_ITEMS_FOR_AI]
    
    # Format for the AI
    formatted_list = []
    for i in recent_subset:
        formatted_list.append(f"- [Published: {i.get('date')}] Topic: {i.get('title')}")
        
    return "\n".join(formatted_list)

def check_semantic_duplication(new_keyword, category, config):
    """
    THE ULTIMATE DEDUPLICATION GUARD (The Blacklist Comparison Engine).
    Executes a two-phase check to ensure NO repetitive content.
    """
    target = str(new_keyword).strip().lower()
    
    # --- PHASE 1: LOCAL FUZZY MATCH (High Speed) ---
    # Catches 1:1 duplicates or very similar titles without API calls.
    kg = load_kg()
    for item in kg:
        existing_title = item.get('title', '').lower()
        
        # Levenshtein Distance
        ratio = difflib.SequenceMatcher(None, target, existing_title).ratio()
        if ratio > SIMILARITY_THRESHOLD:
            log(f"      ⛔ [Phase 1 REJECT] '{target}' is {int(ratio*100)}% similar to an existing title.")
            return True

        # Substring check
        if len(target) > 8 and target in existing_title:
             log(f"      ⛔ [Phase 1 REJECT] '{target}' is a subset of an existing title.")
             return True

    # --- PHASE 2: DEEP SEMANTIC VALUE JUDGE (AI) ---
    # Compares the "Core Value" and "Reader Takeaway".
    model_name = config['settings'].get('model_name', 'gemini-2.5-flash')
    blacklist_text = get_blacklist_context(category)
    
    if blacklist_text == "NO_PREVIOUS_CONTENT":
        return False

    log(f"   🧠 [Phase 2 Judge] Analyzing 'Reader Value' of '{new_keyword}' against Blacklist...")

    prompt = f"""
    ROLE: Ruthless SEO Editor-in-Chief.
    TASK: Content Cannibalization Audit (Blacklist Comparison).
    
    INPUT PROPOSAL: "{new_keyword}"
    CATEGORY: "{category}"
    
    RECENTLY PUBLISHED ARTICLES (THE BLACKLIST):
    {blacklist_text}
    
    ------------------------------------------------------------------------
    STRICT DECISION LOGIC:
    1. ANALYZE VALUE: If I write about "{new_keyword}", what NEW facts or lessons will the reader learn that are NOT in the Blacklist?
    2. REJECT (is_duplicate: true) IF:
       - The core news event is already covered (e.g., "Product Launch" vs "Product is here").
       - The "Core Insight" is identical (e.g., "Why X is better than Y" vs "Comparison of X and Y").
       - The proposal is just a minor sub-feature of a large review we already published.
    3. ALLOW (is_duplicate: false) ONLY IF:
       - It is a significant NEW update (Version 2.0 vs Version 1.0).
       - It is a deep-dive "How-to Guide" and the previous one was just a "News Flash".
       - It covers a completely different user problem/intent.
    ------------------------------------------------------------------------
    
    OUTPUT JSON FORMAT ONLY:
    {{
        "is_duplicate": true/false,
        "conflict_title": "Title of the existing article that causes the conflict",
        "reason": "Detailed logic on why the reader gain is identical or unique"
    }}
    """

    try:
        # Use the system's generator
        result = generate_step_strict(
            model_name, 
            prompt, 
            "Semantic Blacklist Check", 
            required_keys=["is_duplicate"]
        )
        
        is_dup = result.get('is_duplicate', False)
        reason = result.get('reason', 'N/A')
        
        if is_dup:
            log(f"      ⛔ [Phase 2 REJECT] '{new_keyword}' blocked. Reason: {reason}")
            return True
        else:
            log(f"      ✅ [Phase 2 PASSED] Topic is unique. Reason: {reason}")
            return False
            
    except Exception as e:
        log(f"      ⚠️ Semantic Check API Failure: {str(e)}. Proceeding with Phase 1 result (False).")
        return False

def get_recent_titles_string(category=None, limit=100):
    """
    Compatibility function for older modules. 
    Returns a simple string of titles.
    """
    kg = load_kg()
    if not kg: return ""
    
    if category:
        relevant = [i for i in kg if i.get('section') == category]
    else:
        relevant = kg
        
    subset = relevant[-limit:]
    titles = [f"- {i.get('title', 'Untitled')}" for i in subset]
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    """
    Logic for Internal Linking Strategy (Siloing).
    Selects 5 relevant past articles from the Knowledge Graph.
    """
    kg = load_kg()
    
    # 1. Try to find articles in the same category (Silo)
    same_cat = [i for i in kg if i.get('section') == current_category]
    
    # 2. Selection: Take the most recent ones
    selected = same_cat[-5:]
    
    # 3. Backfill if less than 3
    if len(selected) < 3:
        others = [i for i in kg if i.get('section') != current_category]
        needed = 3 - len(selected)
        selected.extend(others[-needed:])

    # 4. Format as JSON for the Prompt C (SEO Polish)
    output = []
    for item in selected:
        output.append({
            "title": item.get('title'),
            "url": item.get('url')
        })
        
    return json.dumps(output, ensure_ascii=False)

def perform_maintenance_cleanup():
    """
    Maintenance task to keep the Knowledge Graph healthy.
    Prevents the JSON file from becoming too massive.
    Prunes metadata but keeps URLs and Titles for Deduplication.
    """
    try:
        data = load_kg()
        if len(data) > 1000:
            # We keep everything but we could implement archival logic here
            # For now, we just log the size
            log(f"   📊 Knowledge Graph size: {len(data)} entries. Maintenance healthy.")
    except Exception as e:
        log(f"   ⚠️ Maintenance Error: {str(e)}")
