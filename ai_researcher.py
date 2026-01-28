# FILE: ai_researcher.py
# ROLE: An elite autonomous agent that uses Google Grounding to find verified, high-quality sources.
# FEATURES: Strict quality filtering, JSON structured output, real-time verification.

import json
import re
import time
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager

# القائمة السوداء الصارمة للمصادر التي لا نريدها كمراجع تقنية
LOW_QUALITY_DOMAINS = [
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com", "medium.com", 
    "facebook.com", "instagram.com", "tiktok.com", "vocal.media", "newsbreak.com",
    "msn.com", "aol.com", "yahoo.com"
]

def extract_urls_fallback(text):
    """
    استخراج الروابط باستخدام Regex في حال فشل تحليل JSON.
    """
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    found = url_pattern.findall(text)
    # تنظيف الروابط من أي بقايا جوجل
    clean_links = []
    for link in found:
        if "google.com" not in link and not any(bad in link for bad in LOW_QUALITY_DOMAINS):
            clean_links.append(link)
    return list(set(clean_links)) # إزالة التكرار

def smart_hunt(topic, config):
    """
    المهمة: الذهاب إلى جوجل، البحث، الفلترة، وإعادة أفضل 3-5 مصادر موثوقة.
    """
    # نستخدم الموديل الذي يدعم Grounding (Flash 2.0 ممتاز في السرعة والدقة)
    # ملاحظة: يمكنك تغييره حسب المتاح في مفتاحك، لكن 2.0 هو الأفضل للبحث حالياً
    model_name = "gemini-2.0-flash-exp" 
    
    log(f"   🕵️‍♂️ [AI Researcher] Conducting deep web search for: '{topic}'...")
    
    key = key_manager.get_current_key()
    if not key:
        log("      ❌ API Key Error.")
        return []

    client = genai.Client(api_key=key)
    
    # 1. إعداد أداة البحث (Google Search Tool)
    google_search_tool = types.Tool(
        google_search_retrieval=types.GoogleSearchRetrieval(
            dynamic_retrieval_config=types.DynamicRetrievalConfig(
                mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
                dynamic_threshold=0.3
            )
        )
    )

    # 2. البرومبت "الصارم" (The Strict Prompt)
    system_instruction = """
    You are an Elite Technical Researcher for a high-authority tech publication.
    Your Job: verify facts and find the PRIMARY sources for a specific tech topic.
    
    STRICT FILTERING RULES (DO NOT IGNORE):
    1. PRIORITIZE: Official Documentation, GitHub Repositories, Major Tech Publications (The Verge, TechCrunch, Arstechnica, Wired), and University Papers (.edu).
    2. BAN: User-Generated Content (Reddit, Quora, LinkedIn), Social Media, Generic News Aggregators (MSN, Yahoo), and Content Farms.
    3. FRESHNESS: Sources must be RECENT (last 30 days) unless the topic is a fundamental tutorial.
    4. ACCURACY: Return the DIRECT article URL, not a home page.
    """

    user_prompt = f"""
    TOPIC: "{topic}"
    
    MISSION: 
    Search Google, analyze the results, and select the TOP 3-5 absolute best, most authoritative articles covering this exact topic.
    
    OUTPUT FORMAT (Return RAW JSON only):
    [
        {{
            "title": "Actual Page Title",
            "link": "https://exact-url.com/article",
            "snippet": "Brief summary of technical value",
            "date": "Published Date or 'Recent'"
        }}
    ]
    """

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.3 # حرارة منخفضة للدقة
            )
        )
        
        # 3. معالجة الرد وتنظيفه
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        
        sources = []
        try:
            parsed_data = json.loads(raw_text)
            
            # 4. التدقيق الثانوي (Double-Check) في الكود
            for item in parsed_data:
                url = item.get('link') or item.get('url') # التعامل مع اختلاف التسمية المحتمل
                title = item.get('title', 'Source')
                
                if not url: continue
                
                # تصفية النطاقات السيئة مرة أخرى للتأكيد
                domain = url.split("//")[-1].split("/")[0].lower()
                if any(bad in domain for bad in LOW_QUALITY_DOMAINS):
                    continue
                
                # تجاهل روابط جوجل الداخلية
                if "google.com" in domain:
                    continue

                sources.append({
                    "title": title,
                    "link": url,
                    "date": item.get('date', 'Today'),
                    "snippet": item.get('snippet', '')
                })

        except json.JSONDecodeError:
            log("      ⚠️ JSON Parsing failed. Attempting regex extraction...")
            # خطة بديلة: استخراج الروابط بالبحث النصي
            found_links = extract_urls_fallback(raw_text)
            for link in found_links:
                sources.append({"title": "AI Discovered Source", "link": link, "date": "Recent"})

        if sources:
            log(f"      ✅ [AI Researcher] Identified {len(sources)} high-quality targets.")
            return sources[:5] # نكتفي بأفضل 5
        else:
            log("      ⚠️ AI Researcher searched but found no quality sources matching criteria.")
            return []

    except Exception as e:
        log(f"      ❌ AI Researcher Critical Error: {e}")
        return []
