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
# 1. CSS STYLING
# ==============================================================================
ARTICLE_STYLE = """
"""

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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=15), retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)), before_sleep=before_sleep_log(logger, logging.WARNING))
def generate_step_strict(model_name, prompt, step_name, required_keys=[]):
    log(f"   🔄 [Tenacity] Executing: {step_name}...")
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: All API Keys exhausted.")
    
    client = genai.Client(api_key=key)
    try:
        generation_config = types.GenerateContentConfig(response_mime_type="application/json", system_instruction=STRICT_SYSTEM_PROMPT, temperature=0.3, top_p=0.8)
        response = client.models.generate_content(model=model_name, contents=prompt, config=generation_config)
        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ Parsing failed locally for {step_name}. Triggering AI Repair...")
            repair_prompt = f"SYSTEM ALERT: Invalid JSON. Fix syntax.\nCONTENT:\n{response.text[:10000]}"
            repair_response = client.models.generate_content(model="gemini-2.5-flash", contents=repair_prompt, config=generation_config)
            parsed_data = master_json_parser(repair_response.text)
            if not parsed_data: raise JSONParsingError(f"Failed to parse JSON for {step_name}")
            else: log(f"      ✅ AI Repair Successful for {step_name}!")

        if required_keys: validate_structure(parsed_data, required_keys)
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "resource exhausted" in error_msg:
            log("      ⚠️ Quota Exceeded (429). Switching Key & Retrying immediately...")
            if key_manager.switch_key(): raise e 
            else: raise RuntimeError("FATAL: All keys exhausted during retry.")
        log(f"      ❌ Attempt Failed for {step_name}: {str(e)[:200]}")
        raise e

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

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): return json.load(open('knowledge_graph.json','r'))
    except: pass
    return []

def get_recent_titles_string(category=None, limit=100):
    kg = load_kg()
    if not kg: return "No previous articles found."
    if category:
        relevant_items = [i for i in kg if i.get('section') == category]
    else:
        relevant_items = kg
    recent_items = relevant_items[-limit:]
    titles = [f"- {i.get('title','Unknown')}" for i in recent_items]
    if not titles: return "No previous articles in this category."
    return "\n".join(titles)
    
def get_relevant_kg_for_linking(current_title, current_category, limit=60):
    kg = load_kg()
    links = []
    
    # 1. الأولوية: مقالات من نفس القسم (لتقوية التخصص)
    same_cat = [i for i in kg if i.get('section') == current_category]
    
    # 2. الثانوية: مقالات من أقسام أخرى ولكنها ذات صلة (بحث بالكلمات المفتاحية)
    # حيلة بسيطة: هل هناك كلمات مشتركة في العنوان؟
    other_cat = [i for i in kg if i.get('section') != current_category]
    relevant_others = []
    
    current_keywords = set(current_title.lower().split())
    for item in other_cat:
        item_keywords = set(item['title'].lower().split())
        # إذا تطابقت كلمتان أو أكثر (غير حروف الجر)، اعتبره ذا صلة
        if len(current_keywords.intersection(item_keywords)) >= 2:
            relevant_others.append(item)

    # ادمج القائمتين مع إعطاء الأولوية للقسم الحالي
    final_list = same_cat[:4] + relevant_others[:2] 
    
    output = [{"title": i['title'], "url": i['url']} for i in final_list]
    return json.dumps(output)

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

# ==============================================================================
# 4. SCRAPING (Optimized)
# ==============================================================================
def resolve_and_scrape(google_url):
    log(f"      🕵️‍♂️ Selenium: Opening & Resolving: {google_url[:60]}...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # CRITICAL OPTIMIZATION: Block images to save resources
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument("--mute-audio") 

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(20) # 20s timeout
        
        driver.get(google_url)
        start_wait = time.time()
        final_url = google_url
        while time.time() - start_wait < 15: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1) 
        
        final_title = driver.title
        page_source = driver.page_source
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None

        log(f"      🔗 Resolved URL: {final_url[:70]}...")
        log(f"      🏷️ Real Page Title: {final_title[:70]}...")

        extracted_text = trafilatura.extract(page_source, include_comments=False, include_tables=True, favor_precision=True)
        if extracted_text and len(extracted_text) > 1000: return final_url, final_title, extracted_text

        soup = BeautifulSoup(page_source, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]): script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        return final_url, final_title, fallback_text

    except Exception as e:
        log(f"      ❌ Selenium Error: {e}")
        return None, None, None
    finally:
        if driver: driver.quit()

