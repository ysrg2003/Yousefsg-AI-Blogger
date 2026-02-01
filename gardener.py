# FILE: gardener.py
# ROLE: Updates old content to keep it "Fresh" for Google (The Living Article Protocol).

import json
import datetime
import os
from bs4 import BeautifulSoup
from config import log
from api_manager import generate_step_strict
import publisher  # نستدعي الناشر لتحديث المقالات
import indexer    # نستدعي المفهرس لإعلام جوجل بالتحديث

# برومبت جديد كلياً ومصمم للتحديث الاستراتيجي
PROMPT_LIVING_ARTICLE = """
ROLE: Elite SEO Content Strategist specializing in "Content Refresh" projects.
TASK: Analyze an old article and determine if a modern update is needed. If so, create a strategic update plan.

CONTEXT:
- Current Date: {current_date}
- Original Article Title: "{original_title}"
- Original Article Summary (first 500 chars): "{original_content_summary}"

STRICT DECISION LOGIC:
1.  **Search for Updates:** Perform a quick search. Has there been a significant version change, new features, or a major competitor release since the article was published?
2.  **Evaluate Relevance:** Is the original article now misleading or completely outdated?
3.  **DECIDE:**
    -   If NO major updates exist -> "update_needed": false.
    -   If YES, a significant update exists -> "update_needed": true.

IF "update_needed" is true, YOU MUST PROVIDE:
1.  **new_title:** A new, compelling title. It MUST incorporate the update. (e.g., "Original Title (2026 Update: What's New)").
2.  **update_section:** A concise, powerful HTML section to be ADDED TO THE TOP of the old article. This section should start with `<h2>Update [Current Month Year]: What's Changed?</h2>` and summarize the latest developments.

OUTPUT JSON FORMAT ONLY:
{{
    "update_needed": true/false,
    "new_title": "The refreshed title reflecting the new information",
    "update_section": "<h2>Update February 2026: What's Changed?</h2><p>The landscape has shifted dramatically...[Your summary here]</p>",
    "reason": "Briefly explain why the update is critical for SEO and user trust."
}}
"""

def run_daily_maintenance(config):
    log("\n🧹 [Gardener V2.0] Starting Living Article Maintenance...")
    
    # 1. تحميل الذاكرة (Knowledge Graph)
    kg_path = 'knowledge_graph.json'
    if not os.path.exists(kg_path):
        log("   ✅ No knowledge graph found. Skipping maintenance.")
        return
    with open(kg_path, 'r', encoding='utf-8') as f:
        kg_data = json.load(f)
    
    # 2. البحث عن مقال قديم ومناسب للتحديث
    today = datetime.date.today()
    target_article = None
    
    # نبحث عن أقدم مقال لم يتم تحديثه ومر عليه 90 يوماً
    old_articles = []
    for item in kg_data:
        try:
            post_id = item.get('post_id')
            if not post_id: continue # لا يمكن تحديث مقال بدون ID

            pub_date = datetime.datetime.strptime(item['date'], "%Y-%m-%d").date()
            age_days = (today - pub_date).days
            
            # الأفضلية للمقالات التي لم تُحدّث أبداً
            last_updated_str = item.get('last_updated', "1970-01-01")
            last_updated_date = datetime.datetime.strptime(last_updated_str, "%Y-%m-%d").date()

            if age_days > 90:
                old_articles.append((item, (today - last_updated_date).days))
        except:
            continue

    if not old_articles:
        log("   ✅ No articles require maintenance today.")
        return

    # ترتيب المقالات حسب الأقدمية في التحديث
    old_articles.sort(key=lambda x: x[1], reverse=True)
    target_article = old_articles[0][0]

    log(f"   🥀 Found candidate for revival: '{target_article['title']}' (Post ID: {target_article['post_id']})")
    
    # 3. جلب المحتوى الأصلي من بلوجر
    original_title, original_content = publisher.get_post_by_id(target_article['post_id'])
    if not original_content:
        log("   ❌ Could not fetch original content from Blogger. Aborting update.")
        return
        
    # تنظيف المحتوى لإرساله للـ AI كملخص
    soup = BeautifulSoup(original_content, 'html.parser')
    content_summary = soup.get_text(separator=' ', strip=True)[:500]

    # 4. استشارة الذكاء الاصطناعي لخطة التحديث
    model_name = config['settings'].get('model_name', 'gemini-2.5-flash')
    current_date_str = today.strftime("%B %Y") # e.g., "February 2026"

    prompt = PROMPT_LIVING_ARTICLE.format(
        current_date=today.isoformat(),
        original_title=original_title,
        original_content_summary=content_summary
    )
    
    try:
        decision = generate_step_strict(
            model_name, 
            prompt, 
            "Gardener: Living Article Strategy",
            required_keys=["update_needed"],
            use_google_search=True # مهم جداً للبحث عن تحديثات حقيقية
        )

        if not decision.get('update_needed'):
            log(f"   ✨ Article '{original_title}' is still fresh. Reason: {decision.get('reason')}")
            # نحدث تاريخ الفحص في KG حتى لا نفحصه غداً
            for item in kg_data:
                if item['post_id'] == target_article['post_id']:
                    item['last_updated'] = today.isoformat()
                    break
            with open(kg_path, 'w', encoding='utf-8') as f:
                json.dump(kg_data, f, indent=2)
            return

        # 5. تنفيذ التحديث
        new_title = decision.get('new_title')
        update_section_html = decision.get('update_section')
        log(f"   🚀 Update required! Reason: {decision.get('reason')}")
        log(f"      New Title: {new_title}")

        if not new_title or not update_section_html:
            log("   ⚠️ AI decided to update but failed to provide content. Skipping.")
            return

        # بناء المحتوى الجديد: قسم التحديث + المحتوى الأصلي
        new_full_content = update_section_html + original_content
        
        # 6. دفع التحديث إلى بلوجر
        success = publisher.update_existing_post(target_article['post_id'], new_title, new_full_content)
        
        if success:
            log(f"   ✅ Successfully pushed update to Blogger for '{new_title}'")
            # 7. تحديث الذاكرة وتنبيه جوجل
            article_url = target_article['url']
            for item in kg_data:
                if item['post_id'] == target_article['post_id']:
                    item['title'] = new_title # تحديث العنوان في ذاكرتنا
                    item['last_updated'] = today.isoformat()
                    item['update_count'] = item.get('update_count', 0) + 1
                    break
            
            with open(kg_path, 'w', encoding='utf-8') as f:
                json.dump(kg_data, f, indent=2)

            # إرسال إشعار لجوجل لإعادة الأرشفة
            indexer.submit_url(article_url)

    except Exception as e:
        log(f"   ❌ Gardener V2.0 crashed during AI strategy phase: {e}")
