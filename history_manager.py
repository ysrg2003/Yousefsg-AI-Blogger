# FILE: history_manager.py
# DESCRIPTION: Manages knowledge graph and duplication checks.
# RESTORED: Original Semantic Check Prompt.

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
    Hybrid Check: Local Fuzzy + AI Semantic Judge (Original Logic).
    """
    if not history_string or len(history_string) < 10: return False
    
    # 1. Local Check
    target = new_keyword.lower().strip()
    for line in history_string.split('\n'):
        title = line.replace("- ", "").strip().lower()
        if len(target) > 5 and target in title: return True
        if difflib.SequenceMatcher(None, target, title).ratio() > 0.85: return True

    # 2. AI Judge (Original Prompt)
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    log(f"   🧠 Semantic Check: Asking AI Judge ({judge_model})...")
    
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
        return result.get('is_duplicate', False)
    except: return False
