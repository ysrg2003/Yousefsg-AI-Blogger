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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import url_resolver
import trafilatura
import ast
import json_repair 
import regex 
import pydantic
import difflib
import logging
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type, 
    before_sleep_log
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from github import Github, InputGitTreeElement
import cv2
import numpy as np
import content_validator_pro
import reddit_manager
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

# NOTE: BORING_KEYWORDS removed to allow important corporate news through.

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING
# ==============================================================================
ARTICLE_STYLE = ""

# ==============================================================================
# 3. HELPER UTILITIES (ULTR-SAFE MODE & SMART RECOVERY)
# ==============================================================================

# --- CONFIGURATION FOR SAFETY ---
PRE_REQUEST_COOLING = 20  # ثواني انتظار إجبارية قبل أي طلب
KEY_SWITCH_COOLING = 10   # ثواني انتظار عند تبديل المفتاح
SYSTEM_RESET_COOLING = 60 # ثواني قيلولة النظام عند فشل كل شيء

logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

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
        """ينتقل للمفتاح التالي. يعيد True إذا نجح، و False إذا انتهت القائمة."""
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Key #{self.current_index + 1}...")
            return True
        return False

    def reset_keys(self):
        """يعيد المؤشر للمفتاح الأول لبدء دورة جديدة"""
        log("   ♻️ Resetting Key Index to 0 (Fresh Start)...")
        self.current_index = 0

key_manager = KeyManager()
TRIED_MODELS = set()
CACHED_JUDGE_MODEL = None

def master_json_parser(text):
    if not text: return None
    match = regex.search(r'\{(?:[^{}]|(?R))*\}', text, regex.DOTALL)
    candidate = match.group(0) if match else text
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass
    try:
        clean = candidate.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except: return None

def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise JSONValidationError(f"Missing keys: {missing_keys}")
    return True

def discover_next_best_model(current_failed_model):
    """يكتشف موديل جديد لم يتم استخدامه من قبل"""
    log("   🕵️‍♂️ Discovery Mode: Searching for a fresh AI model...")
    TRIED_MODELS.add(current_failed_model)
    
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    try:
        all_models = list(client.models.list())
        candidates = []
        for m in all_models:
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace('models/', '')
                if name not in TRIED_MODELS:
                    candidates.append(name)
        
        # الترتيب حسب الأحدث والأسرع
        priority = ['2.0', 'flash', 'pro', '1.5', 'latest']
        candidates.sort(key=lambda x: sum(2 for k in priority if k in x), reverse=True)
        
        if candidates:
            new_model = candidates[0]
            log(f"   💡 Found Fresh Model: {new_model}")
            return f"models/{new_model}" if "models/" not in new_model else new_model
            
    except Exception as e:
        log(f"   ⚠️ Discovery Error: {e}")
    
    # قائمة احتياطية يدوية
    backups = [
        "models/gemini-2.0-flash", 
        "models/gemini-2.0-flash-exp",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash-8b"
    ]
    for b in backups:
        if b not in TRIED_MODELS:
            log(f"   💡 Using Backup Model: {b}")
            return b
            
    return None

def get_oldest_judge_model():
    """يبحث عن أقدم موديل متاح للفحص الدلالي لتوفير الكوتا."""
    global CACHED_JUDGE_MODEL
    if CACHED_JUDGE_MODEL: return CACHED_JUDGE_MODEL

    log("   👴 Looking for the 'Oldest' Model for validation...")
    preferences = [
        "models/gemini-1.0-pro", "models/gemini-1.0-pro-latest",
        "models/gemini-1.0-pro-001", "models/gemini-pro", "models/gemini-1.5-flash"
    ]
    
    key = key_manager.get_current_key()
    if not key: return "models/gemini-1.5-flash"
    
    client = genai.Client(api_key=key)
    try:
        available = [m.name for m in client.models.list()]
        for pref in preferences:
            for avail in available:
                if pref.split('/')[-1] in avail:
                    log(f"   ⚖️ Selected Judge Model: {avail}")
                    CACHED_JUDGE_MODEL = avail
                    return avail
    except: pass
    return "models/gemini-1.5-flash"

