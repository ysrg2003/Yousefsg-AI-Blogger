import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import base64
import feedparser
from bs4 import BeautifulSoup
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types
import selenium
import webdriver_manager
# ---- أضف هذه الاستيرادات بالقرب من أعلى الملف ----
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# webdriver-manager سيسمح بتنزيل ChromeDriver تلقائياً
from webdriver_manager.chrome import ChromeDriverManager
# (قد تحتاج أيضاً هذه لو كنت تستخدم find_element وغيرها)
from selenium.webdriver.common.by import By
# -------------------------------------------------
import url_resolver
import trafilatura
import ast
import json_repair # يجب تثبيتها: pip install json_repair
import regex # يجب تثبيتها: pip install regex
import pydantic
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type, 
    before_sleep_log
)
from prompts import *

# ==============================================================================
# 0. CONFIG & LOGGING
# ==============================================================================

FORBIDDEN_PHRASES = [
    "In today's digital age",
    "The world of AI is ever-evolving",
    "unveils",
    "unveiled",
    "poised to",
    "delve into",
    "game-changer",
    "paradigm shift",
    "tapestry",
    "robust",
    "leverage",
    "underscore",
    "testament to",
    "beacon of",
    "In conclusion",
    "Remember that",
    "It is important to note",
    "Imagine a world",
    "fast-paced world",
    "cutting-edge",
    "realm of"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING
# ==============================================================================
ARTICLE_STYLE = """
<style>
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    h2 { color: #111; font-weight: 800; margin-top: 55px; margin-bottom: 25px; border-bottom: 4px solid #f1c40f; padding-bottom: 8px; display: inline-block; font-size: 28px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 40px; font-size: 24px; }
    .toc-box { background: #ffffff; border: 1px solid #e1e4e8; padding: 30px; margin: 40px 0; border-radius: 12px; display: inline-block; min-width: 60%; box-shadow: 0 8px 16px rgba(0,0,0,0.05); }
    .toc-box h3 { margin-top: 0; font-size: 22px; border-bottom: 2px solid #3498db; padding-bottom: 8px; display: inline-block; margin-bottom: 15px; color: #222; }
    .toc-box ul { list-style: none; padding: 0; margin: 0; }
    .toc-box li { margin-bottom: 12px; border-bottom: 1px dashed #f0f0f0; padding-bottom: 8px; padding-left: 20px; position: relative; }
    .toc-box li:before { content: "►"; color: #3498db; position: absolute; left: 0; font-size: 14px; top: 4px; }
    .toc-box a { color: #444; font-weight: 600; font-size: 18px; text-decoration: none; transition: 0.2s; }
    .toc-box a:hover { color: #3498db; padding-left: 8px; }
    .table-wrapper { overflow-x: auto; margin: 45px 0; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.08); border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; font-size: 18px; }
    th { background: #2c3e50; color: #fff; padding: 18px; text-align: left; text-transform: uppercase; font-size: 16px; letter-spacing: 1px; }
    td { padding: 16px 18px; border-bottom: 1px solid #eee; color: #34495e; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    tr:hover { background-color: #e9ecef; transition: 0.3s; }
    .takeaways-box { background: linear-gradient(135deg, #fdfbf7 0%, #fff 100%); border-left: 6px solid #e67e22; padding: 30px; margin: 40px 0; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    .takeaways-box h3 { margin-top: 0; color: #d35400; font-size: 22px; margin-bottom: 20px; display: flex; align-items: center; }
    .takeaways-box ul { margin: 0; padding-left: 25px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 600; font-size: 18px; color: #222; }
    .faq-section { margin-top: 70px; border-top: 3px solid #f1f1f1; padding-top: 50px; background: #fffcf5; padding: 40px; border-radius: 20px; }
    .faq-title { font-size: 30px; font-weight: 900; color: #222; margin-bottom: 35px; text-align: center; }
    .faq-q { font-weight: 700; font-size: 20px; color: #d35400; margin-bottom: 10px; display: block; }
    .faq-a { font-size: 19px; color: #555; line-height: 1.8; }
    .separator img { border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.12); max-width: 100%; height: auto; display: block; }
    blockquote { background: #ffffff; border-left: 5px solid #f1c40f; margin: 40px 0; padding: 25px 35px; font-style: italic; color: #555; font-size: 1.3em; line-height: 1.6; box-shadow: 0 3px 10px rgba(0,0,0,0.05); }
    a { color: #2980b9; text-decoration: none; font-weight: 600; border-bottom: 2px dotted #2980b9; transition: all 0.3s; }
    a:hover { color: #e67e22; border-bottom: 2px solid #e67e22; background-color: #fff8e1; }
</style>
"""

# ==============================================================================
# 2. PROMPTS (PASTE HERE)
# ==============================================================================

# 🛑 تاكد من كتابة from prompts import *"Beast Mode" هنا 🛑
# (تأكد من أن PROMPT_B يطلب استخدام Source Text)

# ==============================================================================
# 3. HELPER UTILITIES
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"🔄 Switching Key #{self.current_index + 1}...")
            return True
        log("❌ ALL KEYS EXHAUSTED.")  
        return False

