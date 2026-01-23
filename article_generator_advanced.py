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
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
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

BORING_KEYWORDS = [
    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING (UPDATED v14.1 - Fixed Layout & TOC)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* Global Settings */
    .post-body { 
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
        line-height: 1.8; 
        color: #333; 
        font-size: 18px; 
        max-width: 100%;
        overflow-x: hidden; /* Prevents horizontal scroll */
    }
    
    /* Headers */
    h2 { 
        color: #111; 
        font-weight: 800; 
        margin-top: 60px; 
        margin-bottom: 25px; 
        border-bottom: 3px solid #f1c40f; 
        padding-bottom: 10px; 
        font-size: 28px; 
        clear: both; /* Fixes overlap issue */
        display: block; /* Ensures it takes full width */
    }
    h3 { 
        color: #2980b9; 
        font-weight: 700; 
        margin-top: 40px; 
        margin-bottom: 20px;
        font-size: 24px; 
        clear: both;
    }
    
    /* Table of Contents (Fixed) */
    .toc-box { 
        background: #fdfdfd; 
        border: 1px solid #e1e4e8; 
        padding: 25px; 
        margin: 30px 0 50px 0; /* Extra bottom margin to prevent overlap */
        border-radius: 12px; 
        display: block; /* Changed from inline-block to block */
        width: 100%; /* Full width to avoid wrapping issues */
        box-sizing: border-box;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
    }
    .toc-box h3 { 
        margin-top: 0; 
        font-size: 22px; 
        border-bottom: 2px solid #3498db; 
        padding-bottom: 10px; 
        margin-bottom: 20px; 
        color: #2c3e50;
        display: inline-block;
    }
    .toc-box ul { 
        list-style: none !important; 
        padding: 0 !important; 
        margin: 0 !important; 
    }
    .toc-box li { 
        margin-bottom: 12px; 
        border-bottom: 1px dashed #eee; 
        padding-bottom: 8px; 
        padding-left: 0; /* Reset padding */
        position: relative; 
    }
    .toc-box a { 
        color: #444; 
        font-weight: 600; 
        font-size: 18px; 
        text-decoration: none; 
        transition: 0.2s; 
        display: flex; /* Aligns icon and text */
        align-items: center;
        border: none;
    }
    .toc-box a:before { 
        content: "👉"; /* Simple emoji icon */
        margin-right: 10px; 
        font-size: 16px; 
    }
    .toc-box a:hover { 
        color: #3498db; 
        padding-left: 5px; 
        background: none;
    }

    /* Takeaways Box */
    .takeaways-box { 
        background: linear-gradient(135deg, #fffcf5 0%, #fff 100%); 
        border-left: 6px solid #e67e22; 
        padding: 25px; 
        margin: 40px 0; 
        border-radius: 8px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.03); 
    }
    
    /* Tables */
    .table-wrapper { 
        overflow-x: auto; 
        margin: 40px 0; 
        border-radius: 8px; 
        border: 1px solid #eee; 
    }
    table { 
        width: 100%; 
        border-collapse: collapse; 
        background: #fff; 
        font-size: 17px; 
    }
    th { 
        background: #2c3e50; 
        color: #fff; 
        padding: 15px; 
        text-align: left; 
    }
    td { 
        padding: 15px; 
        border-bottom: 1px solid #eee; 
        color: #444; 
    }

    /* Quote/Verdict */
    blockquote { 
        background: #f8f9fa; 
        border-left: 5px solid #27ae60; 
        margin: 40px 0; 
        padding: 20px 30px; 
        font-style: italic; 
        color: #555; 
        font-size: 1.2em; 
    }

    /* Links */
    a { 
        color: #2980b9; 
        text-decoration: none; 
        font-weight: 600; 
        border-bottom: 2px dotted #2980b9; 
        transition: all 0.3s; 
    }
    a:hover { 
        color: #e67e22; 
        border-bottom: 2px solid #e67e22; 
    }
    
    /* FAQ */
    .faq-section { 
        margin-top: 60px; 
        background: #fdfdfd; 
        padding: 30px; 
        border-radius: 15px; 
        border: 1px solid #eee; 
    }
    .faq-q { color: #d35400; font-weight: bold; font-size: 20px; display: block; margin-bottom: 10px; }
    
    /* Sources */
    .Sources { font-size: 0.9em; color: #777; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .Sources ul { list-style-type: disc; padding-left: 20px; }
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
    
    log(f"   🎨 Generating Thumbnail (Flux + Local Overlay)...")

    # 1. تحسين البرومبت (Flux Realism)
    enhancers = ", photorealistic, shot on Sony A7R IV, 85mm lens, f/1.8, cinematic lighting, youtube thumbnail style, 8k, --no cartoon, --no illustration, --no 3d render"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}")
    seed = random.randint(1, 99999)
    
    # نطلب الصورة "خام" بدون نص من Pollinations
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"

    try:
        # 2. تحميل الصورة إلى الذاكرة
        r = requests.get(image_url, timeout=60)
        if r.status_code != 200: return None
        
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        # 3. معالجة النص (Overlay) محلياً باستخدام PIL
        if overlay_text:
            draw = ImageDraw.Draw(img)
            W, H = img.size
            
            # محاولة تحميل خط عريض، أو استخدام الافتراضي
            try:
                # محاولة استخدام خطوط النظام الشائعة
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path):
                    font_path = "arial.ttf"
                font = ImageFont.truetype(font_path, 80)
            except:
                font = ImageFont.load_default()

            # تجهيز النص (أحرف كبيرة)
            text = overlay_text.upper()
            
            # حساب أبعاد النص لتوسيطه
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            x = (W - text_w) / 2
            y = H - text_h - 50 # مسافة من الأسفل
            
            # رسم حدود سوداء للنص (Stroke) لزيادة الوضوح
            stroke_width = 4
            draw.text((x, y), text, font=font, fill="yellow", stroke_width=stroke_width, stroke_fill="black")

        # 4. تحويل الصورة المعدلة للرفع
        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        
        # 5. الرفع إلى ImgBB
        log("      ✅ Uploading processed thumbnail...")
        res = requests.post(
            "https://api.imgbb.com/1/upload", 
            data={"key": key, "name": f"thumb_{seed}"}, 
            files={"image": img_byte_arr}, 
            timeout=60
        )
        
        if res.status_code == 200:
            return res.json()['data']['url']
            
    except Exception as e:
        log(f"      ⚠️ Image Generation/Upload Error: {e}")
    
    return None 

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): return json.load(open('knowledge_graph.json','r'))
    except: pass
    return []