# --- THE ULTRA-SAFE GENERATOR ---
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    current_model = initial_model_name
    
    while True:
        log(f"   🚀 [SafeEngine] Step: {step_name} | Model: {current_model}")
        
        while True:
            key = key_manager.get_current_key()
            if not key: raise RuntimeError("FATAL: No API keys loaded.")

            # PRE-EMPTIVE COOLING
            log(f"      ☕ Cooling down for {PRE_REQUEST_COOLING}s to prevent 429...")
            time.sleep(PRE_REQUEST_COOLING)

            client = genai.Client(api_key=key)
            try:
                generation_config = types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    system_instruction=STRICT_SYSTEM_PROMPT, 
                    temperature=0.3
                )
                
                response = client.models.generate_content(
                    model=current_model, 
                    contents=prompt, 
                    config=generation_config
                )
                
                parsed_data = master_json_parser(response.text)
                if not parsed_data:
                    log("      ⚠️ JSON Repair needed...")
                    time.sleep(5)
                    repair_resp = client.models.generate_content(
                        model=current_model, 
                        contents=f"Fix invalid JSON:\n{response.text[:5000]}", 
                        config=generation_config
                    )
                    parsed_data = master_json_parser(repair_resp.text)

                if not parsed_data: raise JSONParsingError("Failed to parse JSON")
                if required_keys: validate_structure(parsed_data, required_keys)
                
                log(f"      ✅ Success: {step_name} completed.")
                return parsed_data

            except Exception as e:
                error_msg = str(e).lower()
                
                if "429" in error_msg or "quota" in error_msg or "resource exhausted" in error_msg or "overloaded" in error_msg:
                    log(f"      ⚠️ High Traffic/Quota Error on Key #{key_manager.current_index + 1}.")
                    if not key_manager.switch_key():
                        log(f"      ⛔ All keys exhausted for {current_model}.")
                        break 
                    log(f"      ⏳ Key switched. Waiting {KEY_SWITCH_COOLING}s...")
                    time.sleep(KEY_SWITCH_COOLING)
                    continue 
                
                elif "not found" in error_msg or "404" in error_msg:
                     log(f"      ❌ Model {current_model} not available/found.")
                     break 
                
                else:
                    log(f"      ❌ General Error: {str(e)[:100]}. Waiting 10s and retrying...")
                    time.sleep(10)
                    continue

        log(f"      🔄 Initiating SYSTEM RESET & Model Switch...")
        log(f"      💤 System Sleeping for {SYSTEM_RESET_COOLING}s...")
        time.sleep(SYSTEM_RESET_COOLING)
        
        next_model = discover_next_best_model(current_model)
        
        if next_model:
            log(f"      ✅ Recovery: Switching to {next_model}")
            current_model = next_model
            key_manager.reset_keys()
        else:
            log("      ❌ FATAL: No more models available to try.")
            raise RuntimeError("Mission Failed: All models and keys exhausted.")

# ==============================================================================
# NEWS & RSS
# ==============================================================================
def get_gnews_api_sources(query_keywords, category):
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing. Skipping to fallback.")
        return []

    log(f"   📡 Querying GNews API for: '{query_keywords}'...")
    clean_query = query_keywords.replace(',', ' OR ')
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(clean_query)}&lang=en&country=us&max=5&apikey={api_key}"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200 or 'articles' not in data:
            return []
        formatted_items = []
        for art in data.get('articles', []):
            formatted_items.append({
                "title": art.get('title'),
                "link": art.get('url'),
                "date": art.get('publishedAt', str(datetime.date.today())),
                "image": art.get('image')
            })
        log(f"   ✅ GNews found {len(formatted_items)} articles.")
        return formatted_items
    except Exception as e:
        log(f"   ❌ GNews Connection Failed: {e}")
        return []

def get_real_news_rss(query_keywords, category):
    try:
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

# ==============================================================================
# DUPLICATION & HISTORY
# ==============================================================================
def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): return json.load(open('knowledge_graph.json','r'))
    except: pass
    return []

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