key_manager = KeyManager()


# ==============================================================================
# UPDATED JSON UTILITIES (AUTO-REPAIR MODE)
# ==============================================================================


# ==============================================================================
# 5. ADVANCED AI ENGINE: THE "UNBREAKABLE" PIPELINE
# ==============================================================================
import logging
import json
import json_repair  # pip install json_repair
import regex        # pip install regex
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from google import genai
from google.genai import types

# إعداد اللوجر الخاص بمكتبة Tenacity لمراقبة المحاولات في الخلفية
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

# ==============================================================================
# A. CUSTOM EXCEPTIONS & STRICT INSTRUCTIONS
# ==============================================================================

class JSONValidationError(Exception):
    """يُثار هذا الخطأ عندما يكون الـ JSON صالحاً نحوياً ولكن تنقصه مفاتيح أساسية."""
    pass

class JSONParsingError(Exception):
    """يُثار هذا الخطأ عندما يفشل تحليل النص إلى JSON تماماً حتى بعد محاولات الإصلاح."""
    pass

# البرومبت الصارم الذي يجبر الموديل على الصمت والالتزام بالتنسيق فقط
STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested. 
No explanations, no headings, no extra text, no apologies. 
Output exactly and only what the user asked for. 
If the user requests JSON, return PURE JSON. 
Obey safety policy.
"""

# ==============================================================================
# B. HELPER PARSERS & VALIDATORS
# ==============================================================================

def master_json_parser(text):
    """
    محرك تحليل JSON شامل يستخدم Regex و json_repair لاستخراج البيانات من أي نص فوضوي.
    """
    if not text: return None
    
    # 1. Regex Extraction: استخراج ما بين الأقواس المعقوفة {}
    # هذا يزيل أي نصوص قبل أو بعد الـ JSON
    match = regex.search(r'\{(?:[^{}]|(?R))*\}', text, regex.DOTALL)
    candidate = match.group(0) if match else text
    
    # 2. json_repair: المحاولة الأولى والأقوى للإصلاح
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        # التأكد من أن النتيجة هي قاموس أو قائمة وليست نصاً
        if isinstance(decoded, (dict, list)):
            return decoded
    except Exception:
        pass

    # 3. Fallback: محاولة تنظيف بسيطة واستخدام json القياسي
    try:
        clean = candidate.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None

def validate_structure(data, required_keys):
    """
    التحقق من صحة هيكل البيانات (Validation).
    يرفع استثناء إذا كانت البيانات ناقصة ليجبر Tenacity على إعادة المحاولة.
    """
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary output, but got type: {type(data)}")
    
    missing_keys = [key for key in required_keys if key not in data]
    
    if missing_keys:
        # هذا الخطأ سيتم التقاطه بواسطة Tenacity لإعادة المحاولة
        raise JSONValidationError(f"JSON is valid but missing required keys: {missing_keys}")
    
    return True

# ==============================================================================
# C. THE MAIN STRICT GENERATION FUNCTION
# ==============================================================================

@retry(
    # التوقف بعد 5 محاولات فاشلة
    stop=stop_after_attempt(5),
    
    # الانتظار الأسي: يبدأ بـ 4 ثواني، ثم يتضاعف حتى يصل لأقصى حد 15 ثانية
    wait=wait_exponential(multiplier=1, min=4, max=15),
    
    # إعادة المحاولة فقط في حالة هذه الأخطاء المحددة
    retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)),
    
    # تسجيل رسالة في اللوج قبل الانتظار للمحاولة التالية
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(model_name, prompt, step_name, required_keys=[]):
    """
    الدالة النهائية لتوليد المحتوى.
    - تستخدم System Instructions لضمان النتيجة.
    - تستخدم Tenacity لإعادة المحاولة عند الفشل.
    - تستخدم AI Repair لإصلاح الأخطاء النحوية ذاتياً.
    - تدير تبديل المفاتيح (Key Rotation) عند انتهاء الكوتا.
    """
    log(f"   🔄 [Tenacity] Executing: {step_name}...")
    
    # 1. جلب مفتاح API الحالي
    key = key_manager.get_current_key()
    if not key:
        # إذا نفدت المفاتيح، نرفع خطأ قاتلاً لا يمكن إعادة المحاولة معه
        raise RuntimeError("FATAL: All API Keys exhausted.")
    
    client = genai.Client(api_key=key)
    
    try:
        # 2. إعداد الكونفيج الصارم
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json",  # إجبار الموديل على JSON
            system_instruction=STRICT_SYSTEM_PROMPT,  # التعليمات الصارمة
            temperature=0.3,  # تقليل العشوائية للدقة
            top_p=0.8
        )

        # 3. الطلب الأساسي من الموديل
        response = client.models.generate_content(
            model=model_name, 
            contents=prompt, 
            config=generation_config
        )
        
        raw_text = response.text
        
        # 4. محاولة التحليل الأولى
        parsed_data = master_json_parser(raw_text)
        
        # 5. منطق الإصلاح الذاتي (AI Self-Correction)
        # إذا فشل التحليل، نطلب من الذكاء الاصطناعي إصلاح ما أفسده
        if not parsed_data:
            log(f"      ⚠️ Parsing failed locally for {step_name}. Triggering AI Repair...")
            
            repair_prompt = f"""
            SYSTEM ALERT: You generated INVALID JSON in the previous step.
            Your output could not be parsed.
            
            TASK: Fix the syntax errors in the content below.
            RULES:
            1. Return ONLY the valid JSON object.
            2. Do NOT add markdown blocks.
            3. Fix unescaped quotes and trailing commas.
            
            BROKEN CONTENT:
            {raw_text[:10000]}
            """
            
            # نستخدم موديل سريع (Flash) لعملية الإصلاح لتوفير الوقت
            repair_response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=repair_prompt,
                config=generation_config # نستخدم نفس الكونفيج الصارم
            )
            
            # محاولة تحليل النص المصلح
            parsed_data = master_json_parser(repair_response.text)
            
            # إذا استمر الفشل، نرفع خطأ Parsing ليقوم Tenacity بإعادة المحاولة من الصفر
            if not parsed_data:
                raise JSONParsingError(f"Failed to parse JSON even after AI repair for step: {step_name}")
            else:
                log(f"      ✅ AI Repair Successful for {step_name}!")

        # 6. التحقق من صحة الهيكل (Validation)
        # هل المفاتيح المطلوبة موجودة؟
        if required_keys:
            validate_structure(parsed_data, required_keys)
            
        # إذا وصلنا هنا، فالبيانات سليمة 100%
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        # التعامل مع أخطاء الكوتا (429) بشكل خاص
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "resource exhausted" in error_msg:
            log("      ⚠️ Quota Exceeded (429). Switching Key & Retrying immediately...")
            if key_manager.switch_key():
                # نرفع الخطأ مرة أخرى ليقوم Tenacity بالتقاطه وإعادة المحاولة بالمفتاح الجديد
                raise e 
            else:
                raise RuntimeError("FATAL: All keys exhausted during retry.")
        
        # تسجيل الخطأ ورفعه لإعادة المحاولة
        log(f"      ❌ Attempt Failed for {step_name}: {str(e)[:200]}")
        raise e
            

def fetch_full_article(url):
    """
    🚀 SCRAPER v11: 100% Local (Selenium + Trafilatura).
    No 3rd party APIs like Jina. High success rate.
    """
    # 1. جلب الـ HTML والرابط الحقيقي باستخدام Selenium
    data = url_resolver.get_page_html(url)
    
    if not data or not data.get('html'):
        log(f"      ⚠️ Selenium failed to get page source.")
        return None
        
    real_url = data['url']
    html_content = data['html']
    
    log(f"      🧩 Extracting content locally from: {real_url[:50]}...")
    
    try:
        # 2. استخدام Trafilatura لاستخراج نص المقالة من الـ HTML
        # include_comments=False: لإزالة التعليقات
        # include_tables=True: للاحتفاظ بالجداول المهمة
        extracted_text = trafilatura.extract(
            html_content, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True # التركيز على دقة النص وليس كثرته
        )
        
        if extracted_text and len(extracted_text) > 500:
            log(f"      ✅ Extraction Success! {len(extracted_text)} chars found.")
            return extracted_text[:12000]
        else:
            log("      ⚠️ Trafilatura found very little text. Trying fallback...")
            
            # Fallback: محاولة بسيطة في حال فشل المكتبة المتخصصة
            soup = BeautifulSoup(html_content, 'html.parser')
            # حذف العناصر المزعجة يدوياً
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.extract()
            text = soup.get_text(separator='\n')
            
            # تنظيف الفراغات
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = '\n'.join(lines)
            
            if len(clean_text) > 500:
                log(f"      ✅ Fallback Success (BS4): {len(clean_text)} chars.")
                return clean_text[:12000]

    except Exception as e:
        log(f"      ❌ Extraction Error: {e}")
        
    return None


def get_real_news_rss(query_keywords, category):
    try:
        if "," in query_keywords:
            topics = [t.strip() for t in query_keywords.split(',') if t.strip()]
            focused = random.choice(topics)
            log(f"   🎯 Targeted Search: '{focused}'")
            full_query = f"{focused} when:1d"
        else:
            full_query = f"{query_keywords} when:1d"

        encoded = urllib.parse.quote(full_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        if feed.entries:
            for entry in feed.entries[:8]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        else:
            log(f"   ⚠️ RSS Empty. Fallback.")
            fb = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fb)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({"title": entry.title, "link": entry.link, "date": "Today"})
            return items
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []

def get_blogger_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    try:
        r = requests.post('https://oauth2.googleapis.com/token', data=payload)
        return r.json().get('access_token') if r.status_code == 200 else None
    except: return None

def publish_post(title, content, labels):
    token = get_blogger_token()
    if not token: return None
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts?isDraft=false"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels}
    
    try:
        r = requests.post(url, headers=headers, json=body)
        if r.status_code == 200:
            link = r.json().get('url')
            log(f"✅ Published LIVE: {link}")
            return link
        log(f"❌ Blogger Error: {r.text}")
        return None
    except Exception as e:
        log(f"❌ Connection Fail: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    log(f"   🎨 Flux Image Gen...")
    for i in range(3):
        try:
            safe = urllib.parse.quote(f"{prompt_text}, abstract tech, 8k, --no text")
            txt = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white" if overlay_text else ""
            url = f"https://image.pollinations.ai/prompt/{safe}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,999)}{txt}"
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if res.status_code == 200: return res.json()['data']['url']
        except: time.sleep(3)
    return None

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): return json.load(open('knowledge_graph.json','r'))
    except: pass
    return []

def get_recent_titles_string(limit=50):
    kg = load_kg()
    if not kg: return "None"
    return ", ".join([i.get('title','') for i in kg[-limit:]])

def get_relevant_kg_for_linking(category, limit=60):
    kg = load_kg()
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==category][:limit]
    return json.dumps(links)

def update_kg(title, url, section):
    try:
        data = load_kg()
        for i in data:
            if i['url']==url: return
        data.append({"title":title, "url":url, "section":section, "date":str(datetime.date.today())})
        with open('knowledge_graph.json','w') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: d=json.load(f)
            if len(d)>800: json.dump(d[-400:], open('knowledge_graph.json','w'), indent=2)
    except: pass

def generate_step(model, prompt, step):
    log(f"   👉 Generating: {step}")
    while True:
        key = key_manager.get_current_key()
        if not key: 
            log("❌ FATAL: Keys exhausted.")
            return None
        client = genai.Client(api_key=key)
        try:
            r = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return clean_json(r.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                if not key_manager.switch_key(): return None
            else: return None
# ==============================================================================
# 4. ADVANCED SCRAPING (UPDATED FOR HIGH QUALITY & LOGGING)
# ==============================================================================
def resolve_and_scrape(google_url):
    """
    Open Google URL -> Resolve -> Get Page Source -> Extract Text.
    Returns: (final_url, page_title, text_content)
    """
    log(f"      🕵️‍♂️ Selenium: Opening & Resolving: {google_url[:60]}...")
    
    # خيارات المتصفح
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # انتحال شخصية متصفح حقيقي لتجنب الحظر
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument("--mute-audio") # كتم الصوت لتسريع التحميل

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25) # مهلة تحميل 25 ثانية
        
        driver.get(google_url)
        
        # حلقة انتظار للخروج من جوجل
        start_wait = time.time()
        final_url = google_url
        
        while time.time() - start_wait < 15: # انتظار 15 ثانية كحد أقصى للتحويل
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1) # فحص كل ثانية
        
        # التقاط العنوان الحقيقي للصفحة
        final_title = driver.title
        page_source = driver.page_source
        
        # التحقق من الروابط غير المرغوبة (فيديو، معارض صور)
        # هذا يمنع مشكلة "Washington Post Video" التي واجهتها
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None

        log(f"      🔗 Resolved URL: {final_url[:70]}...")
        log(f"      🏷️ Real Page Title: {final_title[:70]}...")

        # استخراج النص باستخدام Trafilatura
        extracted_text = trafilatura.extract(
            page_source, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True
        )
        
        if extracted_text and len(extracted_text) > 1000:
            return final_url, final_title, extracted_text

        # Fallback (BS4) إذا فشل Trafilatura
        soup = BeautifulSoup(page_source, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        
        return final_url, final_title, fallback_text

    except Exception as e:
        log(f"      ❌ Selenium Error: {e}")
        return None, None, None
    finally:
        if driver:
            driver.quit()

def run_pipeline(category, config, mode="trending"):
    """
    The Master Pipeline v12.0 (Unbreakable & Strict Mode).
    Uses Tenacity for retries and strictly adheres to validation rules.
    """
    # 1. إعداد المتغيرات الأساسية
    model_name = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} (Strict Analyst Mode 🧠)")
    
    # تحميل قاعدة المعرفة لتجنب التكرار
    recent_titles = get_recent_titles_string(limit=60)

    # =====================================================
    # STEP 0: SEO STRATEGY (THE BRAIN)
    # =====================================================
    log("   🧠 Consulting SEO Strategist for a winning keyword...")
    
    target_keyword = ""
    seo_reasoning = ""

    try:
        # طلب كلمة مفتاحية ذكية من الذكاء الاصطناعي
        seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today())
        
        # نستخدم الدالة الصارمة، إذا فشلت 5 مرات سترفع خطأ
        seo_plan = generate_step_strict(
            model_name, 
            seo_prompt, 
            "Step 0 (SEO Strategy)", 
            required_keys=["target_keyword"]
        )
        
        target_keyword = seo_plan.get('target_keyword')
        seo_reasoning = seo_plan.get('reasoning', 'N/A')
        log(f"   🎯 Strategy Defined: Targeting keyword '{target_keyword}'")
        
    except Exception as e:
        # هذه الخطوة الوحيدة التي نسمح فيها بالـ Fallback اليدوي لأننا نستطيع العمل بدونه
        log(f"   ⚠️ SEO Step failed after retries: {e}. Using config fallback.")
        target_keyword = cat_conf.get('trending_focus', category)
        if "," in target_keyword:
            target_keyword = random.choice([t.strip() for t in target_keyword.split(',')])

    # =====================================================
    # STEP 1: MULTI-SOURCE RESEARCH (THE HUNTER)
    # =====================================================
    # البحث في أخبار جوجل
    rss_query = f"{target_keyword} when:3d"
    rss_items = get_real_news_rss(rss_query.replace("when:3d","").strip(), category)
    
    # محاولة ثانية بنطاق أوسع إذا لم نجد نتائج
    if not rss_items:
        log("   ⚠️ No specific news found. Retrying with broad category search...")
        rss_items = get_real_news_rss(category, category)
        if not rss_items:
            log("❌ FATAL: No RSS items found even after fallback. Aborting.")
            return

    collected_sources = []
    main_headline = ""
    main_link = ""
    
    log(f"   🕵️‍♂️ Investigating multiple sources for: '{target_keyword}'...")
    
    # حلقة الفحص وجمع المصادر
    for item in rss_items[:6]:
        # 1. فلترة التكرار
        if item['title'][:20] in recent_titles: 
            log(f"      ⏭️ Skipped duplicate title: {item['title'][:30]}...")
            continue
        
        # 2. فلترة النطاق المكرر
        if any(src['domain'] in item['link'] for src in collected_sources): 
            continue

        log(f"      📌 Checking Source: {item['title'][:40]}...")
        
        # محاولة فك الرابط وجلب المحتوى
        r_url, r_title, text = resolve_and_scrape(item['link'])
        
        # 3. فلترة الجودة (الطول)
        if text and len(text) >= 800:
            log(f"         ✅ Accepted Source! ({len(text)} chars).")
            
            domain = urllib.parse.urlparse(r_url).netloc
            collected_sources.append({
                "title": r_title,
                "text": text,
                "domain": domain,
                "url": r_url,
                "date": item['date']
            })
            
            # تحديد البيانات الرئيسية من المصدر الأول
            if not main_headline:
                main_headline = item['title']
                main_link = item['link']
            
            # الاكتفاء بـ 3 مصادر
            if len(collected_sources) >= 3: 
                log("      ✨ Collected sufficient data (3 robust sources).")
                break
        else:
            log(f"         ⚠️ Rejected (Weak/Short Content).")
            time.sleep(1)

    if not collected_sources:
        log("❌ FATAL: No valid high-quality sources found. Skipping.")
        return

    # =====================================================
    # STEP 2: DRAFTING & SYNTHESIS (STRICT CHAIN)
    # =====================================================
    log(f"\n✍️ Synthesizing Content from {len(collected_sources)} sources...")
    
    # تحضير النص المجمع
    combined_text = ""
    for i, src in enumerate(collected_sources):
        combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"

    json_ctx = {
        "rss_headline": main_headline,
        "keyword_focus": target_keyword,
        "source_count": len(collected_sources),
        "date": str(datetime.date.today())
    }
    
    prefix = "*** MULTI-SOURCE RESEARCH DATA (SYNTHESIZE THIS) ***"
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n{prefix}\n{combined_text}"
    
    # هنا نبدأ السلسلة الصارمة (Strict Chain)
    # أي فشل هنا سيؤدي لإيقاف البايبلاين بدلاً من نشر محتوى سيء
    try:
        # --- Step B: Writer ---
        # نطلب مفاتيح محددة جداً لضمان الهيكل
        required_b = ["headline", "hook", "article_body", "verdict"]
        json_b = generate_step_strict(
            model_name, 
            PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), 
            "Step B (Writer)", 
            required_keys=required_b
        )

        # --- Step C: SEO & Style ---
        kg_links = get_relevant_kg_for_linking(category)
        required_c = ["finalTitle", "finalContent", "seo", "imageGenPrompt"]
        prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
        
        json_c = generate_step_strict(
            model_name, 
            prompt_c, 
            "Step C (SEO & Style)", 
            required_keys=required_c
        )

        # --- Step D: Humanizer ---
        required_d = ["finalTitle", "finalContent"]
        prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
        
        json_d = generate_step_strict(
            model_name, 
            prompt_d, 
            "Step D (Humanizer)", 
            required_keys=required_d
        )

        # --- Step E: Final Polish ---
        required_e = ["finalTitle", "finalContent", "imageGenPrompt", "seo"]
        prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
        
        final = generate_step_strict(
            model_name, 
            prompt_e, 
            "Step E (Final Polish)", 
            required_keys=required_e
        )
        
        # استخراج النتائج النهائية الموثوقة
        title = final['finalTitle']
        content_html = final['finalContent']
        seo_data = final.get('seo', {})
        img_prompt = final.get('imageGenPrompt', title)
        img_overlay = final.get('imageOverlayText', 'News')

    except Exception as e:
        # هذا البلوك يلتقط أي فشل نهائي بعد استنفاد محاولات Tenacity
        log(f"❌ PIPELINE CRASHED during generation phase: {e}")
        log("❌ Aborting to prevent publishing bad content.")
        return

    # =====================================================
    # STEP 3: MULTIMEDIA GENERATION
    # =====================================================
    log("   🧠 Generating Multimedia Assets...")
    
    yt_meta = {}
    fb_cap = title
    vid_html = ""
    vid_main = None
    vid_short = None
    fb_path = None
    img_url = None

    try:
        # 1. Social Metadata
        yt_meta = generate_step_strict(
            model_name, 
            PROMPT_YOUTUBE_METADATA.format(draft_title=title), 
            "YT Meta",
            required_keys=["title", "description", "tags"]
        )
        
        fb_dat = generate_step_strict(
            model_name, 
            PROMPT_FACEBOOK_HOOK.format(title=title), 
            "FB Hook",
            required_keys=["FB_Hook"]
        )
        fb_cap = fb_dat.get('FB_Hook', title)

        # 2. Image Generation
        img_url = generate_and_upload_image(img_prompt, img_overlay)

        # 3. Video Generation
        # استخراج ملخص للنص لعمل السكربت
        summ = re.sub('<[^<]+?>','', content_html)[:2500]
        
        # توليد السكربت بصيغة صارمة
        script_json = generate_step_strict(
            model_name, 
            PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), 
            "Video Script"
        )
        
        # التحقق من أن السكربت قائمة (List) كما هو مطلوب
        if isinstance(script_json, list) and len(script_json) > 0:
            timestamp = int(time.time())
            rr = video_renderer.VideoRenderer()
            base_output_dir = os.path.abspath("output")
            os.makedirs(base_output_dir, exist_ok=True)
            
            # --- Main Video (Landscape) ---
            main_video_path = os.path.join(base_output_dir, f"main_{timestamp}.mp4")
            log(f"      🎬 Rendering Main Video...")
            pm = rr.render_video(script_json, title, main_video_path)
            
            if pm and os.path.exists(pm):
                desc = f"{yt_meta.get('description','')}\n\n🚀 Full Article Link Coming Soon.\n\n#{category.replace(' ','')} #AI"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                
                if vid_main:
                    vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'

            # --- Short Video (Portrait) ---
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            short_video_path = os.path.join(base_output_dir, f"short_{timestamp}.mp4")
            log(f"      🎬 Rendering Short Video...")
            ps = rs.render_video(script_json, title, short_video_path)
            
            if ps and os.path.exists(ps):
                fb_path = ps
                vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])

    except Exception as e:
        log(f"⚠️ Multimedia Error: {e}")
        import traceback
        traceback.print_exc()

    # =====================================================
    # STEP 4: PUBLISHING
    # =====================================================
    log("   🚀 Publishing to Blogger...")
    
    # تجميع المقال النهائي
    full_body = ARTICLE_STYLE
    
    # الصورة
    if img_url: 
        alt_text = seo_data.get("imageAltText", title)
        full_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" alt="{alt_text}" /></a></div>'
    
    # الفيديو
    if vid_html: full_body += vid_html
    
    # المحتوى
    full_body += content_html
    
    # Schema Markup
    if 'schemaMarkup' in final:
        try: 
            full_body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass
    
    # النشر
    published_url = publish_post(title, full_body, [category, "Tech News", "AI"])
    
    # =====================================================
    # STEP 5: DISTRIBUTION & UPDATES
    # =====================================================
    if published_url:
        log(f"✅ PUBLISHED SUCCESSFULLY: {published_url}")
        
        # 1. تحديث قاعدة المعرفة
        update_kg(title, published_url, category)
        
        # 2. تحديث وصف اليوتيوب بالرابط
        new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL STORY HERE:\n{published_url}\n\n#AI #Technology"
        if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
        if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
        
        # 3. النشر على فيسبوك
        try:
            log("   📢 Distributing to Facebook...")
            if fb_path and os.path.exists(fb_path): 
                fb_text = f"{fb_cap}\n\nRead more: {published_url}\n\n#AI"
                social_manager.post_reel_to_facebook(fb_path, fb_text)
            elif img_url:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{published_url}", published_url, img_url)
        except Exception as e:
            log(f"   ⚠️ Social Dist Error: {e}")
    else:
        log("❌ Blogger Publish Failed.")

# ==============================================================================
# 7. MAIN
# ==============================================================================

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ No Config.")
        return
    
    cat = random.choice(list(cfg['categories'].keys()))
    run_pipeline(cat, cfg, mode="trending")
    perform_maintenance_cleanup()
    log("✅ Finished.")

if __name__ == "__main__":
    main()
