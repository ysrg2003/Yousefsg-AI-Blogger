# FILE: ai_researcher.py
# ROLE: Elite autonomous agent using Google Grounding for verified, high-quality research.
# FEATURES: 
#   1. Query Decomposition: Breaks down long topics into smart search queries.
#   2. Multi-Mode Research: Can hunt for general news, official docs, or visual evidence.
#   3. Syntactically Correct: Uses the proper method for calling Gemini with Tools.

import json
import re
import time
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager

# Strict blacklist of domains to avoid for authoritative research
LOW_QUALITY_DOMAINS = [
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com", "medium.com", 
    "facebook.com", "instagram.com", "tiktok.com", "vocal.media", "newsbreak.com",
    "msn.com", "aol.com", "yahoo.com", "forbes.com"
]

def extract_urls_fallback(text):
    """Emergency Regex extractor if JSON parsing fails."""
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    found = url_pattern.findall(text)
    clean_links = [link for link in set(found) if "google.com" not in link and not any(bad in link for bad in LOW_QUALITY_DOMAINS)]
    return clean_links

def generate_search_plan(topic, client, model_name):
    """
    Analyzes the long topic and creates specific, targeted search queries to ensure results.
    """
    log(f"   🧠 [AI Researcher] Analyzing topic to create a search plan...")
    prompt = f"""
    TASK: You are a Search Engine Specialist.
    INPUT TOPIC: {topic}
    
    ACTION: Break this long, descriptive topic down into 3 short, effective Google Search Queries.
    
    1. A query for the latest news and reviews (e.g., "DeepSeek R1 review").
    2. A query for official documentation or the company's website (e.g., "DeepSeek official documentation").
    3. A query for finding visual demonstrations or screenshots (e.g., "DeepSeek R1 demo video UI").
    
    OUTPUT JSON format ONLY:
    {{
        "news_query": "...",
        "official_query": "...",
        "visual_query": "..."
    }}
    """
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            generation_config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        return json.loads(response.text)
    except:
        # Simple string manipulation fallback if the AI planner fails
        log("      ⚠️ Search plan generation failed. Using simple keyword extraction.")
        short_topic = " ".join(topic.split()[:4])
        return {
            "news_query": f"{short_topic} review",
            "official_query": f"{short_topic} official website",
            "visual_query": f"{short_topic} demo"
        }

def upload_external_image(source_url, filename_title):
    """
    Downloads an image, checks if it's valid, applies smart blur, and uploads to GitHub.
    """
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)} 
        
        # === تعديل: فحص الرأس (Head Check) ===
        try:
            head_req = requests.head(source_url, headers=headers, timeout=5, allow_redirects=True)
            content_type = head_req.headers.get('Content-Type', '').lower()
            if 'image' not in content_type and content_type != '':
                log(f"      ⚠️ Skipped non-image URL ({content_type}): {source_url}")
                return None
        except: pass # إذا فشل الفحص السريع، نكمل للتنزيل العادي كمحاولة أخيرة

        # التنزيل
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200: 
            log(f"      ⚠️ Failed to download external image (Status {r.status_code}): {source_url}")
            return None
        
        # 1. فتح الصورة
        try:
            original_img = Image.open(BytesIO(r.content)).convert("RGBA")
        except Exception:
            log(f"      ❌ Corrupt image data from: {source_url}")
            return None
        
        # 2. تطبيق التشويش الذكي
        base_img_rgb = original_img.convert("RGB")
        base_img_rgb = apply_smart_privacy_blur(base_img_rgb)
        
        # 3. الحفظ والرفع
        img_byte_arr = BytesIO()
        base_img_rgb.save(img_byte_arr, format='JPEG', quality=95)
        
        safe_name = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50]
        safe_name = f"{int(time.time())}_{safe_name}.jpg"

        public_url = upload_to_github_cdn(img_byte_arr, safe_name)
        
        if public_url:
            log(f"      ✅ Image Mirrored to CDN: {public_url}")
            return public_url
        else:
            return None

    except Exception as e:
        log(f"      ❌ External Image Upload Failed: {e}")
        return None
        
def smart_hunt(topic, config, mode="general"):
    model_name = "gemini-2.5-flash" 
    key = key_manager.get_current_key()
    if not key: return []
    client = genai.Client(api_key=key)
    
    search_plan = generate_search_plan(topic, client, model_name)
    active_query = search_plan.get("news_query", topic)
    if mode == "official": active_query = search_plan.get("official_query", topic)
    if mode == "visual": active_query = search_plan.get("visual_query", topic)
    
    log(f"   🕵️‍♂️ [AI Researcher] Executing ({mode}) search for: '{active_query}'")
    google_search_tool = types.Tool(google_search=types.GoogleSearch())

    # === تعديل: تعليمات صارمة لمنع الروابط الوسيطة ===
    sys_instruction = """
    You are a Research Engine. 
    MANDATORY RULE FOR LINKS:
    1. You MUST return the ORIGINAL, PUBLIC URL (e.g., 'wired.com/article', 'youtube.com/watch').
    2. You are STRICTLY FORBIDDEN from returning 'google.com/search', 'vertexaisearch', or any redirect/proxy links.
    3. If the search tool gives you a redirect link, you MUST extract the actual destination domain.
    4. Return ONLY a JSON list of objects with 'title' and 'link'.
    """

    config_gen = types.GenerateContentConfig(
        tools=[google_search_tool],
        system_instruction=sys_instruction,
        temperature=0.2,
        response_mime_type="application/json"
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=f"Find 3 high-authority sources for: '{active_query}'. Ensure links are direct and accessible.",
            config=config_gen
        )
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        from api_manager import master_json_parser
        parsed_data = master_json_parser(raw_text)
        
        results = []
        if parsed_data and isinstance(parsed_data, list):
            for item in parsed_data:
                url = item.get('link') or item.get('url')
                
                # === تعديل: فلتر كود برمجي ===
                if url:
                    # نرفض أي رابط يحتوي على هذه الكلمات
                    if any(x in url for x in ["vertexaisearch", "google.com/url", "google.com/search"]):
                        log(f"      🗑️ [Root Fix] Blocked internal Google link: {url}")
                        continue
                    results.append({"title": item.get('title', 'Source'), "link": url, "url": url})
        
        return results
    except Exception as e:
        log(f"      ❌ AI Researcher CRASHED: {e}")
        return []