# ==============================================================================
# IMAGE PROCESSING
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
        if not gh_token or not image_repo_name:
            log("      ❌ GitHub Token or Image Repo Name missing.")
            return None

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
                repo.create_file(path=file_path, message=f"🤖 Auto-upload (Retry): {filename}", content=image_bytes.getvalue(), branch="main")
            else: raise e

        cdn_url = f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
        log(f"      ☁️ Hosted on Public CDN: {cdn_url}")
        return cdn_url
    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def ensure_haarcascade_exists():
    cascade_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        log("      📥 Downloading Face Detection Model (Haar Cascade)...")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        try:
            r = requests.get(url, timeout=30)
            with open(cascade_path, 'wb') as f: f.write(r.content)
        except Exception as e:
            log(f"      ⚠️ Failed to download Haar Cascade: {e}")
            return None
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
        # Use more lenient parameters to find faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            log(f"      🕵️‍♂️ Detected {len(faces)} face(s). Applying NUCLEAR blur...")
            h_img, w_img, _ = img_np.shape
            for (x, y, w, h) in faces:
                # 60% padding logic
                pad_w = int(w * 0.6) 
                pad_h = int(h * 0.6)
                pad_h_bottom = int(h * 0.8)
                x1 = max(0, x - pad_w)
                y1 = max(0, y - pad_h)
                x2 = min(w_img, x + w + pad_w)
                y2 = min(h_img, y + h + pad_h_bottom)
                roi = img_np[y1:y2, x1:x2]
                
                # Dynamic Kernel
                k_size = (w // 2) 
                if k_size % 2 == 0: k_size += 1
                k_size = max(k_size, 51)
                
                try:
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 0)
                    img_np[y1:y2, x1:x2] = blurred_roi
                except: continue
        else:
            log("      🤖 No human faces detected. Keeping image sharp.")

        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
    except Exception as e:
        log(f"      ⚠️ Smart Blur Error: {e}. Fallback to global blur.")
        return pil_image.filter(ImageFilter.GaussianBlur(radius=15))

def select_best_image_with_gemini(model_name, article_title, images_list):
    if not images_list: return None
    log(f"   🤖 Asking Gemini to select the best image from {len(images_list)} candidates...")
    valid_images = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i, img_data in enumerate(images_list[:4]): 
        try:
            r = requests.get(img_data['url'], headers=headers, timeout=10)
            if r.status_code == 200:
                valid_images.append({"mime_type": "image/jpeg", "data": r.content, "original_url": img_data['url']})
        except: pass

    if not valid_images: return None
    prompt = f"""
    TASK: Photo Editor Selection.
    ARTICLE TITLE: "{article_title}"
    CRITERIA FOR SELECTION:
    1. **Relevance:** Image must match the specific tech topic.
    2. **PRIVACY & AESTHETICS:** PREFER images of gadgets, screens, code, robots. AVOID close-up portraits of specific people. AVOID blurry images.
    OUTPUT INSTRUCTIONS: Return ONLY the integer index (0, 1, 2...) of the best image. If ALL images are unsafe/irrelevant, return -1.
    """
    try:
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)
        inputs = [prompt]
        for img in valid_images: inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))
        response = client.models.generate_content(model="gemini-2.5-flash", contents=inputs)
        result = response.text.strip()
        if "-1" in result or "NONE" in result: return None
        import re
        match = re.search(r'\d+', result)
        if match:
            idx = int(match.group())
            if 0 <= idx < len(valid_images):
                log(f"      ✅ Gemini selected Image #{idx+1}.")
                return valid_images[idx]['original_url']
    except Exception as e:
        log(f"      ⚠️ Gemini Vision Error: {e}")
    return images_list[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    log(f"   🖼️ Processing Source Image: {source_url[:60]}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200: return None
        
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
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        base_img = original_img.crop((left, top, right, bottom))
        
        base_img_rgb = base_img.convert("RGB")
        base_img_rgb = apply_smart_privacy_blur(base_img_rgb)
        base_img = base_img_rgb.convert("RGBA")

        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            W, H = base_img.size
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arialbd.ttf"
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
        safe_filename = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50]
        safe_filename += ".webp"
        return upload_to_github_cdn(img_byte_arr, safe_filename)
    except Exception as e:
        log(f"      ⚠️ Source Image Error: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    log(f"   🎨 Generating Thumbnail (Flux + GitHub Host)...")
    enhancers = ", photorealistic, shot on Sony A7R IV, 8k, youtube thumbnail style"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}")
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"
    try:
        r = requests.get(image_url, timeout=60)
        if r.status_code != 200: return None
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        if overlay_text:
            draw = ImageDraw.Draw(img)
            W, H = img.size
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arial.ttf"
                font = ImageFont.truetype(font_path, 80)
            except: font = ImageFont.load_default()
            text = overlay_text.upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (W - text_w) / 2
            y = H - text_h - 50
            for dx in range(-4, 5):
                for dy in range(-4, 5): draw.text((x+dx, y+dy), text, font=font, fill="black")
            draw.text((x, y), text, font=font, fill="yellow")
        
        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='WEBP', quality=85)
        filename = f"ai_gen_{seed}.webp"
        return upload_to_github_cdn(img_byte_arr, filename)
    except Exception as e:
        log(f"      ⚠️ AI Image Error: {e}")
        return None

