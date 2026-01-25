# FILE: history_manager.py
# DESCRIPTION: Manages the knowledge_graph.json, providing functions to read, write,
#              and check for semantic duplication using a hybrid local/AI approach.

import json
import datetime
import difflib
from config import log
from api_manager import generate_step_strict, CURRENT_MODEL_OVERRIDE

def load_kg():
    """Loads the knowledge graph from file."""
    try:
        if os.path.exists('knowledge_graph.json'): 
            with open('knowledge_graph.json', 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return []

def update_kg(title, url, section):
    """Adds a new article to the knowledge graph."""
    try:
        data = load_kg()
        if any(item['url'] == url for item in data):
            return
        data.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
        with open('knowledge_graph.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log(f"   ⚠️ Could not update knowledge graph: {e}")

def perform_maintenance_cleanup():
    """Trims the knowledge graph to prevent it from becoming too large."""
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f:
                d = json.load(f)
            if len(d) > 800:
                json.dump(d[-400:], open('knowledge_graph.json', 'w'), indent=2)
                log("   🧹 Performed knowledge graph maintenance.")
    except Exception as e:
        log(f"   ⚠️ Maintenance cleanup failed: {e}")

def get_recent_titles_string(category=None, limit=100):
    """Gets a formatted string of recent titles for use in prompts."""
    kg = load_kg()
    if not kg: return "No previous articles found."
    
    if category: 
        relevant_items = [i for i in kg if i.get('section') == category]
    else: 
        relevant_items = kg
        
    recent_items = relevant_items[-limit:]
    titles = [f"- {i.get('title','Unknown')}" for i in recent_items]
    if not titles: return f"No previous articles found in this category."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category):
    """Finds relevant past articles for internal linking."""
    kg = load_kg()
    same_cat = [i for i in kg if i.get('section') == current_category]
    other_cat = [i for i in kg if i.get('section') != current_category]
    
    relevant_others = []
    current_keywords = set(current_title.lower().split())
    for item in other_cat:
        item_keywords = set(item['title'].lower().split())
        if len(current_keywords.intersection(item_keywords)) >= 2:
            relevant_others.append(item)
            
    # Prioritize same-category links
    final_list = same_cat[:4] + relevant_others[:2] 
    return json.dumps([{"title": i['title'], "url": i['url']} for i in final_list])

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Check: Uses fast local check first, then a precise AI judge.
    """
    if not history_string or len(history_string) < 10: return False
    
    # 1. LOCAL CHECK (Fast & Free)
    target = new_keyword.lower().strip()
    existing_titles = [line.replace("- ", "").strip().lower() for line in history_string.split('\n') if line.strip()]
    
    for title in existing_titles:
        if len(target) > 5 and (target in title or title in target):
            log(f"      ⛔ BLOCKED (Local Exact): '{title}'")
            return True
        similarity = difflib.SequenceMatcher(None, target, title).ratio()
        if similarity > 0.85:
            log(f"      ⛔ BLOCKED (Local Fuzzy): {int(similarity*100)}% match with '{title}'")
            return True

    # 2. AI JUDGE (Precise)
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    log(f"   🧠 Semantic Check: Asking AI Judge ({judge_model}) about '{new_keyword}'...")
    
    prompt = f"""
    TASK: Duplication Check.
    NEW TOPIC: "{new_keyword}"
    PAST ARTICLES:
    {history_string}
    
    QUESTION: Is "NEW TOPIC" covering the exact same event/story as any "PAST ARTICLES"?
    OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
    """
    try:
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        if is_dup: log("      ⛔ BLOCKED (AI): Duplicate detected.")
        else: log("      ✅ PASSED (AI): Unique.")
        return is_dup
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error: {e}. Assuming safe.")
        return False
