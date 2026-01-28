# FILE: history_manager.py
# ROLE: Manages the knowledge graph, prevents duplicate content, and enables contextual linking.
# CRITICAL FIX (V7.1): Corrected SyntaxError in update_kg and refined logic.

import os
import json
import datetime
import difflib
from config import log
from api_manager import generate_step_strict, CURRENT_MODEL_OVERRIDE

DB_FILE = 'knowledge_graph.json'

def load_kg():
    """
    Loads the knowledge graph history from the JSON file safely.
    """
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log(f"⚠️ Warning: Could not load History DB: {e}")
    return []

# --- THE CRITICAL FIX IS HERE ---
# The function signature now correctly accepts 'post_id' as an optional argument.
def update_kg(title, url, section, post_id=None):
    """
    Updates the Knowledge Graph with a new published article.
    Accepts 'post_id' to enable future updates by the 'Gardener' module.
    """
    try:
        data = load_kg()
        
        # Prevent exact URL duplicates
        if any(item.get('url') == url for item in data):
            return

        # Create the new entry as a dictionary
        new_entry = {
            "title": title,
            "url": url,
            "section": section,
            "date": str(datetime.date.today())
        }

        # If a Blogger Post ID is provided, add it to the dictionary.
        # This logic is now inside the function, not in the dictionary definition.
        if post_id:
            new_entry["post_id"] = post_id
            
        data.append(new_entry)
        
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        log(f"   💾 History updated. Total Knowledge Graph: {len(data)} articles.")
        
    except Exception as e:
        log(f"❌ Error updating Knowledge Graph: {e}")

def perform_maintenance_cleanup():
    """
    Keeps the JSON file size manageable by removing very old entries.
    """
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Keep the last 500 articles.
            if len(data) > 500:
                trimmed_data = data[-500:]
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump(trimmed_data, f, indent=2, ensure_ascii=False)
                log(f"   🧹 Maintenance: Trimmed history DB to last 500 entries.")
    except: pass

def get_recent_titles_string(category=None, limit=100):
    """
    Returns a formatted string of recent titles for AI Context.
    """
    kg = load_kg()
    if not kg: return "No previous articles found."
    
    if category:
        relevant = [i for i in kg if i.get('section') == category]
    else:
        relevant = kg
        
    recent_subset = relevant[-limit:]
    titles = [f"- {i.get('title', 'Unknown Title')}" for i in recent_subset]
    
    if not titles: return "No previous articles in this category."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    """
    Selects 5 relevant past articles for Internal Linking suggestions.
    """
    kg = load_kg()
    same_cat = [i for i in kg if i.get('section') == current_category]
    selected_links = same_cat[-5:]
    
    # Add from other categories if not enough
    if len(selected_links) < 3:
        other_cat = [i for i in kg if i.get('section') != current_category]
        selected_links.extend(other_cat[- (3 - len(selected_links)):])

    formatted_output = [{"title": i['title'], "url": i['url']} for i in selected_links]
    return json.dumps(formatted_output)

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Duplication Check: Fuzzy Matching + AI Semantic Judge.
    """
    if not history_string or len(history_string) < 10: 
        return False
    
    # --- Phase 1: Local Fuzzy Match ---
    target = new_keyword.lower().strip()
    for line in history_string.split('\n'):
        existing_title = line.replace("- ", "").strip().lower()
        
        similarity_ratio = difflib.SequenceMatcher(None, target, existing_title).ratio()
        if similarity_ratio > 0.65:
            log(f"      ⛔ BLOCKED (Local Fuzzy Match): '{target}' is too similar to '{existing_title}'")
            return True

    # --- Phase 2: AI Semantic Judge ---
    try:
        judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
        prompt = f"""
        ROLE: Strict Editor-in-Chief.
        TASK: Detect Content Redundancy.
        NEW TOPIC: "{new_keyword}"
        RECENTLY PUBLISHED:
        {history_string}
        
        QUESTION: Is the NEW TOPIC covering the exact same news event or core idea as any of the recently published articles?
        OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
        """
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        
        if is_dup:
            log(f"      ⛔ BLOCKED (AI Judge): Detected redundancy for '{new_keyword}'.")
        else:
            log(f"      ✅ PASSED (AI Judge): '{new_keyword}' is a fresh topic.")
        return is_dup
    
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error (API): {e}. Proceeding cautiously.")
        # If AI check fails, trust the local check which already passed.
        return False
