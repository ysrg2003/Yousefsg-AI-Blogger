# FILE: history_manager.py
# DESCRIPTION: Manages knowledge graph and duplication checks.
# UPDATED: "Paranoid Mode" to prevent same-product redundancy (e.g. Sora Price vs Sora Realism).

import os
import json
import datetime
import difflib
from config import log
from api_manager import generate_step_strict, CURRENT_MODEL_OVERRIDE

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): 
            with open('knowledge_graph.json', 'r') as f: return json.load(f)
    except: pass
    return []

def update_kg(title, url, section):
    try:
        data = load_kg()
        if any(item['url'] == url for item in data): return
        data.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
        with open('knowledge_graph.json', 'w') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f: d = json.load(f)
            if len(d) > 800:
                json.dump(d[-400:], open('knowledge_graph.json', 'w'), indent=2)
    except: pass

def get_recent_titles_string(category=None, limit=100):
    kg = load_kg()
    if not kg: return "No previous articles found."
    if category: relevant = [i for i in kg if i.get('section') == category]
    else: relevant = kg
    titles = [f"- {i.get('title','Unknown')}" for i in relevant[-limit:]]
    if not titles: return "No previous articles."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    kg = load_kg()
    same_cat = [i for i in kg if i.get('section') == current_category]
    return json.dumps([{"title": i['title'], "url": i['url']} for i in same_cat[:5]])

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Check: Local Fuzzy + AI Semantic Judge (Paranoid Edition).
    Prevents 'Cannibalization' (e.g., two articles about Sora 2 on the same day).
    """
    if not history_string or len(history_string) < 10: return False
    
    # 1. Local Check (Stricter Fuzzy Match)
    target = new_keyword.lower().strip()
    
    # Extract main entity (longest word) to catch things like "Sora", "Gemini"
    target_tokens = target.split()
    main_entity = max(target_tokens, key=len) if target_tokens else target

    for line in history_string.split('\n'):
        title = line.replace("- ", "").strip().lower()
        
        # If the exact main entity is in a recent title, be very suspicious
        if len(main_entity) > 3 and main_entity in title:
            # We don't return True immediately, but we let the AI know this is high risk
            pass 

        # Lowered threshold from 0.85 to 0.65 to catch "Sora Price" vs "Sora Features"
        if difflib.SequenceMatcher(None, target, title).ratio() > 0.65: 
            log(f"      ⛔ BLOCKED (Fuzzy Match): '{target}' too similar to '{title}'")
            return True

    # 2. AI Judge (Paranoid Prompt)
    # Using gemini-2.5-flash as default for better logic reasoning than 3-flash-preview
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-2.5-flash"
    
    log(f"   🧠 Semantic Check: Asking AI Judge ({judge_model}) to be STRICT...")
    
    prompt = f"""
    ROLE: Strict Editor-in-Chief.
    TASK: Detect Content Redundancy / Cannibalization.
    
    NEW TOPIC PROPOSAL: "{new_keyword}"
    
    RECENTLY PUBLISHED ARTICLES:
    {history_string}
    
    CRITERIA FOR BLOCKING (STRICT):
    1. **SAME PRODUCT RULE:** If the NEW TOPIC is about a specific product (e.g., "Sora", "Gemini", "iPhone") and we ALREADY have a recent article about that SAME product, return TRUE.
    2. **DIFFERENT ANGLES ARE NOT ENOUGH:** "Sora Price" and "Sora Realism" are the SAME story (The launch of Sora). Do not allow multiple articles on the same launch.
    3. **EXCEPTION:** Only allow if it is a COMPLETELY different event (e.g., "Product Release" vs "Major Scandal" months later).
    
    QUESTION: Should we BLOCK this new topic to prevent redundancy?
    OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
    """
    
    try:
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        
        if is_dup:
            log(f"      ⛔ BLOCKED (AI Judge): Detected redundancy for '{new_keyword}'.")
        else:
            log(f"      ✅ PASSED (AI Judge): '{new_keyword}' is a fresh topic.")
            
        return is_dup
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error: {e}. Assuming safe to proceed.")
        return False
