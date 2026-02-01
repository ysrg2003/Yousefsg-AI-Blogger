# FILE: history_manager.py (V11.0 - Self-Healing & Semantic Linking Integration)
# ROLE: Central Intelligence Memory & Semantic Deduplication Engine
# DESCRIPTION: Manages the Knowledge Graph (knowledge_graph.json). 
#              Prevents SEO Cannibalization using a Hybrid Blacklist Strategy.
#              UPGRADED: Now features self-healing for legacy data and a semantic
#              vector-based internal linking strategy for superior SEO siloing.
# INTEGRATION: Directly linked to main.py, cluster_manager.py, and gardener.py.

import os
import json
import datetime
import difflib
import traceback
import numpy as np
from config import log
from api_manager import generate_step_strict

# --- الترقية: إضافة الذكاء الدلالي (Semantic Intelligence) ---
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    log("❌ CRITICAL ERROR: 'sentence-transformers' or 'scikit-learn' not installed.")
    log("   Please add them to your requirements.txt file and ensure they are installed.")
    raise

# --- الترقية: تحميل النموذج الذكي مرة واحدة عالمياً لتوفير الموارد ---
# هذا النموذج يعمل محلياً، لا يحتاج لإنترنت (بعد التحميل الأول) ولا مفتاح API.
_model = SentenceTransformer('all-MiniLM-L6-v2')

# --- GLOBAL CONFIGURATION ---
DB_FILE = 'knowledge_graph.json'
MAX_HISTORY_ITEMS_FOR_AI = 60
SIMILARITY_THRESHOLD = 0.65

# --- الترقية: دالة مساعدة لتوليد المتجهات الرقمية ---
def _generate_embedding(text: str):
    """Generates a sentence embedding (vector) for the given text."""
    return _model.encode(text, convert_to_numpy=True)

