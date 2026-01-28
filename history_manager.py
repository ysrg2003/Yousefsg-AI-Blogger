# FILE: history_manager.py
# DESCRIPTION: Manages the knowledge graph, prevents duplicate content, and enables contextual linking.
# UPGRADES: Added 'post_id' support for Gardener module + 'Paranoid' semantic deduplication.

import os
import json
import datetime
import difflib
from config import log
from api_manager import generate_step_strict, CURRENT_MODEL_OVERRIDE

# Path to the JSON database
DB_FILE = 'knowledge_graph.json'

def load_kg():
    """
    Loads the knowledge graph history from the JSON file.
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
    CRITICAL FIX: Now accepts 'post_id' to enable the 'Gardener' module updates.
    """
    try:
        data = load_kg()
        
        # Avoid exact URL duplicates
        if any(item.get('url') == url for item in data):
            return

        new_entry = {
            "title": title,
            "url": url,
            "section": section,
            "date": str(datetime.date.today())
        }

        # If a Blogger Post ID is provided, save it for future updates
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
    Keeps the JSON file size manageable by removing very old entries
    while keeping enough history for SEO linking strategies.
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
        pass

def get_recent_titles_string(category=None, limit=100):
    """
    Returns a formatted string of recent titles to feed into the AI Context.
    """
    kg = load_kg()
    if not kg: return "No previous articles found."
    
    if category:
        relevant = [i for i in kg if i.get('section') == category]
    else:
        relevant = kg
        
    # Get the last 'limit' items
    recent_subset = relevant[-limit:]
    
    titles = [f"- {i.get('title', 'Unknown Title')}" for i in recent_subset]
    
    if not titles: return "No previous articles in this category."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    """
    Selects 5 relevant past articles to suggest as Internal Links in the new article.
    Prioritizes same category, then attempts title matching.
    """
    kg = load_kg()
    
    # 1. Filter by same category (Priority)
    same_cat = [i for i in kg if i.get('section') == current_category]
    
    # 2. Select recent ones (Logic: fresher content is better for linking)
    selected_links = same_cat[-5:]
    
    # 3. If we don't have enough, grab some from other categories purely for volume
    if len(selected_links) < 3:
        other_cat = [i for i in kg if i.get('section') != current_category]
        selected_links.extend(other_cat[- (3 - len(selected_links)):])

    formatted_output = [{"title": i['title'], "url": i['url']} for i in selected_links]
    return json.dumps(formatted_output)

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Duplication Check: 
    1. Local String Fuzzy Matching (Fast/Cheap)
    2. AI Semantic Judge (Smart/Contextual) - Prevents 'Cannibalization'.
    """
    if not history_string or len(history_string) < 10: 
        return False
    
    # --- PHASE 1: LOCAL HEURISTICS (Fuzzy Match) ---
    target = new_keyword.lower().strip()
    
    # Extract "Core Entity" to prevent redundancy on specific products (e.g. "Sora Price" vs "Sora Cost")
    target_tokens = target.split()
    main_entity = max(target_tokens, key=len) if target_tokens else target

    for line in history_string.split('\n'):
        existing_title = line.replace("- ", "").strip().lower()
        
        # High fuzzy similarity means it's likely a duplicate
        similarity_ratio = difflib.SequenceMatcher(None, target, existing_title).ratio()
        
        # Threshold 0.65 is strict to catch variations of the same news
        if similarity_ratio > 0.65:
            log(f"      ⛔ BLOCKED (Local Fuzzy Match): '{target}' is {int(similarity_ratio*100)}% similar to '{existing_title}'")
            return True

        # Special Check: If short titles match key words too closely
        if len(target) > 5 and target in existing_title:
             log(f"      ⛔ BLOCKED (Local Substring): '{target}' found in '{existing_title}'")
             return True

    # --- PHASE 2: AI SEMANTIC JUDGE (Paranoid Mode) ---
    # Using the overridden model or a reliable Flash model for logic
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    
    log(f"   🧠 Semantic Check: Asking AI Judge ({judge_model}) for deep comparison...")
    
    prompt = f"""
    ROLE: Strict Editor-in-Chief.
    TASK: Detect Content Redundancy / Cannibalization.
    
    NEW TOPIC PROPOSAL: "{new_keyword}"
    
    RECENTLY PUBLISHED ARTICLES:
    {history_string}
    
    CRITERIA FOR BLOCKING (STRICT):
    1. **SAME PRODUCT/EVENT RULE:** If the NEW TOPIC covers the exact same news event (e.g., "DeepSeek R1 Launched" vs "DeepSeek R1 is Here"), BLOCK IT.
    2. **SYNONYM RULE:** "Price of X" and "Cost of X" are the SAME article. BLOCK.
    3. **EXCEPTION:** Only allow if the NEW TOPIC is a completely different angle (e.g., "Installation Guide" vs "Business Implications").
    
    QUESTION: Is this new topic redundant?
    OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
    """
    
    try:
        # Re-using the tenacity-protected generator from api_manager
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        
        if is_dup:
            log(f"      ⛔ BLOCKED (AI Judge): Detected redundancy for '{new_keyword}'.")
        else:
            log(f"      ✅ PASSED (AI Judge): '{new_keyword}' is considered fresh.")
            
        return is_dup
    
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error (API): {e}. Proceeding cautiously.")
        # If AI check fails, rely on the Local Fuzzy check we did earlier (which returned False to get here)
        return False
