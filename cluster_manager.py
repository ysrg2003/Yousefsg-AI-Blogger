# FILE: cluster_manager.py
# ROLE: Manages Topic Clusters (Silos) to build SEO Authority.

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
    """يطلب من الذكاء الاصطناعي خطة محتوى كاملة (سلسلة) بدلاً من مقال واحد"""
    log(f"   🧠 [Cluster Manager] Designing a new content series for: {category}...")
    
    prompt = f"""
    ROLE: SEO Content Strategist.
    TASK: Create a "Topic Cluster" (Series of 4 connected articles) for the category: "{category}".
    GOAL: Dominate a specific niche trend currently happening.
    
    RULES:
    1. The topics must be sequential (Beginner -> Advanced -> Comparison -> Future).
    2. They must be highly searchable keywords.
    3. Do NOT use generic titles. Use specific product names or problems.
    
    OUTPUT JSON:
    {{
      "cluster_name": "e.g., DeepSeek Mastery Series",
      "topics": [
        "Topic 1 (The Hook/News)",
        "Topic 2 (The How-To/Guide)",
        "Topic 3 (The Comparison/Vs)",
        "Topic 4 (The Advanced/Hidden Features)"
      ]
    }}
    """
    try:
        plan = generate_step_strict(model_name, prompt, "Cluster Generation", required_keys=["cluster_name", "topics"])
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
        return next_topic, True # True تعني "هذا جزء من سلسلة"

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
    
    # 3. الفشل (العودة للنظام القديم)
    log("   ⚠️ Cluster generation failed. Falling back to Daily Hunt.")
    return None, False