# ==============================================================================
# MAIN PIPELINE
# ==============================================================================

def check_semantic_duplication(new_keyword, history_string):
    if not history_string or len(history_string) < 10: return False
    log(f"   🧠 Checking for Semantic Cannibalization: '{new_keyword}'...")
    prompt = f"""
    TASK: SEO Cannibalization Check.
    NEW KEYWORD: "{new_keyword}"
    EXISTING ARTICLES: {history_string}
    QUESTION: Does the "NEW KEYWORD" target the **same search intent** as any of the "EXISTING ARTICLES"? 
    OUTPUT: Return ONLY JSON: {{"is_duplicate": true}} OR {{"is_duplicate": false}}
    """
    try:
        result = generate_step_strict("models/gemini-2.5-flash", prompt, "Semantic Check", required_keys=["is_duplicate"])
        is_dup = result.get('is_duplicate', False)
        if is_dup: log(f"      ⛔ BLOCKED: Semantic Duplicate Detected!")
        else: log(f"      ✅ PASSED: Topic appears semantically unique.")
        return is_dup
    except Exception as e:
        log(f"      ⚠️ Semantic Check Error: {e}. Assuming safe.")
        return False

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "models/gemini-2.5-flash")
    
    # 1. STRATEGY
    target_keyword = ""
    if forced_keyword:
        log(f"\n🔄 RETRY MODE: Trying fallback keyword in '{category}': '{forced_keyword}'")
        target_keyword = forced_keyword
    else:
        log(f"\n🚀 INIT PIPELINE: {category} (AI Strategist Mode)")
        recent_titles = get_recent_titles_string(category=category, limit=100)
        try:
            seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_titles)
            seo_plan = generate_step_strict(model_name, seo_prompt, "Step 0 (SEO Strategy)", required_keys=["target_keyword"])
            target_keyword = seo_plan.get('target_keyword')
            log(f"   🎯 Strategy Defined: Targeting '{target_keyword}'")
        except:
            log("   ⚠️ SEO Strategy failed. Returning False to trigger fallback.")
            return False

    # 2. SEMANTIC GUARD
    all_history = get_recent_titles_string(category=None, limit=200)
    if check_semantic_duplication(target_keyword, all_history):
        log("   🚫 ABORTING: This topic creates Keyword Cannibalization.")
        return False

    # 3. SOURCE HUNTING
    rss_query = f"{target_keyword} when:2d"
    rss_items = get_real_news_rss(rss_query.replace("when:2d","").strip(), category)
    if not rss_items:
        log(f"   ⚠️ No news found for '{target_keyword}'. Aborting.")
        return False

    collected_sources = []
    main_headline = ""
    main_link = ""
    required_terms = target_keyword.lower().split()
    significant_keyword = max(required_terms, key=len) if required_terms else ""
    log(f"   🕵️‍♂️ Investigating sources for: '{target_keyword}'...")

    for item in rss_items[:8]:
        if hasattr(sys.modules[__name__], 'BORING_KEYWORDS'):
             if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS): continue
        if significant_keyword and len(significant_keyword) > 3:
            if significant_keyword not in item['title'].lower():
                log(f"         ⚠️ Skipped Irrelevant: '{item['title']}'")
                continue
        if any(src['domain'] in item['link'] for src in collected_sources): continue

        data = url_resolver.get_page_html(item['link'])
        if data and data.get('html'):
            html_content = data['html']
            text = trafilatura.extract(html_content, include_comments=False, include_tables=True)
            if not text:
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style", "nav", "footer"]): script.extract()
                text = soup.get_text(" ", strip=True)
            og_image = extract_og_image(html_content)

            if text and len(text) >= 800:
                if significant_keyword and significant_keyword not in text.lower(): continue
                log(f"         ✅ Accepted Source! ({len(text)} chars).")
                collected_sources.append({
                    "title": item['title'],
                    "text": text,
                    "domain": urllib.parse.urlparse(data['url']).netloc,
                    "url": data['url'],
                    "date": item['date'],
                    "source_image": og_image
                })
                if not main_headline:
                    main_headline = item['title']
                    main_link = item['link']
                if len(collected_sources) >= 3: break
        time.sleep(1.5)

    if not collected_sources:
        log(f"   ❌ No valid sources found for '{target_keyword}'.")
        return False

    # 4. EXECUTION
    try:
        log(f"\n✍️ Synthesizing Content from {len(collected_sources)} sources...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"
        
        sources_list_formatted = [{"title": s['title'], "url": s['url']} for s in collected_sources]
        json_ctx = {"rss_headline": main_headline, "keyword_focus": target_keyword, "source_count": len(collected_sources), "date": str(datetime.date.today()), "style_guide": "Critical, First-Person, Beginner-Focused, Honest Review"}
        payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** RESEARCH DATA ***\n{combined_text}"
        
        json_b = generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)", required_keys=["headline", "hook", "article_body", "verdict"])
        # نستخرج العنوان المقترح من الخطوة B ونرسله لدالة الربط
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

        # Multimedia
        log("   🧠 Generating Multimedia Assets...")
        yt_meta = generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title", "description", "tags"])
        fb_dat = generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)
        
        log("   🖼️ Starting Intelligent Image Strategy...")
        candidate_images = []
        for src in collected_sources:
            if src.get('source_image'): candidate_images.append({'url': src['source_image'], 'domain': src['domain']})
        
        selected_source_image = None
        if candidate_images: selected_source_image = select_best_image_with_gemini(model_name, title, candidate_images)
        overlay_text_clean = img_overlay if img_overlay else "LATEST NEWS"
        
        img_url = None
        if selected_source_image:
            log(f"      🎯 Processing selected image...")
            img_url = process_source_image(selected_source_image, overlay_text_clean, title)
        if not img_url:
            log("      🎨 No suitable source image found. Generating Abstract AI Art...")
            safe_prompt = f"{img_prompt}, abstract technology, blurred background, no people, no skin, no faces, futuristic, 3d render"
            img_url = generate_and_upload_image(safe_prompt, overlay_text_clean)

        summ_clean = re.sub('<[^<]+?>','', content_html)[:2500]
        script_json = None
        for attempt in range(1, 4):
            log(f"      🎬 Generating Script (Attempt {attempt}/3)...")
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
            timestamp = int(time.time())
            base_output_dir = os.path.abspath("output")
            os.makedirs(base_output_dir, exist_ok=True)
            log(f"      🎬 Rendering Main Video...")
            try:
                rr = video_renderer.VideoRenderer(output_dir=base_output_dir, width=1920, height=1080)
                main_video_path = os.path.join(base_output_dir, f"main_{timestamp}.mp4")
                pm = rr.render_video(script_json, title, main_video_path)
                if pm and os.path.exists(pm):
                    desc = f"{yt_meta.get('description','')}\n\n🚀 Full Story: {main_link}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                    if vid_main: 
                        # JeTheme Optimized Video
                        vid_html = f'''
                        <div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
                            <iframe 
                                style="position:absolute;top:0;left:0;width:100%;height:100%;" 
                                src="https://www.youtube.com/embed/{vid_main}" 
                                frameborder="0" 
                                allowfullscreen 
                                loading="lazy"
                                width="1280" 
                                height="720"
                                title="{title}">
                            </iframe>
                        </div>
                        '''
            except Exception as e: log(f"      ⚠️ Main Video Error: {e}")

            log(f"      🎬 Rendering Short Video...")
            try:
                rs = video_renderer.VideoRenderer(output_dir=base_output_dir, width=1080, height=1920)
                short_video_path = os.path.join(base_output_dir, f"short_{timestamp}.mp4")
                ps = rs.render_video(script_json, title, short_video_path)
                if ps and os.path.exists(ps):
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
            except Exception as e: log(f"      ⚠️ Short Video Error: {e}")

        # Publishing
        log("   🚀 Publishing to Blogger...")
        author_box = """<div style="margin-top:40px; padding:25px; background:#f4f6f8; border-radius:12px; display:flex; align-items:center; border:1px solid #e1e4e8;"><img src="https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791" style="width:70px; height:70px; border-radius:50%; margin-right:15px; border:2px solid #fff; box-shadow:0 2px 5px rgba(0,0,0,0.1);" alt="Yousef Sameer"><div><h4 style="margin:0; font-size:18px; color:#2c3e50;">Yousef Sameer</h4><p style="margin:5px 0 0; font-size:14px; color:#666; line-height:1.4;">I test AI tools so you don't have to break your device. <br><strong>Brutally honest reviews. No fluff.</strong></p></div></div>"""
        
        content_html = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
        content_html = content_html.replace('href=""', 'href="').replace('"" target', '" target')
        content_html = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', content_html)
        
        # DEFINED THE MISSING VARIABLE
        final_content_with_author = content_html + author_box
        
        # JeTheme Optimized Image Block
        img_html = ""
        if img_url: 
            alt_text = seo_data.get("imageAltText", title)
            img_html = f'''
            <div class="separator" style="clear:both;text-align:center;margin-bottom:30px;">
                <a href="{img_url}" style="margin-left:1em; margin-right:1em;">
                    <img border="0" 
                         src="{img_url}" 
                         alt="{alt_text}" 
                         width="1200" 
                         height="630" 
                         fetchpriority="high" 
                         loading="eager" 
                         style="max-width:100%; height:auto; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" 
                         data-original-width="1200" 
                         data-original-height="630" />
                </a>
            </div>
            '''

        full_body = ARTICLE_STYLE + img_html + vid_html + final_content_with_author
        
        if 'schemaMarkup' in final:
            try: full_body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
            except: pass
        
        # -----------------------------------------------------------
        # 🛑 FINAL SAFETY CHECK (PRE-FLIGHT)
        # -----------------------------------------------------------
        log("   🛡️ Performing Final Semantic Check on Generated Title...")
        if check_semantic_duplication(title, all_history):
            log(f"   🚫 ABORTING PUBLISH: The generated title '{title}' is a duplicate of existing content!")
            return False 

        published_url = publish_post(title, full_body, [category, "Tech News", "Explainers"])
        
        if published_url:
            log(f"✅ PUBLISHED: {published_url}")
            update_kg(title, published_url, category)
            new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL ARTICLE HERE:\n{published_url}\n\n#AI #TechNews"
            if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
            if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
            try:
                log("   📢 Distributing to Facebook...")
                if fb_path and os.path.exists(fb_path): 
                    fb_text = f"{fb_cap}\n\nRead more: {published_url}\n\n#AI"
                    social_manager.post_reel_to_facebook(fb_path, fb_text)
                elif img_url:
                    social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{published_url}", published_url, img_url)
            except Exception as e: log(f"   ⚠️ Social Distribution Error: {e}")
            return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED during generation: {e}")
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
    log(f"🎲 Session Categories Priority: {all_categories}")
    
    success = False
    for category in all_categories:
        log(f"\n📁 SWITCHING TO CATEGORY: {category}")
        if run_pipeline(category, cfg, forced_keyword=None):
            success = True
            break 
        log(f"   ⚠️ AI Strategy failed for {category}. Switching to Manual List...")
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
        log("\n✅ MISSION ACCOMPLISHED. Article Published.")
        perform_maintenance_cleanup()
    else:
        log("\n❌ MISSION FAILED. Exhausted all categories and all keywords.")

if __name__ == "__main__":
    main()