def get_recent_titles_string(category=None, limit=100):
    kg = load_kg()
    if not kg: return "No previous articles found."
    if category: relevant_items = [i for i in kg if i.get('section') == category]
    else: relevant_items = kg
    recent_items = relevant_items[-limit:]
    titles = [f"- {i.get('title','Unknown')}" for i in recent_items]
    if not titles: return "No previous articles in this category."
    return "\n".join(titles)

def get_relevant_kg_for_linking(current_title, current_category, limit=60):
    kg = load_kg()
    same_cat = [i for i in kg if i.get('section') == current_category]
    other_cat = [i for i in kg if i.get('section') != current_category]
    relevant_others = []
    current_keywords = set(current_title.lower().split())
    for item in other_cat:
        item_keywords = set(item['title'].lower().split())
        if len(current_keywords.intersection(item_keywords)) >= 2:
            relevant_others.append(item)
    final_list = same_cat[:4] + relevant_others[:2] 
    output = [{"title": i['title'], "url": i['url']} for i in final_list]
    return json.dumps(output)

def check_semantic_duplication(new_keyword, history_string):
    """
    Hybrid Check: Local Fuzzy Logic + Old AI Model
    """
    if not history_string or len(history_string) < 10: return False
    
    # 1. LOCAL PRE-FILTER
    target = new_keyword.lower().strip()
    existing_titles = [line.replace("- ", "").strip().lower() for line in history_string.split('\n') if line.strip()]
    
    for title in existing_titles:
        if target in title or title in target:
             if len(target) > 4:
                 log(f"      ⛔ BLOCKED (Exact): '{title}'")
                 return True
        similarity = difflib.SequenceMatcher(None, target, title).ratio()
        if similarity > 0.80:
            log(f"      ⛔ BLOCKED (Local): {int(similarity*100)}% match with '{title}'")
            return True

    # 2. AI JUDGE
    log(f"   🧠 Semantic Check: Asking AI Judge about '{new_keyword}'...")
    judge_model = get_oldest_judge_model()
    prompt = f"""
    TASK: Duplication Check.
    NEW TOPIC: "{new_keyword}"
    PAST ARTICLES: {history_string}
    QUESTION: Is "NEW TOPIC" semantically identical to any "PAST ARTICLES"?
    OUTPUT JSON: {{"is_duplicate": true/false}}
    """
    try:
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        if is_dup: log("      ⛔ BLOCKED (AI): Duplicate detected.")
        else: log("      ✅ PASSED (AI): Unique.")
        return is_dup
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error: {e}. Proceeding.")
        return False

# ==============================================================================
# BLOGGER & PUBLISHING
# ==============================================================================
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

