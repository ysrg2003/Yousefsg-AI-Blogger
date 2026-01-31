# FILE: cluster_manager.py
# ROLE: Manages Topic Clusters (Silos) to build SEO Authority.
# UPDATED: Generic "Version Hunter" Logic - Works for ANY category.

import json
import os
import datetime
from config import log
from api_manager import generate_step_strict

CLUSTER_FILE = "content_plan.json"

def load_plan():
    if os.path.exists(CLUSTER_FILE):
        try:
            with open(CLUSTER_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"active_cluster": None, "queue": [], "completed": []}

def save_plan(data):
    with open(CLUSTER_FILE, 'w') as f: json.dump(data, f, indent=2)

def generate_new_cluster(category, model_name):
    """
    يولد خطة محتوى ذكية تعتمد على البحث المباشر عن أحدث الإصدارات 
    بغض النظر عن نوع الفئة (فيديو، برمجة، صوت، تسويق...).
    """
    log(f"   🧠 [Cluster Manager] Scanning for the absolute latest trends in: {category}...")
    
    today_date = datetime.date.today()
    
    # البرومبت "الجوكر" - لا يحتوي على أسماء محددة بل "منطق بحث"
    prompt = f"""
    ROLE: Elite Tech Trend Analyst & Version Hunter.
    CURRENT DATE: {today_date} (We are strictly in the present/future).
    TARGET CATEGORY: "{category}".
    
    🛑 DYNAMIC VERSION DISCOVERY PROTOCOL (EXECUTE STEP-BY-STEP):
    1. **SEARCH PHASE:** Search Google for "Latest {category} tools releases {today_date.year}".
    2. **VERSION CHECK:** Identify the top 2 market leaders in this category.
       - If your internal memory says "Tool v3" is latest, explicitly search: "Is Tool v4 released?".
       - If "Tool v5" exists in search results, IGNORE your memory and write about v5.
    3. **IGNORE OLD TECH:** If a tool hasn't had a major update in 6 months, find a newer competitor that *did* update recently.
    4. **CONTENT PLAN:** Create a 4-part series about the SINGLE most exciting *new* tool or update found in step 1.
    
    OUTPUT JSON ONLY:
    {{
      "cluster_name": "e.g., [Newest Tool Name] [Version] Mastery Series",
      "topics": [
        "Topic 1 (The Hook: Review of [Newest Tool] [Latest Version] - Is it a Game Changer?)",
        "Topic 2 (The Guide: How to master [New Feature] in [Latest Version])",
        "Topic 3 (The Comparison: [Latest Version] vs [Previous Version] vs Competitor)",
        "Topic 4 (The Future/Advanced: Hidden tricks in [Latest Version])"
      ]
    }}
    """
    try:
        # تفعيل البحث (Google Search) إلزامي هنا
        plan = generate_step_strict(
            model_name, 
            prompt, 
            "Cluster Generation", 
            required_keys=["cluster_name", "topics"],
            use_google_search=True 
        )
        return plan
    except: return None

def get_strategic_topic(category, config):
    """الدالة الرئيسية التي تستدعيها main.py"""
    data = load_plan()
    model_name = config['settings'].get('model_name')

    # 1. هل هناك عنقود نشط وفيه مقالات متبقية؟
    if data.get('active_cluster') and data.get('queue'):
        next_topic = data['queue'].pop(0)
        log(f"   🔗 [Cluster Strategy] Continuing series '{data['active_cluster']}': {next_topic}")
        save_plan(data)
        return next_topic, True 

    # 2. إذا انتهى العنقود أو لم يوجد، ننشئ واحداً جديداً
    log("   🆕 [Cluster Strategy] No active series. Generating new cluster...")
    new_plan = generate_new_cluster(category, model_name)
    
    if new_plan and new_plan.get('topics'):
        data['active_cluster'] = new_plan['cluster_name']
        data['queue'] = new_plan['topics']
        
        # نأخذ الموضوع الأول فوراً
        first_topic = data['queue'].pop(0)
        save_plan(data)
        log(f"   🚀 [Cluster Strategy] Starting NEW series '{new_plan['cluster_name']}': {first_topic}")
        return first_topic, True
    
    # 3. الفشل
    log("   ⚠️ Cluster generation failed. Falling back to Daily Hunt.")
    return None, False
