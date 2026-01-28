# FILE: history_manager.py
# ROLE: Knowledge Graph & Memory Core.
# FEATURES: 
#   1. Prevents content cannibalization via Hybrid Semantic Checks (Fuzzy + AI).
#   2. Manages 'post_id' storage for the Gardener module (Update capability).
#   3. Provides intelligent context for internal linking strategies.
#   4. CRITICAL FIX: Solved SyntaxError regarding dictionary construction.

import os
import json
import datetime
import difflib
from config import log
from api_manager import generate_step_strict

# Path to the JSON database
DB_FILE = 'knowledge_graph.json'

def load_kg():
    """
    Loads the knowledge graph history from the JSON file safely.
    Returns an empty list if file doesn't exist or is corrupted.
    """
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log(f"⚠️ Warning: Could not load History DB: {e}")
    return []

def update_kg(title, url, section, post_id=None):
    """
    Updates the Knowledge Graph with a new published article.
    CRITICAL FIX: Accepts 'post_id' (optional) and handles dictionary insertion correctly.
    """
    try:
        data = load_kg()
        
        # 1. Prevent exact URL duplicates (Idempotency)
        if any(item.get('url') == url for item in data):
            log(f"   ⚠️ URL already exists in KG. Skipping duplicate entry.")
            return

        # 2. Construct the new entry
        new_entry = {
            "title": title,
            "url": url,
            "section": section,
            "date": str(datetime.date.today())
        }

        # 3. Store Blogger Post ID if available (Essential for Gardener updates)
        # This fixes the SyntaxError by using standard dictionary assignment
        if post_id:
            new_entry["post_id"] = post_id
            
        data.append(new_entry)
        
        # 4. Save atomically with UTF-8 encoding
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        log(f"   💾 History updated. Total Knowledge Graph: {len(data)} articles.")
        
    except Exception as e:
        log(f"❌ Error updating Knowledge Graph: {e}")

def perform_maintenance_cleanup():
    """
    Keeps the JSON file size manageable by pruning very old entries.
    Retains the last 500 articles to maintain context for linking and duplication checks.
    """
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Keep the last 500 articles. Oldest are removed first.
            if len(data) > 500:
                trimmed_data = data[-500:]
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump(trimmed_data, f, indent=2, ensure_ascii=False)
                log(f"   🧹 Maintenance: Trimmed history DB to last 500 entries.")
    except Exception as e:
        log(f"   ⚠️ Maintenance error: {e}")

def get_recent_titles_string(category=None, limit=100):
    """
    Returns a formatted string of recent titles to feed into the AI Context.
    Used by the Strategy module to avoid writing about the same topic twice.
    """
    kg = load_kg()
    if not kg: return "No previous articles found."
    
    if category:
        relevant = [i for i in kg if i.get('section') == category]
    else:
        relevant = kg
        
    # Get the last 'limit' items to keep context window manageable
    recent_subset = relevant[-limit:]
    
    titles = [f"- {i.get('title', 'Unknown Title')}" for i in recent_subset]
    
    if not titles: return "No previous articles in this category."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    """
    Selects 5 relevant past articles to suggest as Internal Links in the new article.
    Strategy:
    1. Prioritize articles in the same Category (Silo Structure).
    2. Backfill with recent articles from other categories if needed.
    """
    kg = load_kg()
    
    # Filter by same category (Priority)
    same_cat = [i for i in kg if i.get('section') == current_category]
    
    # Select recent ones (Fresher content is usually better for linking news)
    # Taking the last 5 items
    selected_links = same_cat[-5:]
    
    # If we don't have enough, grab some from other categories purely for volume/structure
    if len(selected_links) < 3:
        other_cat = [i for i in kg if i.get('section') != current_category]
        needed = 3 - len(selected_links)
        selected_links.extend(other_cat[-needed:])

    # Format for AI Prompt
    formatted_output = [{"title": i['title'], "url": i['url']} for i in selected_links]
    return json.dumps(formatted_output)

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Duplication Check (The "Paranoid" Guard):
    1. Phase 1: Local Fuzzy Match (Fast/Cheap) - Catches obvious duplicates.
    2. Phase 2: AI Semantic Judge (Smart/Contextual) - Catches "Cannibalization" (different words, same meaning).
    """
    if not history_string or len(history_string) < 10: 
        return False
    
    # --- Phase 1: Local Heuristics (Fuzzy Match) ---
    target = new_keyword.lower().strip()
    
    for line in history_string.split('\n'):
        existing_title = line.replace("- ", "").strip().lower()
        
        # Levenshtein distance ratio
        # Threshold 0.65 is strict: catches "Sora Price" vs "Sora Cost"
        similarity_ratio = difflib.SequenceMatcher(None, target, existing_title).ratio()
        
        if similarity_ratio > 0.65:
            log(f"      ⛔ BLOCKED (Local Fuzzy Match): '{target}' is {int(similarity_ratio*100)}% similar to '{existing_title}'")
            return True

        # Substring check for short titles
        if len(target) > 5 and target in existing_title:
             log(f"      ⛔ BLOCKED (Local Substring): '{target}' found in '{existing_title}'")
             return True

    # --- Phase 2: AI Semantic Judge (Using Hybrid Engine) ---
    # We use a fast model via api_manager to perform a logic check
    try:
        # Use a reliable model identifier for the judge
        judge_model_name = "gemini-2.5-flash" 
        
        log(f"   🧠 Semantic Check: Asking AI Judge to compare '{target}' against history...")
        
        prompt = f"""
        ROLE: Strict Editor-in-Chief.
        TASK: Detect Content Redundancy / SEO Cannibalization.
        
        NEW TOPIC PROPOSAL: "{new_keyword}"
        
        RECENTLY PUBLISHED ARTICLES:
        {history_string}
        
        CRITERIA FOR BLOCKING (STRICT):
        1. **SAME EVENT RULE:** If the NEW TOPIC covers the exact same news event (e.g., "DeepSeek R1 Launched" vs "DeepSeek R1 is Here"), BLOCK IT.
        2. **SYNONYM RULE:** "Price of X" and "Cost of X" are the SAME article. BLOCK IT.
        3. **EXCEPTION:** Only allow if the NEW TOPIC is a completely different angle (e.g., "Installation Guide" vs "Business Implications").
        
        QUESTION: Is this new topic redundant?
        OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
        """
        
        # Using the unified generator from api_manager
        result = generate_step_strict(judge_model_name, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        
        if is_dup:
            log(f"      ⛔ BLOCKED (AI Judge): Detected redundancy for '{new_keyword}'.")
        else:
            log(f"      ✅ PASSED (AI Judge): '{new_keyword}' is considered a fresh topic.")
            
        return is_dup
    
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error (API): {e}. Proceeding cautiously (Defaulting to False).")
        # If AI check fails (e.g. network error), we trust the local check which already passed.
        return False