def get_recent_titles_string(category=None, limit=100):
    """
    تقرأ ملف knowledge_graph.json وتعيد قائمة بالعناوين السابقة.
    التحسين: تقوم بفلترة العناوين حسب الفئة الحالية لزيادة دقة منع التكرار.
    """
    kg = load_kg()
    if not kg: return "No previous articles found."
    
    # تصفية النتائج: نأخذ فقط المقالات التي تنتمي لنفس الفئة الحالية
    # أو نأخذ الكل إذا لم نحدد فئة
    if category:
        relevant_items = [i for i in kg if i.get('section') == category]
    else:
        relevant_items = kg

    # نأخذ آخر 'limit' عنصر (الأحدث)
    recent_items = relevant_items[-limit:]
    
    # ندمجها في نص واحد مفصول بـ " | " ليسهل على الموديل قراءته
    titles = [f"- {i.get('title','Unknown')}" for i in recent_items]
    
    if not titles:
        return "No previous articles in this category."
        
    return "\n".join(titles)
    
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

# ==============================================================================
# HELPER: IMAGE EXTRACTION & PROCESSING (Real Images)
# ==============================================================================

def extract_og_image(html_content):
    """استخراج رابط الصورة البارزة من كود HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # الأولوية 1: Open Graph
        meta = soup.find('meta', property='og:image')
        if meta and meta.get('content'): return meta['content']
        # الأولوية 2: Twitter Card
        meta = soup.find('meta', name='twitter:image')
        if meta and meta.get('content'): return meta['content']
        return None
    except:
        return None

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width):
    """رسم نص مع حدود خارجية لزيادة الوضوح"""
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def process_source_image(source_url, overlay_text, filename_title):
    """
    تحميل الصورة، تعتيمها، كتابة النص، ورفعها باسم مخصص.
    """
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None

    log(f"   🖼️ Processing Source Image: {source_url[:60]}...")
    
    try:
        # 1. تحميل الصورة (تمويه المتصفح)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200: return None
        
        original_img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        # 2. تغيير الحجم والقص (Standard Blog Size 1200x630)
        target_w, target_h = 1200, 630
        img_ratio = original_img.width / original_img.height
        target_ratio = target_w / target_h
        
        if img_ratio > target_ratio:
            new_height = target_h
            new_width = int(new_height * img_ratio)
        else:
            new_width = target_w
            new_height = int(new_width / img_ratio)
            
        original_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center Crop
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        base_img = original_img.crop((left, top, right, bottom))
        
        # 3. إضافة طبقة تعتيم (Dark Overlay)
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90)) # تعتيم بنسبة 35% تقريباً
        base_img = Image.alpha_composite(base_img, overlay)
        
        # 4. كتابة النص (Overlay Text)
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            W, H = base_img.size
            
            # محاولة تحميل خط عريض
            try:
                # مسارات خطوط لينكس الشائعة
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arialbd.ttf"
                font = ImageFont.truetype(font_path, 70)
            except:
                font = ImageFont.load_default()
            
            # التفاف النص (Word Wrap)
            words = overlay_text.upper().split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] < W - 100: current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))
            
            # رسم الأسطر في المنتصف
            text_y = H / 2 - (len(lines) * 80 / 2)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_x = (W - (bbox[2] - bbox[0])) / 2
                draw_text_with_outline(draw, (line_x, text_y), line, font, "#FFD700", "black", 4)
                text_y += 85

        # 5. تنظيف اسم الملف (SEO Friendly Filename)
        # تحويل العنوان إلى صيغة: this-is-the-title
        safe_filename = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()
        safe_filename = safe_filename[:50] # تحديد الطول

        # 6. الرفع
        img_byte_arr = BytesIO()
        base_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=92)
        img_byte_arr.seek(0)
        
        log(f"      📤 Uploading processed image as: {safe_filename}.jpg")
        res = requests.post(
            "https://api.imgbb.com/1/upload", 
            data={"key": key, "name": safe_filename}, # هنا نرسل الاسم المخصص
            files={"image": img_byte_arr}, 
            timeout=60
        )
        
        if res.status_code == 200:
            return res.json()['data']['url']
            
    except Exception as e:
        log(f"      ⚠️ Image Processing Error: {e}")
    
    return None

def run_pipeline(category, config, mode="trending"):
    """
    The Master Pipeline v14.0 (Viral B2C + Strict Integration + Robust Multimedia).
    Integrates social_manager, video_renderer, and youtube_manager flawlessly.
    """
    # 1. إعداد المتغيرات الأساسية
    model_name = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} (Viral Explainer Mode ⚡)")
    
    # تحميل قاعدة المعرفة لتجنب التكرار
    # تحميل قاعدة المعرفة لتجنب التكرار
    # نمرر الـ category لنحصل على تاريخ هذا القسم فقط
    recent_titles = get_recent_titles_string(category=category, limit=100)
    
    # طباعة للتأكد من أن النظام يرى التاريخ
    # log(f"   📚 Knowledge Graph Loaded: Found {len(recent_titles.split(' | '))} previous articles in '{category}'.")

    # =====================================================
    # STEP 0: SEO STRATEGY (THE BRAIN)
    # =====================================================
    log("   🧠 Consulting SEO Strategist for a winning keyword...")
    
    target_keyword = ""

    try:
        # طلب كلمة مفتاحية ذكية
        seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today())
        
        seo_plan = generate_step_strict(
            model_name, 
            seo_prompt, 
            "Step 0 (SEO Strategy)", 
            required_keys=["target_keyword"]
        )
        
        target_keyword = seo_plan.get('target_keyword')
        log(f"   🎯 Strategy Defined: Targeting keyword '{target_keyword}'")
        
    except Exception as e:
        log(f"   ⚠️ SEO Step failed. Using fallback.")
        target_keyword = cat_conf.get('trending_focus', category)
        if "," in target_keyword:
            target_keyword = random.choice([t.strip() for t in target_keyword.split(',')])

    # =====================================================
    # STEP 1: MULTI-SOURCE RESEARCH (THE HUNTER)
    # =====================================================
    # (Pseudo-code logic to add)
    reddit_query = f"{target_keyword} site:reddit.com"
    # قم بجلب أول نتيجة من ريديت واستخرج النص منها
    # أضف هذا النص إلى "Payload" المرسل للموديل تحت عنوان:
    # *** REAL USER OPINIONS (REDDIT) ***
    # البحث في أخبار جوجل
    rss_query = f"{target_keyword} when:3d"
    rss_items = get_real_news_rss(rss_query.replace("when:3d","").strip(), category)
    
    if not rss_items:
        log("   ⚠️ No specific news found. Retrying broad search...")
        rss_items = get_real_news_rss(category, category)
        if not rss_items:
            log("❌ FATAL: No RSS items found. Aborting.")
            return

    collected_sources = []
    main_headline = ""
    main_link = ""
    
    log(f"   🕵️‍♂️ Investigating sources for: '{target_keyword}'...")
    
    for item in rss_items[:6]:
        if item['title'][:20] in recent_titles: continue
            # --- NEW BLOCKER ---
        # إذا كان العنوان يحتوي على كلمات مملة، تجاوزه فوراً
        if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS):
            log(f"         ⛔ Skipped Boring Corporate Topic: {item['title']}")
            continue
        # -------------------
        if any(src['domain'] in item['link'] for src in collected_sources): continue

        log(f"      📌 Checking Source: {item['title'][:40]}...")
        
        # استخدام دالة url_resolver التي أرفقتها
        data = url_resolver.get_page_html(item['link'])
        
        if data and data.get('html'):
            r_url = data['url']
            html_content = data['html']
            
            # استخراج النص باستخدام Trafilatura
            text = trafilatura.extract(html_content, include_comments=False, include_tables=True)
            
            # Fallback إذا فشل Trafilatura
            if not text:
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style", "nav", "footer"]): script.extract()
                text = soup.get_text(" ", strip=True)


                # ... (داخل حلقة فحص المصادر) ...
            
            # استخراج الصورة الأصلية من الـ HTML الذي جلبناه
            og_image = extract_og_image(html_content)

            # قبول المقالات ذات الطول المناسب
            if text and len(text) >= 800:
                log(f"         ✅ Accepted Source! ({len(text)} chars). Has Image? {'Yes' if og_image else 'No'}")
                domain = urllib.parse.urlparse(r_url).netloc
                r_title = item['title']

                collected_sources.append({
                    "title": r_title,
                    "text": text,
                    "domain": domain,
                    "url": r_url,
                    "date": item['date'],
                    "source_image": og_image  # <-- نحفظ رابط الصورة هنا
                })
                
                if not main_headline:
                    # ...
                
                if not main_headline:
                    main_headline = item['title']
                    main_link = item['link']
                
                if len(collected_sources) >= 3: break
            else:
                log("         ⚠️ Content too short or extraction failed.")
        else:
             log("         ⚠️ Selenium failed to resolve URL.")
             
        time.sleep(2) # راحة لتجنب الحظر

    if not collected_sources:
        log("❌ FATAL: No valid sources found. Skipping.")
        return

    # =====================================================
    # STEP 2: DRAFTING & SYNTHESIS (THE STRICT CHAIN)
    # =====================================================
    log(f"\n✍️ Synthesizing Content from {len(collected_sources)} sources...")
    
    # تحضير النص للموديل
    combined_text = ""
    for i, src in enumerate(collected_sources):
        combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"

    # تحضير قائمة المصادر لاستخدامها لاحقاً في Step C
    sources_list_formatted = [{"title": s['title'], "url": s['url']} for s in collected_sources]

# ... داخل run_pipeline ...

    # إضافة تعليمات السياق الجديدة
    json_ctx = {
        "rss_headline": main_headline,
        "keyword_focus": target_keyword,
        "source_count": len(collected_sources),
        "date": str(datetime.date.today()),
        "style_guide": "Critical, First-Person, Beginner-Focused, Honest Review" # <-- إضافة هذا السطر
    }
    
    # ... الباقي كما هو ...
    
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** RESEARCH DATA ***\n{combined_text}"
    
    try:
        # --- Step B: Writer (B2C Style) ---
        required_b = ["headline", "hook", "article_body", "verdict"]
        
        json_b = generate_step_strict(
            model_name, 
            PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), 
            "Step B (Writer)", 
            required_keys=required_b
        )

        # --- Step C: SEO & Style ---
        kg_links = get_relevant_kg_for_linking(category)
        
        input_for_c = {
            "draft_content": json_b,
            "sources_data": sources_list_formatted 
        }
        
        required_c = ["finalTitle", "finalContent", "seo", "imageGenPrompt"]
        prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_for_c), knowledge_graph=kg_links)
        
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
        
        # استخراج النتائج النهائية
        title = final['finalTitle']
        content_html = final['finalContent']
        seo_data = final.get('seo', {})
        img_prompt = final.get('imageGenPrompt', title)
        img_overlay = final.get('imageOverlayText', 'News')

    except Exception as e:
        log(f"❌ PIPELINE CRASHED during generation: {e}")
        import traceback
        traceback.print_exc()
        return

    # =====================================================
    # STEP 3: MULTIMEDIA GENERATION (Priority: Real -> AI)
    # =====================================================
    log("   🧠 Generating Multimedia Assets...")
    
    yt_meta = {}
    fb_cap = title
    vid_html = ""
    img_url = None

    try:
        # 1. Social Metadata & Hooks
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

        # 2. Image Strategy: Try Sources First, Then AI
        overlay_text_clean = img_overlay if img_overlay else "NEWS UPDATE"
        
        log("   🖼️ Starting Image Strategy (Real Sources First)...")
        
        # الحلقة الذكية: نحاول المصدر الأول، ثم الثاني، وهكذا
        for src in collected_sources:
            raw_img_url = src.get('source_image')
            if raw_img_url:
                log(f"      🎯 Trying image from source: {src['domain']}...")
                # محاولة المعالجة
                img_url = process_source_image(raw_img_url, overlay_text_clean, title)
                
                if img_url:
                    log("      ✅ Success! Real source image processed & uploaded.")
                    break # وجدنا صورة، نخرج من الحلقة
                else:
                    log("      ⚠️ Failed to process this source image. Trying next...")
        
        # إذا انتهت الحلقة ولم نجد صورة (img_url لا يزال None)
        if not img_url:
            log("      🎨 No valid source images found/processed. Fallback to AI Generation...")
            img_url = generate_and_upload_image(img_prompt, img_overlay)

        # 3. Video Generation (كما هو بدون تغيير...)
        # ...

        # 3. Video Generation (Robust Key Search)
        summ_clean = re.sub('<[^<]+?>','', content_html)[:2500]
        
        script_json = None
        
        # حلقة المحاولة (3 محاولات)
        for attempt in range(1, 4):
            log(f"      🎬 Generating Script (Attempt {attempt}/3)...")
            try:
                raw_result = generate_step_strict(
                    model_name, 
                    PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ_clean), 
                    f"Video Script (Att {attempt})"
                )
                
                # استراتيجية الاستخراج الجديدة
                if isinstance(raw_result, dict):
                    # 1. البحث المباشر عن المفتاح الذي طلبناه
                    if 'video_script' in raw_result and isinstance(raw_result['video_script'], list):
                        script_json = raw_result['video_script']
                        log("      ✅ Found 'video_script' key directly.")
                        break
                    
                    # 2. البحث عن مفاتيح بديلة محتملة
                    for key in ['script', 'dialogue', 'conversation', 'scenes', 'content']:
                        if key in raw_result and isinstance(raw_result[key], list):
                            script_json = raw_result[key]
                            log(f"      ✅ Found script under key: '{key}'")
                            break
                    
                    # 3. إذا فشل، البحث عن أي قائمة داخل القيم
                    if not script_json:
                        for val in raw_result.values():
                            if isinstance(val, list) and len(val) > 0:
                                if isinstance(val[0], dict) and 'text' in val[0]:
                                    script_json = val
                                    log("      ✅ Found script hidden in values.")
                                    break
                
                elif isinstance(raw_result, list):
                    script_json = raw_result
                    log("      ✅ Received List directly.")
                    break
                
                if not script_json:
                     log("      ❌ Attempt failed. Retrying...")

            except Exception as e:
                log(f"      ⚠️ Script Generation Error: {e}")

        # بدء الريندر إذا وجدنا السكربت
        if script_json and len(script_json) > 0:
            timestamp = int(time.time())
            base_output_dir = os.path.abspath("output")
            os.makedirs(base_output_dir, exist_ok=True)
            
            # --- Main Video ---
            log(f"      🎬 Rendering Main Video...")
            try:
                rr = video_renderer.VideoRenderer(output_dir=base_output_dir, width=1920, height=1080)
                main_video_path = os.path.join(base_output_dir, f"main_{timestamp}.mp4")
                pm = rr.render_video(script_json, title, main_video_path)
                
                if pm and os.path.exists(pm):
                    desc = f"{yt_meta.get('description','')}\n\n🚀 Full Story: {main_link}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(
                        pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[])
                    )
                    if vid_main:
                        vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            except Exception as e:
                log(f"      ⚠️ Main Video Error: {e}")

            # --- Short Video ---
            log(f"      🎬 Rendering Short Video...")
            try:
                rs = video_renderer.VideoRenderer(output_dir=base_output_dir, width=1080, height=1920)
                short_video_path = os.path.join(base_output_dir, f"short_{timestamp}.mp4")
                ps = rs.render_video(script_json, title, short_video_path)
                
                if ps and os.path.exists(ps):
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(
                        ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts']
                    )
            except Exception as e:
                log(f"      ⚠️ Short Video Error: {e}")

        else:
            log(f"      ❌ Failed to extract script after 3 attempts.")

    except Exception as e:
        log(f"⚠️ Multimedia Process Error: {e}")
        import traceback
        traceback.print_exc()
    
    # =====================================================
    # STEP 4: PUBLISHING
    # =====================================================
    log("   🚀 Publishing to Blogger...")
    
    # --- NEW: AUTHOR BOX INJECTION ---
    # هذا الصندوق سيظهر في نهاية كل مقال
    author_box = """
    <div style="margin-top:40px; padding:25px; background:#f4f6f8; border-radius:12px; display:flex; align-items:center; border:1px solid #e1e4e8;">
        <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791" 
             style="width:70px; height:70px; border-radius:50%; margin-right:15px; border:2px solid #fff; box-shadow:0 2px 5px rgba(0,0,0,0.1);" alt="Yousef Sameer">
        <div>
            <h4 style="margin:0; font-size:18px; color:#2c3e50;">Tech Reviewer</h4>
            <p style="margin:5px 0 0; font-size:14px; color:#666; line-height:1.4;">
                I test AI tools so you don't have to break your device. 
                <br><strong>Brutally honest reviews. No fluff.</strong>
            </p>
        </div>
    </div>
    """
    
    # دمج المحتوى: المقال + صندوق الكاتب + المصادر (المصادر موجودة أصلاً في content_html من البرومبت)
    # ... (داخل run_pipeline) ...

    # =====================================================
    # 🛠️ FIX BROKEN LINKS (CRITICAL)
    # =====================================================
    log("   🔧 Sanitizing HTML links...")
    
    # 1. إزالة الهروب الخاطئ (Escaped Quotes) الذي يضعه Gemini أحياناً
    # يحول href=\"https...\" إلى href="https..."
    content_html = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
    
    # 2. إزالة علامات التنصيص المزدوجة (Double Quotes) التي تسبب خطأ 404
    # يحول href=""https..."" إلى href="https..."
    content_html = content_html.replace('href=""', 'href="').replace('"" target', '" target')
    
    # 3. تنظيف قوي باستخدام Regex لأي حالات معقدة أخرى
    # يبحث عن أي رابط يبدأ بـ http ويحاصره علامات تنصيص فوضوية
    content_html = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', content_html)
    
    # =====================================================

    # الآن ندمج المحتوى النظيف مع صندوق الكاتب
    final_content_with_author = content_html + author_box
    

    # ---------------------------------

    full_body = ARTICLE_STYLE
    
    if img_url: 
        alt_text = seo_data.get("imageAltText", title)
        full_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" alt="{alt_text}" style="max-width:100%; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" /></a></div>'
    
    if vid_html: full_body += vid_html
    
    # نستخدم المتغير الجديد
    full_body += final_content_with_author
    
    # ... (باقي كود النشر كما هو) ...
 
    
    if 'schemaMarkup' in final:
        try: full_body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass
    
    published_url = publish_post(title, full_body, [category, "Tech News", "Explainers"])
    
    # =====================================================
    # STEP 5: DISTRIBUTION & UPDATES
    # =====================================================
    if published_url:
        log(f"✅ PUBLISHED: {published_url}")
        update_kg(title, published_url, category)
        
        # 1. تحديث الوصف في يوتيوب
        new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL ARTICLE HERE:\n{published_url}\n\n#AI #TechNews"
        if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
        if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
        
        # 2. النشر على فيسبوك باستخدام social_manager
        try:
            log("   📢 Distributing to Facebook...")
            
            # الأولوية للريلز (Reels) لأنها تجلب تفاعلاً أكبر
            if fb_path and os.path.exists(fb_path): 
                fb_text = f"{fb_cap}\n\nRead more: {published_url}\n\n#AI"
                # استدعاء الدالة من social_manager
                social_manager.post_reel_to_facebook(fb_path, fb_text)
            
            # إذا لم يوجد فيديو، ننشر الصورة والمقال
            elif img_url:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{published_url}", published_url, img_url)
                
        except Exception as e:
            log(f"   ⚠️ Social Distribution Error: {e}")
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