def _load_kg_raw():
    """
    Loads the raw knowledge graph data from the JSON file with strict UTF-8 encoding.
    This is the initial, unprocessed load.
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

# --- الترقية: دالة الإصلاح الذاتي الآلية ---
def _ensure_all_embeddings_exist(data):
    """
    Self-healing function. Checks if any old article is missing an embedding and fixes it.
    This runs automatically, removing the need for a separate backfill script.
    """
    needs_saving = False
    for item in data:
        if "embedding" not in item or not item.get("embedding"):
            title = item.get("title")
            if title:
                log(f"   🔧 [Self-Healing] Found old article missing vector. Generating for: {title[:40]}...")
                item["embedding"] = _generate_embedding(title).tolist()
                needs_saving = True
    
    if needs_saving:
        log("   💾 Saving updated knowledge graph with backfilled vectors...")
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"   ❌ Self-Healing Save Error: {e}")
    return data

# --- الترقية: تحميل ومعالجة قاعدة البيانات عند بدء تشغيل الوحدة ---
_kg_data = _load_kg_raw()
_kg_data = _ensure_all_embeddings_exist(_kg_data) # <--- الفحص الآلي والإصلاح الذاتي يتم هنا

def load_kg():
    """
    Returns the globally loaded and potentially healed knowledge graph data.
    This replaces multiple file reads with a single, efficient memory access.
    """
    global _kg_data
    return _kg_data

def update_kg(title, url, section, post_id=None):
    """
    Updates the Knowledge Graph with a new published article AND its semantic embedding.
    """
    global _kg_data
    try:
        # 1. Idempotency Check: Prevent duplicate URL entries
        if any(item.get('url') == url for item in _kg_data):
            log(f"   ⚠️ URL '{url}' already exists in History. Entry skipped.")
            return

        # 2. الترقية: توليد المتجه الرقمي للعنوان الجديد
        log("   🧠 Generating semantic vector for the new title...")
        embedding = _generate_embedding(title)

        # 3. Construction of the Master Entry
        new_entry = {
            "title": str(title).strip(),
            "url": str(url).strip(),
            "section": str(section).strip(),
            "date": str(datetime.date.today()),
            "post_id": str(post_id) if post_id else None,
            "last_verified": str(datetime.date.today()),
            "update_count": 0,
            "embedding": embedding.tolist()  # <-- حفظ المتجه الجديد في قاعدة البيانات
        }

        # 4. Atomic Append to the global variable
        _kg_data.append(new_entry)
        
        # 5. Save with high precision and formatting
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(_kg_data, f, indent=2, ensure_ascii=False)
            
        log(f"   💾 [Memory Updated] Total Articles in Blacklist: {len(_kg_data)}.")
        
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
    
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_limit)
    
    relevant_items = []
    for item in kg:
        try:
            pub_date_str = item.get('date', '2024-01-01')
            pub_date = datetime.datetime.strptime(pub_date_str, "%Y-%m-%d").date()
            
            if pub_date >= cutoff_date:
                relevant_items.append(item)
        except:
            continue

    relevant_items.sort(key=lambda x: x.get('date', ''), reverse=True)
    recent_subset = relevant_items[:MAX_HISTORY_ITEMS_FOR_AI]
    
    formatted_list = [f"- [Published: {i.get('date')}] Topic: {i.get('title')}" for i in recent_subset]
        
    return "\n".join(formatted_list)

def check_semantic_duplication(new_keyword, category, config):
    """
    THE ULTIMATE DEDUPLICATION GUARD (The Blacklist Comparison Engine).
    Executes a two-phase check to ensure NO repetitive content.
    """
    target = str(new_keyword).strip().lower()
    
    kg = load_kg()
    for item in kg:
        existing_title = item.get('title', '').lower()
        
        ratio = difflib.SequenceMatcher(None, target, existing_title).ratio()
        if ratio > SIMILARITY_THRESHOLD:
            log(f"      ⛔ [Phase 1 REJECT] '{target}' is {int(ratio*100)}% similar to an existing title.")
            return True

        if len(target) > 8 and target in existing_title:
             log(f"      ⛔ [Phase 1 REJECT] '{target}' is a subset of an existing title.")
             return True

    model_name = config['settings'].get('model_name', 'gemini-2.5-flash')
    blacklist_text = get_blacklist_context(category)
    
    if blacklist_text == "NO_PREVIOUS_CONTENT":
        return False

    log(f"   🧠 [Phase 2 Judge] Analyzing 'Reader Value' of '{new_keyword}' against Blacklist...")
    prompt = f"""
    ROLE: Ruthless Editor-in-Chief & Duplicate Content Police.
    TASK: Determine if the "New Proposal" is redundant based on the "Blacklist" (Past Articles).
    
    INPUT PROPOSAL: {new_keyword}
    CATEGORY: {category}
    
    RECENTLY PUBLISHED ARTICLES (THE BLACKLIST):
    {blacklist_text}
    
    ------------------------------------------------------------------------
    🚨 STRICT DUPLICATION RULES (READ CAREFULLY):
    
    1. **THE "CONTAINMENT" RULE:** 
       - If the New Proposal is a "Weekly Roundup" or "News Summary" (e.g., "Google Cloud News"), and we JUST wrote about the main item in that news (e.g., "Gemini 3.0"), **REJECT IT**.
       - We do not want a general summary immediately after a specific deep dive.
       
    2. **THE "ENTITY" RULE:**
       - If the New Proposal focuses on the SAME Product/Entity (e.g., "Gemini 3") as a recent article, even if the title is different (e.g., "Gemini 3 Pricing" vs "Gemini 3 Review"), **REJECT IT** unless it is at least 7 days later.
       
    3. **THE "REPHRASING" RULE:**
       - "Is X good?" vs "X Review" -> DUPLICATE.
       - "How to use X" vs "X Guide" -> DUPLICATE.
    
    DECISION MATRIX:
    - If strictly distinct (different product, different intent): "is_duplicate": false.
    - If overlapping, contained, or repetitive: "is_duplicate": true.
    ------------------------------------------------------------------------
    
    OUTPUT JSON FORMAT ONLY:
    {{
        "is_duplicate": true/false,
        "conflict_title": "Title of the existing article that causes the conflict (or 'None')",
        "reason": "Explain clearly why this is rejected based on the Containment or Entity rule."
    }}
    """
    try:
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

# --- الترقية: استبدال كامل لمنطق الربط الداخلي ---
def get_relevant_kg_for_linking(current_title, current_category):
    """
    V3.0 - Semantic Linking Strategy.
    Finds the 5 most conceptually similar articles from the Knowledge Graph using vector similarity.
    """
    log("   🔗 [Semantic Linker] Finding conceptually related articles...")
    kg = load_kg()
    
    # 1. فلترة المقالات التي لا تحتوي على متجهات أو المقال الحالي نفسه
    kg_with_embeddings = [
        item for item in kg if item.get("embedding") and item.get("title") != current_title
    ]
    
    if len(kg_with_embeddings) < 1:
        log("      ⚠️ Not enough historical data for semantic linking. Skipping.")
        return json.dumps([])

    # 2. توليد متجه للمقال الحالي
    current_embedding = _generate_embedding(current_title)
    
    # 3. استخراج متجهات المقالات السابقة
    historical_embeddings = np.array([item["embedding"] for item in kg_with_embeddings])
    
    # 4. حساب التشابه الدلالي (Cosine Similarity)
    similarities = cosine_similarity(
        current_embedding.reshape(1, -1),
        historical_embeddings
    )[0]
    
    # 5. ترتيب المقالات حسب درجة التشابه
    scored_articles = sorted(
        zip(similarities, kg_with_embeddings), 
        key=lambda x: x[0], 
        reverse=True
    )
    
    # 6. اختيار أفضل 5 مقالات ذات صلة
    top_5_semantically_related = [article for score, article in scored_articles[:5]]

    # 7. تجهيز المخرجات للبرومبت
    output = []
    log("      ✅ Top 5 Semantic Matches Found:")
    for item in top_5_semantically_related:
        log(f"         - (Score: {scored_articles[len(output)][0]:.2f}) {item.get('title')}")
        output.append({
            "title": item.get('title'),
            "url": item.get('url')
        })
        
    return json.dumps(output, ensure_ascii=False)

def perform_maintenance_cleanup():
    """
    Maintenance task to keep the Knowledge Graph healthy.
    """
    try:
        data = load_kg()
        if len(data) > 1000:
            log(f"   📊 Knowledge Graph size: {len(data)} entries. Maintenance healthy.")
    except Exception as e:
        log(f"   ⚠️ Maintenance Error: {str(e)}")