# ==============================================================================
# IMAGES & SCRAPING
# ==============================================================================
def extract_og_image(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        meta = soup.find('meta', property='og:image')
        if meta and meta.get('content'): return meta['content']
        meta = soup.find('meta', name='twitter:image')
        if meta and meta.get('content'): return meta['content']
        return None
    except: return None

def upload_to_github_cdn(image_bytes, filename):
    try:
        gh_token = os.getenv('MY_GITHUB_TOKEN')
        image_repo_name = os.getenv('GITHUB_IMAGE_REPO') 
        if not image_repo_name: image_repo_name = os.getenv('GITHUB_REPO_NAME')
        if not gh_token or not image_repo_name: return None

        g = Github(gh_token)
        repo = g.get_repo(image_repo_name)
        date_folder = datetime.datetime.now().strftime("%Y-%m")
        file_path = f"images/{date_folder}/{filename}"
        
        try:
            repo.create_file(path=file_path, message=f"🤖 Auto-upload: {filename}", content=image_bytes.getvalue(), branch="main")
        except Exception as e:
            if "already exists" in str(e):
                filename = f"{random.randint(1000,9999)}_{filename}"
                file_path = f"images/{date_folder}/{filename}"
                repo.create_file(path=file_path, message=f"Retry: {filename}", content=image_bytes.getvalue(), branch="main")
            else: raise e
        
        # NOTE: Using jsdelivr for CDN
        cdn_url = f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
        log(f"      ☁️ Hosted on CDN: {cdn_url}")
        return cdn_url
    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def ensure_haarcascade_exists():
    cascade_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        log("      📥 Downloading Face Detection Model...")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        try:
            r = requests.get(url, timeout=30)
            with open(cascade_path, 'wb') as f: f.write(r.content)
        except Exception as e: return None
    return cascade_path

def apply_smart_privacy_blur(pil_image):
    try:
        img_np = np.array(pil_image)
        if img_np.shape[2] == 4: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        cascade_path = ensure_haarcascade_exists()
        if not cascade_path: return pil_image
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            log(f"      🕵️‍♂️ Detected {len(faces)} face(s). Blurring...")
            h_img, w_img, _ = img_np.shape
            for (x, y, w, h) in faces:
                pad_w, pad_h = int(w*0.6), int(h*0.6)
                x1, y1 = max(0, x - pad_w), max(0, y - pad_h)
                x2, y2 = min(w_img, x + w + pad_w), min(h_img, y + h + int(h*0.8))
                roi = img_np[y1:y2, x1:x2]
                k_size = (w // 2) | 1
                k_size = max(k_size, 51)
                try:
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 0)
                    img_np[y1:y2, x1:x2] = blurred_roi
                except: continue
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
    except: return pil_image.filter(ImageFilter.GaussianBlur(radius=15))

def select_best_image_with_gemini(model_name, article_title, images_list):
    if not images_list: return None
    log(f"   🤖 AI Vision: Selecting best image...")
    valid_images = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for img_data in images_list[:4]: 
        try:
            r = requests.get(img_data['url'], headers=headers, timeout=10)
            if r.status_code == 200:
                valid_images.append({"mime_type": "image/jpeg", "data": r.content, "original_url": img_data['url']})
        except: pass

    if not valid_images: return None
    prompt = f"TASK: Select best image index (0-{len(valid_images)-1}) for '{article_title}'. Return Integer only."
    try:
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)
        inputs = [prompt]
        for img in valid_images: inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))
        response = client.models.generate_content(model="gemini-2.0-flash", contents=inputs)
        match = re.search(r'\d+', response.text)
        if match:
            idx = int(match.group())
            if 0 <= idx < len(valid_images): return valid_images[idx]['original_url']
    except: pass
    return images_list[0]['url']

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0: draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def process_source_image(source_url, overlay_text, filename_title):
    if not source_url or source_url.startswith('/'): return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        original_img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        target_w, target_h = 1200, 630
        img_ratio = original_img.width / original_img.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_width = int(target_h * img_ratio)
            new_height = target_h
        else:
            new_width = target_w
            new_height = int(target_w / img_ratio)
        original_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        base_img = original_img.crop((left, top, left + target_w, top + target_h))
        
        base_img_rgb = base_img.convert("RGB")
        base_img_rgb = apply_smart_privacy_blur(base_img_rgb)
        base_img = base_img_rgb.convert("RGBA")
        
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            W, H = base_img.size
            try:
                font_path = "arialbd.ttf"
                if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                font = ImageFont.truetype(font_path, 80) 
            except: font = ImageFont.load_default()
            
            words = overlay_text.upper().split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] < W - 80: current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))
            
            text_y = H / 2 - (len(lines) * 90 / 2)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_x = (W - (bbox[2] - bbox[0])) / 2
                draw_text_with_outline(draw, (line_x, text_y), line, font, "#FFD700", "black", 5)
                text_y += 95

        img_byte_arr = BytesIO()
        base_img.convert("RGB").save(img_byte_arr, format='WEBP', quality=85)
        safe_filename = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50] + ".webp"
        return upload_to_github_cdn(img_byte_arr, safe_filename)
    except Exception as e:
        log(f"      ⚠️ Source Image Error: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    log(f"   🎨 Generating AI Thumbnail...")
    enhancers = ", photorealistic, shot on Sony A7R IV, 8k, youtube thumbnail style"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}")
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"
    try:
        r = requests.get(image_url, timeout=60)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        if overlay_text:
            draw = ImageDraw.Draw(img)
            W, H = img.size
            try: font = ImageFont.truetype("arial.ttf", 80)
            except: font = ImageFont.load_default()
            text = overlay_text.upper()
            bbox = draw.textbbox((0,0), text, font=font)
            x, y = (W - (bbox[2]-bbox[0]))/2, H - (bbox[3]-bbox[1]) - 50
            for dx in range(-4,5):
                for dy in range(-4,5): draw.text((x+dx, y+dy), text, font=font, fill="black")
            draw.text((x,y), text, font=font, fill="yellow")
        
        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='WEBP', quality=85)
        return upload_to_github_cdn(img_byte_arr, f"ai_gen_{seed}.webp")
    except Exception as e: return None

