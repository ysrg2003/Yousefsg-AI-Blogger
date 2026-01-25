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

# User-Agent Rotation List (Advanced Scraper Pro)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils", "unveiled",
    "poised to", "delve into", "game-changer", "paradigm shift", "tapestry", "robust",
    "leverage", "underscore", "testament to", "beacon of", "In conclusion",
    "Remember that", "It is important to note", "Imagine a world", "fast-paced world",
    "cutting-edge", "realm of"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. HELPER UTILITIES (SMART KEY MANAGER & DISCOVERY)
# ==============================================================================

TRIED_MODELS = set()
CURRENT_MODEL_OVERRIDE = None

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
            log(f"   🔄 Switching to Key #{self.current_index + 1}...")
            return True
        log("   ⚠️ All keys exhausted. Resetting to Key #1 and triggering Model Discovery...")
        self.current_index = 0
        return False 

key_manager = KeyManager()

import logging
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested. 
No explanations, no headings, no extra text, no apologies. 
Output exactly and only what the user asked for. 
If the user requests JSON, return PURE JSON. 
Obey safety policy.
"""

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
        raise JSONValidationError(f"Expected Dictionary output, but got type: {type(data)}")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise JSONValidationError(f"JSON is valid but missing required keys: {missing_keys}")
    return True

def discover_fresh_model(current_model_name):
    """Finds a new model when the current one fails on all keys."""
    global CURRENT_MODEL_OVERRIDE
    log(f"   🕵️‍♂️ Discovery Mode: Finding replacement for {current_model_name}...")
    TRIED_MODELS.add(current_model_name.replace('models/', ''))
    
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    candidates = []
    try:
        for m in client.models.list():
            m_name = m.name.replace('models/', '')
            if 'gemini' in m_name and 'embedding' not in m_name:
                if m_name not in TRIED_MODELS:
                    candidates.append(m_name)
    except Exception as e:
        log(f"   ⚠️ Listing models failed: {e}")

    # STRICT PRIORITY LIST
    priority_list = [
        "gemini-3-flash-preview", 
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"
    ]
    
    final_choice = None
    for p in priority_list:
        if p in candidates:
            final_choice = p
            break
        if not candidates and p not in TRIED_MODELS:
            final_choice = p
            break
            
    if final_choice:
        log(f"   💡 New Model Selected: {final_choice}")
        CURRENT_MODEL_OVERRIDE = final_choice 
        return final_choice
    
    log("   ❌ Fatal: No untried models left.")
    return None

@retry(
    stop=stop_after_attempt(15), 
    wait=wait_exponential(multiplier=2, min=4, max=30), 
    retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)), 
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    # Enforce priority: Override > Initial
    model_to_use = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else initial_model_name
    model_to_use = model_to_use.replace("models/", "") 
    
    log(f"   🔄 [Tenacity] Executing: {step_name} | Model: {model_to_use}")
    
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: All API Keys exhausted.")
    
    client = genai.Client(api_key=key)
    
    try:
        time.sleep(5) 
        
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=STRICT_SYSTEM_PROMPT, 
            temperature=0.3, 
            top_p=0.8
        )
        
        response = client.models.generate_content(
            model=model_to_use, 
            contents=prompt, 
            config=generation_config
        )
        
        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ Parsing failed. Triggering Repair...")
            time.sleep(2)
            repair_response = client.models.generate_content(
                model=model_to_use, 
                contents=f"Fix JSON Syntax:\n{response.text[:5000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_response.text)
            if not parsed_data: raise JSONParsingError(f"Failed to parse JSON for {step_name}")

        if required_keys: validate_structure(parsed_data, required_keys)
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        is_429 = "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg
        is_404 = "404" in error_msg or "not found" in error_msg
        is_403 = "403" in error_msg or "permission" in error_msg
        
        if is_429 or is_403:
            log(f"      ⚠️ API Error ({'429' if is_429 else '403'}) on Key #{key_manager.current_index + 1}.")
            if not key_manager.switch_key():
                log(f"      ⛔ Model {model_to_use} failed on ALL keys. Switching Model...")
                time.sleep(20) 
                new_model = discover_fresh_model(model_to_use)
                if not new_model: raise RuntimeError("FATAL: All models failed.")
            raise e 
            
        elif is_404:
             log(f"      ❌ Model {model_to_use} NOT FOUND. Switching immediately.")
             discover_fresh_model(model_to_use)
             raise e 
             
        else:
            log(f"      ❌ General Error: {str(e)[:200]}")
            raise e

# ==============================================================================
# 3. NEWS & HISTORY UTILITIES
# ==============================================================================

def get_gnews_api_sources(query_keywords, category):
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        log("   ⚠️ GNews API Key missing/not loaded.")
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

def get_real_news_rss(query_keywords):
    # This function now takes a single query string to support the loop logic in main pipeline
    try:
        encoded = urllib.parse.quote(query_keywords)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        items = []
        if feed.entries:
            for entry in feed.entries[:8]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                items.append({"title": title_clean, "link": entry.link, "date": pub})
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
    if not history_string or len(history_string) < 10: return False
    
    # 1. LOCAL CHECK
    target = new_keyword.lower().strip()
    existing_titles = [line.replace("- ", "").strip().lower() for line in history_string.split('\n') if line.strip()]
    
    for title in existing_titles:
        if target in title or title in target:
             if len(target) > 5:
                 log(f"      ⛔ BLOCKED (Local Exact): '{title}'")
                 return True
        similarity = difflib.SequenceMatcher(None, target, title).ratio()
        if similarity > 0.85:
            log(f"      ⛔ BLOCKED (Local Fuzzy): {int(similarity*100)}% match with '{title}'")
            return True

    # 2. AI JUDGE
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    
    log(f"   🧠 Semantic Check: Asking AI Judge ({judge_model}) about '{new_keyword}'...")
    
    prompt = f"""
    TASK: Duplication Check.
    NEW TOPIC: "{new_keyword}"
    PAST ARTICLES: {history_string}
    QUESTION: Is "NEW TOPIC" covering the exact same event/story as any "PAST ARTICLES"?
    OUTPUT JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
    """
    try:
        result = generate_step_strict(judge_model, prompt, "Semantic Judge", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        if is_dup: log("      ⛔ BLOCKED (AI): Duplicate detected.")
        else: log("      ✅ PASSED (AI): Unique.")
        return is_dup
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error: {e}. Assuming safe.")
        return False

# ==============================================================================
# 4. ADVANCED SCRAPER PRO (Eager + User-Agent + Validation)
# ==============================================================================

def is_valid_article_text(text):
    """Validation Layer 2.0: Checks if scraped text is garbage or high quality."""
    if not text or len(text) < 600: return False
    
    # Check for junk phrases that indicate scraper blocking
    junk_indicators = [
        "JavaScript is required", "enable cookies", "access denied", 
        "security check", "please verify you are a human", "403 forbidden",
        "captcha", "cloudflare", "Incapsula", "robot"
    ]
    
    text_lower = text.lower()[:500] # Check first 500 chars usually contains these messages
    for junk in junk_indicators:
        if junk in text_lower:
            return False
            
    return True

def resolve_and_scrape(google_url):
    log(f"      🕵️‍♂️ Selenium: Opening & Resolving: {google_url[:60]}...")
    
    # Random User-Agent for Scraper Pro
    random_ua = random.choice(USER_AGENTS)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Fix 1: Block images to save bandwidth
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
    # Fix 2: Eager loading strategy (DOM only, skips ads/heavy scripts)
    chrome_options.page_load_strategy = 'eager' 
    chrome_options.add_argument(f'user-agent={random_ua}')
    chrome_options.add_argument("--mute-audio") 

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25) # Slightly increased timeout for safety
        
        driver.get(google_url)
        start_wait = time.time()
        final_url = google_url
        while time.time() - start_wait < 15: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1) 
        
        extracted_text = trafilatura.extract(driver.page_source, include_comments=False, include_tables=True, favor_precision=True)
        if is_valid_article_text(extracted_text):
             return final_url, driver.title, extracted_text

        # Fallback to BeautifulSoup if trafilatura fails or returns junk
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form", "iframe"]): 
            script.extract()
        
        bs_text = soup.get_text(" ", strip=True)
        if is_valid_article_text(bs_text):
            return final_url, driver.title, bs_text
            
        return None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {e}")
        return None, None, None
    finally:
        if driver: driver.quit()

# ==============================================================================
# 5. IMAGE PROCESSING
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

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0: draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

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
        
        return f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def ensure_haarcascade_exists():
    cascade_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
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
                pad_w = int(w*0.6) 
                pad_h = int(h*0.6)
                pad_h_bottom = int(h * 0.8)
                x1 = max(0, x - pad_w)
                y1 = max(0, y - pad_h)
                x2 = min(w_img, x + w + pad_w)
                y2 = min(h_img, y + h + pad_h_bottom)
                roi = img_np[y1:y2, x1:x2]
                k_size = (w // 2) | 1
                k_size = max(k_size, 51)
                try:
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 0)
                    img_np[y1:y2, x1:x2] = blurred_roi
                except: continue
        return Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
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
    
    vision_models = [
        "gemini-3-flash-preview", 
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp", 
        "gemini-1.5-flash"
    ]
    
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    inputs = [prompt]
    for img in valid_images: inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))

    for v_model in vision_models:
        try:
            response = client.models.generate_content(model=v_model, contents=inputs)
            match = re.search(r'\d+', response.text)
            if match:
                idx = int(match.group())
                if 0 <= idx < len(valid_images): 
                    log(f"      ✅ Vision Success ({v_model}): Selected Image #{idx+1}")
                    return valid_images[idx]['original_url']
        except Exception as e:
            continue

    return images_list[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    if not source_url or source_url.startswith('/'): return None
    log(f"   🖼️ Processing Source Image: {source_url[:60]}...")
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
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
        base_img = original_img.crop((left, top, left+target_w, top+target_h))
        
        base_img = apply_smart_privacy_blur(base_img.convert("RGB")).convert("RGBA")
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            W, H = base_img.size
            try: font = ImageFont.truetype("arialbd.ttf", 80) 
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
# 6. MAIN PIPELINE (SMART MULTI-SOURCE HUNTING)
# ==============================================================================

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
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

    # 2. SEMANTIC GUARD
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

    # 3. SMART MULTI-SOURCE HUNTING (Loop until 3 quality sources)
    collected_sources = []
    main_headline = ""
    main_link = ""
    words = target_keyword.split()
    significant_word = max(words, key=len) if words else category
    
    # 2. مصفوفة استراتيجيات البحث (بدون كلمة News التافهة)
    # المستوى الأول: بحث حرفي دقيق
    # المستوى الثاني: بحث عن الأحداث (Revealed, Hands-on)
    # المستوى الثالث: بحث مقارن (Vs) لجلب مقالات دسمة
    # المستوى الرابع: بحث عن التحديثات السنوية الحصرية
    search_strategies = [
        f'"{target_keyword}"', 
        f'{target_keyword} (breakthrough OR revealed OR "hands-on" OR review)',
        f'{significant_word} vs (Sora OR ChatGPT OR Gemini OR Claude OR " ")',
        f'{category} update'
    ]

    for attempt_idx, attempt in enumerate(search_attempts):
        if len(collected_sources) >= 3:
            log(f"   ✅ Collected sufficient sources ({len(collected_sources)}). Moving on.")
            break
            
        log(f"   🕵️‍♂️ Source Hunting (Level {attempt_idx+1}): {attempt['type']} -> '{attempt['query']}'")
        
        items = []
        if attempt['type'] == "GNEWS":
            items = get_gnews_api_sources(attempt['query'], category)
        else:
            items = get_real_news_rss(attempt['query'])
            
        for item in items:
            if len(collected_sources) >= 3: break
            
            # Deduplication
            if any(src['url'] == item['link'] for src in collected_sources): continue
            
            # Simple relevance check (skip if too irrelevant)
            if attempt_idx < 2 and significant_keyword and len(significant_keyword) > 3:
                if significant_keyword not in item['title'].lower() and significant_keyword not in item['link'].lower():
                    continue

            # SCRAPE & VALIDATE (Scraper Pro)
            final_url, final_title, text = resolve_and_scrape(item['link'])
            
            if text: # is_valid_article_text already checked inside resolve_and_scrape
                log(f"         ✅ Accepted Source! ({len(text)} chars).")
                
                # Try to preserve original image if possible
                source_img = item.get('image')
                if not source_img:
                    # Fallback: try to guess OG image from URL if possible (usually not reliable without HTML parsing again)
                    pass

                collected_sources.append({
                    "title": final_title if final_title else item['title'], 
                    "text": text,
                    "domain": urllib.parse.urlparse(final_url).netloc,
                    "url": final_url, 
                    "date": item['date'],
                    "source_image": source_img
                })
                if not main_headline: main_headline, main_link = item['title'], item['link']
            
            time.sleep(1.5) # Be polite

    if not collected_sources:
        log(f"   ❌ No valid sources found for '{target_keyword}' after all attempts.")
        return False
        
    # REDDIT INTEL
    reddit_context = ""
    try:
        reddit_context = reddit_manager.get_community_intel(target_keyword)
        if reddit_context: log(f"   ✅ Acquired smart community insights from Reddit.")
    except: pass
    
    # 4. EXECUTION
    try:
        log(f"\n✍️ Synthesizing Content from {len(collected_sources)} sources...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nLink: {src['url']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"
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
        for attempt in range(1, 4):
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
        
        # Updated Author Box with Socials
        author_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Yousef S. | Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
                   
                    
                    <div style="display:flex; gap:15px; margin-top:10px; flex-wrap:wrap;">
                        <a href="https://www.facebook.com/share/1AkVHBNbV1/" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Facebook"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="24" height="24" alt="FB"></a>
                        <a href="https://x.com/latestaime" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="X (Twitter)"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24" height="24" alt="X"></a>
                        <a href="https://www.instagram.com/latestai.me" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Instagram"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="24" height="24" alt="IG"></a>
                        <a href="https://m.youtube.com/@0latestai" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="YouTube"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24" height="24" alt="YT"></a>
                        <a href="https://pinterest.com/latestaime" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Pinterest"><img src="https://cdn-icons-png.flaticon.com/512/145/145808.png" width="24" height="24" alt="Pin"></a>
                        <a href="https://reddit.com/user/Yousefsg/" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24" height="24" alt="Reddit"></a>
                        <a href="https://www.latestai.me" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Website"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24" height="24" alt="Web"></a>
                    </div>
                </div>
            </div>
        </div>
        """
        
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
