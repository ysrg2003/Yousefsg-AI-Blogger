# FILE: gardener.py
# ROLE: Updates old content to keep it "Fresh" for Google.

import json
import datetime
import requests
import os
from config import log
from api_manager import generate_step_strict
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def get_blogger_service():
    # يستخدم نفس توكن النشر الموجود في publisher.py
    # للتبسيط سنفترض وجود دالة لجلب الـ Credentials أو التوكن
    # هنا سنستخدم Requests مباشرة مع التوكن المجدد لسهولة الدمج
    from publisher import get_blogger_token
    return get_blogger_token()

def run_daily_maintenance(config):
    log("\n🧹 [Gardener] Starting Maintenance Check...")
    
    # 1. تحميل الذاكرة
    if not os.path.exists('knowledge_graph.json'): return
    with open('knowledge_graph.json', 'r') as f: kg = json.load(f)
    
    # 2. البحث عن مقال قديم (مر عليه أكثر من 60 يوم)
    today = datetime.date.today()
    target_article = None
    
    for item in kg:
        try:
            pub_date = datetime.datetime.strptime(item['date'], "%Y-%m-%d").date()
            age_days = (today - pub_date).days
            if age_days > 60 and not item.get('last_updated'):
                target_article = item
                break
        except: continue
        
    if not target_article:
        log("   ✅ No articles need maintenance today.")
        return

    log(f"   🥀 Found old article: '{target_article['title']}'. Attempting revival...")
    
    # 3. البحث عن تحديثات (News Fetcher)
    # هنا نستخدم منطق بسيط: نسأل Gemini إذا كان هناك تحديث
    model_name = config['settings'].get('model_name')
    prompt = f"""
    TASK: Check if this topic is outdated: "{target_article['title']}".
    If yes, write a short "Update Paragraph" (2-3 sentences) starting with "UPDATE [Current Date]:".
    If no major changes, return JSON with "update_needed": false.
    """
    
    try:
        res = generate_step_strict(model_name, prompt, "Gardener Check")
        if res.get('update_needed') == False:
            log("   ✨ Article is still fresh.")
            # نحدث التاريخ في KG حتى لا نفحصه غداً
            target_article['last_updated'] = str(today)
            with open('knowledge_graph.json', 'w') as f: json.dump(kg, f, indent=2)
            return

        update_text = res.get('update_text')
        if update_text:
            # 4. التحديث في بلوجر (سنحتاج Post ID، وهذا يتطلب تخزينه في KG مستقبلاً)
            # بما أننا لم نخزن Post ID سابقاً، سنكتفي بتسجيل الملاحظة الآن
            # في النسخة القادمة يجب تعديل publisher.py ليحفظ Post ID في knowledge_graph.json
            log(f"   ⚠️ Update ready: {update_text[:50]}... (Skipping actual push due to missing Post ID in KG)")
            
    except Exception as e:
        log(f"   ❌ Gardener Error: {e}")