# ==============================================================================
# MAIN PIPELINE
# ==============================================================================
def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "models/gemini-2.0-flash")
    
    # 1. STRATEGY
    target_keyword = ""
    is_manual_mode = False

    if forced_keyword:
        log(f"\n🔄 RETRY MODE: Trying fallback keyword in '{category}': '{forced_keyword}'")
        target_keyword = forced_keyword
        is_manual_mode = True
    else:
        log(f"\n🚀 INIT PIPELINE: {category} (AI Strategist Mode)")
        recent_titles = get_recent_titles_string(category=category, limit=100)
        strategy_success = False
        for attempt in range(1, 3):
            try:
                seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_titles)
                seo_plan = generate_step_strict(model_name, seo_prompt, f"Step 0 (SEO Strategy - Attempt {attempt})", required_keys=["target_keyword"])
                target_keyword = seo_plan.get('target_keyword')
                if target_keyword:
                    log(f"   🎯 Strategy Defined: Targeting '{target_keyword}'")
                    strategy_success = True
                    break
            except Exception as e:
                log(f"   ⚠️ Strategy attempt {attempt} failed: {e}")
                time.sleep(2)
        if not strategy_success:
            log("   ❌ SEO Strategy failed. Switching to fallback.")
            return False

    # 2. SEMANTIC GUARD (SMART TIME-WINDOW)
    days_lookback = 7 if is_manual_mode else 60
    kg_data = load_kg()
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_lookback)
    relevant_history = []
    for item in kg_data:
        try:
            item_date = datetime.datetime.strptime(item.get('date', '2024-01-01'), "%Y-%m-%d").date()
            if item_date >= cutoff_date: relevant_history.append(f"- {item.get('title')}")
        except: pass
    history_string = "\n".join(relevant_history) if relevant_history else "No recent articles."

    if check_semantic_duplication(target_keyword, history_string):
        log(f"   🚫 ABORTING: Topic '{target_keyword}' covered in last {days_lookback} days.")
        return False
    else:
        log(f"   ✅ PASSED: Topic fresh enough (Lookback: {days_lookback} days).")

    # 3. SOURCE HUNTING
    rss_items = get_gnews_api_sources(target_keyword, category)
    if not rss_items:
        log("   🔄 GNews yielded no results. Switching to Legacy RSS Scraping...")
        rss_items = get_real_news_rss(f"{target_keyword}", category)

    if not rss_items:
        log(f"   ⚠️ No news found via API or RSS for '{target_keyword}'.")
        return False

    collected_sources = []
    main_headline = ""
    main_link = ""
    required_terms = target_keyword.lower().split()
    significant_keyword = max(required_terms, key=len) if required_terms else ""
    
    log(f"   🕵️‍♂️ Investigating sources for: '{target_keyword}'...")
    for item in rss_items[:8]:
        if significant_keyword and len(significant_keyword) > 3:
            if significant_keyword not in item['title'].lower() and significant_keyword not in item['link'].lower():
                continue
        if any(src['domain'] in item['link'] for src in collected_sources): continue

        data = url_resolver.get_page_html(item['link'])
        if data and data.get('html'):
            text = trafilatura.extract(data['html'], include_comments=False, include_tables=True)
            if not text:
                soup = BeautifulSoup(data['html'], 'html.parser')
                for s in soup(["script", "style", "nav", "footer"]): s.extract()
                text = soup.get_text(" ", strip=True)
            
            if text and len(text) >= 600:
                log(f"         ✅ Accepted Source! ({len(text)} chars).")
                collected_sources.append({
                    "title": item['title'], "text": text,
                    "domain": urllib.parse.urlparse(data['url']).netloc,
                    "url": data['url'], "date": item['date'],
                    "source_image": extract_og_image(data['html'])
                })
                if not main_headline: main_headline, main_link = item['title'], item['link']
                if len(collected_sources) >= 3: break
        time.sleep(1.5)

    if not collected_sources: return False
        
    # REDDIT INTEL
    reddit_context = ""
    try:
        reddit_context = reddit_manager.get_community_intel(target_keyword)
        if reddit_context: log(f"   ✅ Acquired smart community insights from Reddit.")
    except: pass
    
    # 4. EXECUTION
    try:
        log(f"\n✍️ Synthesizing Content...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"
        combined_text += f"\n\n{reddit_context}\n"
        
        sources_list_formatted = [{"title": s['title'], "url": s['url']} for s in collected_sources]
        json_ctx = {"rss_headline": main_headline, "keyword_focus": target_keyword, "source_count": len(collected_sources), "date": str(datetime.date.today()), "style_guide": "Critical, First-Person, Beginner-Focused"}
        
        payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** RESEARCH DATA ***\n{combined_text}"
        json_b = generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)", required_keys=["headline", "hook", "article_body", "verdict"])
        
        current_headline = json_b.get('headline', target_keyword)
        kg_links = get_relevant_kg_for_linking(current_headline, category)
        input_c = {"draft_content": json_b, "sources_data": sources_list_formatted}
        json_c = generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), "Step C (SEO)", required_keys=["finalTitle", "finalContent", "seo", "imageGenPrompt"])
        json_d = generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D (Humanizer)", required_keys=["finalTitle", "finalContent", "seo", "imageGenPrompt"])
        final = generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), "Step E (Final Polish)", required_keys=["finalTitle", "finalContent", "seo", "imageGenPrompt"])
        
        title = final['finalTitle']
        content_html = final['finalContent']
        seo_data = final.get('seo', {})
        img_prompt = final.get('imageGenPrompt', title)
        img_overlay = final.get('imageOverlayText', 'News')

        # MULTIMEDIA
        log("   🧠 Generating Multimedia Assets...")
        yt_meta = generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title", "description", "tags"])
        fb_dat = generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)
        
        log("   🖼️ Image Strategy...")
        candidate_images = []
        for src in collected_sources:
            if src.get('source_image'): candidate_images.append({'url': src['source_image'], 'domain': src['domain']})
        
        selected_source_image = None
        if candidate_images: selected_source_image = select_best_image_with_gemini(model_name, title, candidate_images)
        overlay_text_clean = img_overlay if img_overlay else "LATEST NEWS"
        
        img_url = None
        if selected_source_image:
            img_url = process_source_image(selected_source_image, overlay_text_clean, title)
        if not img_url:
            safe_prompt = f"{img_prompt}, abstract technology, blurred background, no people, no skin, no faces, futuristic, 3d render"
            img_url = generate_and_upload_image(safe_prompt, overlay_text_clean)

        summ_clean = re.sub('<[^<]+?>','', content_html)[:2500]
        script_json = None
        for attempt in range(1, 3):
            try:
                raw_result = generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ_clean), f"Video Script (Att {attempt})")
                if isinstance(raw_result, dict):
                    if 'video_script' in raw_result: script_json = raw_result['video_script']
                    elif 'script' in raw_result: script_json = raw_result['script']
                elif isinstance(raw_result, list): script_json = raw_result
                if script_json: break
            except: pass

        vid_main, vid_short, vid_html, fb_path = None, None, "", None
        if script_json and len(script_json) > 0:
            ts = int(time.time())
            out_dir = os.path.abspath("output")
            os.makedirs(out_dir, exist_ok=True)
            
            try:
                rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
                main_p = os.path.join(out_dir, f"main_{ts}.mp4")
                pm = rr.render_video(script_json, title, main_p)
                if pm and os.path.exists(pm):
                    desc = f"{yt_meta.get('description','')}\n\n🚀 Full Story: {main_link}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                    if vid_main: 
                        vid_html = f'''<div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen loading="lazy" title="{title}"></iframe></div>'''
            except: pass

            try:
                rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
                short_p = os.path.join(out_dir, f"short_{ts}.mp4")
                ps = rs.render_video(script_json, title, short_p)
                if ps and os.path.exists(ps):
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
            except: pass

        # VALIDATION
        log("   🛡️ Initiating Self-Healing Validation...")
        try:
            val_client = genai.Client(api_key=key_manager.get_current_key())
            healer = content_validator_pro.AdvancedContentValidator(val_client)
            full_text = "\n".join([s['text'] for s in collected_sources])
            content_html = healer.run_professional_validation(content_html, full_text, collected_sources)
        except Exception as e: log(f"   ⚠️ Validation Error: {e}")

        # PUBLISH
        log("   🚀 Publishing to Blogger...")
        author_box = """<div style="margin-top:50px; padding:25px; background:#f8f9fa; border-left: 5px solid #2ecc71; border-radius:8px; font-family:sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:20px;"><img src="https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791" style="width:80px; height:80px; border-radius:50%; object-fit:cover;" alt="Yousef Sameer"><div style="flex:1;"><h4 style="margin:0 0 5px; font-size:20px; color:#2c3e50;">Yousef Sameer</h4><span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:3px 8px; border-radius:4px; font-weight:bold;">TECH EDITOR @ LATESTAI</span><p style="margin:12px 0; font-size:15px; color:#555;">Testing AI tools so you don't break your workflow.</p></div></div></div>"""
        
        content_html = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
        content_html = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', content_html)
        final_content_with_author = content_html + author_box
        
        img_html = ""
        if img_url: 
            alt_text = seo_data.get("imageAltText", title)
            img_html = f'''<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}" style="margin-left:1em; margin-right:1em;"><img border="0" src="{img_url}" alt="{alt_text}" width="1200" height="630" style="max-width:100%; height:auto; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" /></a></div>'''

        full_body = ARTICLE_STYLE + img_html + vid_html + final_content_with_author
        if 'schemaMarkup' in final:
            try: full_body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
            except: pass
        
        if not is_manual_mode:
            if check_semantic_duplication(title, history_string):
                 log(f"   🚫 ABORTING PUBLISH: Generated title '{title}' matches recent history.")
                 return False 

        published_url = publish_post(title, full_body, [category, "Tech News", "Explainers"])
        if published_url:
            log(f"✅ PUBLISHED: {published_url}")
            update_kg(title, published_url, category)
            new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL ARTICLE HERE:\n{published_url}\n\n#AI #TechNews"
            if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
            if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
            try:
                if fb_path and os.path.exists(fb_path): 
                    social_manager.post_reel_to_facebook(fb_path, f"{fb_cap}\n\nRead more: {published_url}\n\n#AI")
                elif img_url:
                    social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{published_url}", published_url, img_url)
            except Exception as e: log(f"   ⚠️ Social Error: {e}")
            return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        import traceback
        traceback.print_exc()
        return False
    return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ No Config.")
        return
    
    all_categories = list(cfg['categories'].keys())
    random.shuffle(all_categories)
    log(f"🎲 Session Categories: {all_categories}")
    
    success = False
    for category in all_categories:
        log(f"\n📁 SWITCHING TO CATEGORY: {category}")
        if run_pipeline(category, cfg, forced_keyword=None):
            success = True
            break 
        log(f"   ⚠️ AI Strategy failed. Switching to Manual List...")
        trending_text = cfg['categories'][category].get('trending_focus', '')
        if trending_text:
            manual_topics = [t.strip() for t in trending_text.split(',') if t.strip()]
            random.shuffle(manual_topics)
            for topic in manual_topics:
                log(f"   👉 Trying Manual Topic: '{topic}'")
                if run_pipeline(category, cfg, forced_keyword=topic):
                    success = True
                    break 
            if success: break 
            
    if success:
        log("\n✅ MISSION ACCOMPLISHED.")
        perform_maintenance_cleanup()
    else:
        log("\n❌ MISSION FAILED. Exhausted all attempts.")

if __name__ == "__main__":
    main()
