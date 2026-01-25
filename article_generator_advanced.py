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
# 0. GLOBAL CONFIGURATION & ANTI-BOT SETTINGS
# ==============================================================================

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils", "unveiled",
    "poised to", "delve into", "game-changer", "paradigm shift", "tapestry", "robust",
    "leverage", "underscore", "testament to", "beacon of", "In conclusion",
    "Remember that", "It is important to note", "Imagine a world", "fast-paced world",
    "cutting-edge", "realm of"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1.2 Mobile/15E148 Safari/604.1"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. SMART KEY & MODEL MANAGEMENT (THE ENGINE)
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
        log("   ⚠️ All keys exhausted. Resetting Cycle for Discovery...")
        self.current_index = 0
        return False

key_manager = KeyManager()

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

    priority_list = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
    
    final_choice = next((p for p in priority_list if p in candidates), None)
    if not final_choice and candidates: final_choice = candidates[0]
    if not final_choice:
        for p in priority_list:
            if p not in TRIED_MODELS:
                final_choice = p
                break
                
    if final_choice:
        log(f"   💡 New Model Selected: {final_choice}")
        CURRENT_MODEL_OVERRIDE = final_choice 
        return final_choice
    return None

# --- THE ULTIMATE HYBRID AI GENERATOR ---
@retry(
    stop=stop_after_attempt(15), 
    wait=wait_exponential(multiplier=2, min=5, max=35), 
    retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)), 
    before_sleep=before_sleep_log(logging.getLogger("RetryEngine"), logging.WARNING)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    model_to_use = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else initial_model_name
    model_to_use = model_to_use.replace("models/", "") # Anti-404 Fix
    
    log(f"   🔄 [Tenacity] Executing: {step_name} | Model: {model_to_use}")
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    try:
        time.sleep(random.uniform(3, 6)) # Jitter to prevent concurrent hit 429
        
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=STRICT_SYSTEM_PROMPT, 
            temperature=0.3
        )
        
        response = client.models.generate_content(model=model_to_use, contents=prompt, config=generation_config)
        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ Parsing failed. Triggering AI-Repair...")
            time.sleep(3)
            repair_response = client.models.generate_content(
                model=model_to_use, 
                contents=f"Fix this invalid JSON and return ONLY the corrected JSON:\n{response.text[:6000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_response.text)
            if not parsed_data: raise JSONParsingError(f"Critical JSON Failure on {step_name}")

        if required_keys: validate_structure(parsed_data, required_keys)
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        # Handle 429 (Quota), 403 (Permission), 404 (Not Found)
        if any(x in error_msg for x in ["429", "quota", "exhausted", "403", "permission", "limit"]):
            log(f"      ⚠️ API Hit ({error_msg[:20]}) on Key #{key_manager.current_index + 1}.")
            if not key_manager.switch_key():
                log(f"      ⛔ Model Cycle Exhausted. Finding new model...")
                time.sleep(25)
                if not discover_fresh_model(model_to_use): raise RuntimeError("TOTAL COLLAPSE: No models left.")
            raise e 
        elif "404" in error_msg or "not found" in error_msg:
             discover_fresh_model(model_to_use)
             raise e
        else:
            log(f"      ❌ Unhandled Error: {str(e)[:100]}")
            raise e

# ==============================================================================
# 2. JSON & STRUCTURE HELPERS
# ==============================================================================

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
    if not isinstance(data, dict): raise JSONValidationError("Output is not a dictionary.")
    missing = [k for k in required_keys if k not in data]
    if missing: raise JSONValidationError(f"Missing required JSON keys: {missing}")
    return True

# ==============================================================================
# 3. RESEARCH ENGINE (GNEWS + RSS + PRO SCRAPER)
# ==============================================================================

def get_pro_news(query_keywords, category):
    """Combines GNews API and RSS for maximum recall."""
    log(f"   📡 Starting Deep Research for: '{query_keywords}'...")
    all_items = []
    
    # 1. GNews API (High Quality)
    api_key = os.getenv('GNEWS_API_KEY')
    if api_key:
        url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(query_keywords)}&lang=en&country=us&max=5&apikey={api_key}"
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                for art in r.json().get('articles', []):
                    all_items.append({"title": art['title'], "link": art['url'], "date": art['publishedAt'], "image": art.get('image')})
        except: pass

    # 2. RSS Fallback (Reliable)
    try:
        fb_query = urllib.parse.quote(f"{query_keywords} when:2d")
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={fb_query}&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:10]:
            all_items.append({"title": entry.title.split(' - ')[0], "link": entry.link, "date": getattr(entry, 'published', 'Today')})
    except: pass

    # Deduplicate by title similarity
    unique_items = []
    for item in all_items:
        if not any(difflib.SequenceMatcher(None, item['title'].lower(), u['title'].lower()).ratio() > 0.85 for u in unique_items):
            unique_items.append(item)
            
    return unique_items

def resolve_and_scrape(google_url):
    """Robust Selenium Scraper with Eager loading and Anti-Detection."""
    log(f"      🕵️‍♂️ Pro Scraper: {google_url[:50]}...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") # Speed
    chrome_options.page_load_strategy = 'eager' # Don't wait for heavy JS/Ads
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25)
        
        driver.get(google_url)
        # Wait for potential redirects
        time.sleep(2)
        final_url = driver.current_url
        page_source = driver.page_source
        
        extracted_text = trafilatura.extract(page_source, include_comments=False, include_tables=True)
        if not extracted_text or len(extracted_text) < 500:
            soup = BeautifulSoup(page_source, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]): tag.extract()
            extracted_text = soup.get_text(" ", strip=True)

        if len(extracted_text) < 600: return None, None, None
        return final_url, driver.title, extracted_text

    except Exception as e:
        log(f"      ❌ Selenium Failed: {str(e)[:60]}")
        return None, None, None
    finally:
        if driver: driver.quit()

# ==============================================================================
# 4. MULTIMEDIA & IMAGE PROCESSING
# ==============================================================================

def select_best_image_with_gemini(model_name, article_title, images_list):
    if not images_list: return None
    log(f"   🤖 AI Vision: Selecting best candidate image...")
    valid_images = []
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for img_data in images_list[:4]: 
        try:
            r = requests.get(img_data['url'], headers=headers, timeout=10)
            if r.status_code == 200:
                valid_images.append({"mime_type": "image/jpeg", "data": r.content, "url": img_data['url']})
        except: pass

    if not valid_images: return None
    prompt = f"TASK: Return the integer index (0-{len(valid_images)-1}) of the image most relevant to the tech news: '{article_title}'. Return ONLY the number."
    
    # Try multiple models for vision support
    vision_models = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash"]
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    inputs = [prompt]
    for img in valid_images: inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))

    for v_model in vision_models:
        try:
            resp = client.models.generate_content(model=v_model, contents=inputs)
            match = re.search(r'\d+', resp.text)
            if match:
                idx = int(match.group())
                if 0 <= idx < len(valid_images): return valid_images[idx]['url']
        except: continue
    return valid_images[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    if not source_url or source_url.startswith('/'): return None
    log(f"   🖼️ Refining Source Image: {source_url[:50]}...")
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        # Crop & Resize for Blogger (1200x630)
        target_w, target_h = 1200, 630
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_w = int(target_h * img_ratio)
            img = img.resize((new_w, target_h), Image.Resampling.LANCZOS)
            left = (new_w - target_w) / 2
            img = img.crop((left, 0, left + target_w, target_h))
        else:
            new_h = int(target_w / img_ratio)
            img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - target_h) / 2
            img = img.crop((0, top, target_w, top + target_h))
        
        # Privacy & Styling
        img_rgb = img.convert("RGB")
        try:
            # Face Detection Check
            cascade_path = "haarcascade_frontalface_default.xml"
            if not os.path.exists(cascade_path):
                r_cas = requests.get("https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml")
                with open(cascade_path, 'wb') as f: f.write(r_cas.content)
            
            img_np = np.array(img_rgb)
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            for (x, y, w, h) in faces:
                roi = img_np[y:y+h, x:x+w]
                img_np[y:y+h, x:x+w] = cv2.GaussianBlur(roi, (99, 99), 30)
            img_rgb = Image.fromarray(img_np)
        except: pass

        # Dark Overlay + Text
        overlay = Image.new('RGBA', img_rgb.size, (0, 0, 0, 100))
        img_final = Image.alpha_composite(img_rgb.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img_final)
        
        try: font = ImageFont.truetype("arialbd.ttf", 85)
        except: font = ImageFont.load_default()
        
        words = overlay_text.upper().split()
        lines, cur_line = [], ""
        for w in words:
            if draw.textbbox((0,0), cur_line + w, font=font)[2] < 1100: cur_line += w + " "
            else: lines.append(cur_line.strip()); cur_line = w + " "
        lines.append(cur_line.strip())
        
        y_text = 315 - (len(lines) * 45)
        for line in lines:
            w_l = draw.textbbox((0,0), line, font=font)[2]
            draw.text(((1200-w_l)/2, y_text), line, font=font, fill="#FFD700")
            y_text += 100

        byte_arr = BytesIO()
        img_final.convert("RGB").save(byte_arr, format='WEBP', quality=85)
        safe_name = re.sub(r'\W+', '-', filename_title).lower()[:50] + ".webp"
        return upload_to_github_cdn(byte_arr, safe_name)
    except Exception as e:
        log(f"      ⚠️ Image Refine Error: {e}")
        return None

def generate_and_upload_image(prompt, overlay):
    log(f"   🎨 Generating AI Artwork (Fallback Mode)...")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt + ', cinematic tech, 8k')}?width=1280&height=720&model=flux&seed={random.randint(1,999)}&nologo=true"
    try:
        r = requests.get(url, timeout=60)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        byte_arr = BytesIO()
        img.convert("RGB").save(byte_arr, format='WEBP', quality=85)
        return upload_to_github_cdn(byte_arr, f"ai_gen_{int(time.time())}.webp")
    except: return None

def upload_to_github_cdn(bytes_io, filename):
    try:
        token = os.getenv('MY_GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_IMAGE_REPO') or os.getenv('GITHUB_REPO_NAME')
        if not token or not repo_name: return None
        g = Github(token)
        repo = g.get_repo(repo_name)
        path = f"images/{datetime.datetime.now().strftime('%Y-%m')}/{filename}"
        repo.create_file(path=path, message=f"Robot Upload: {filename}", content=bytes_io.getvalue(), branch="main")
        return f"https://cdn.jsdelivr.net/gh/{repo_name}@main/{path}"
    except: return None

# ==============================================================================
# 5. CORE PIPELINE (THE PRODUCTION LINE)
# ==============================================================================

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
    # 1. SEO STRATEGY
    target_keyword, is_manual = "", False
    if forced_keyword:
        target_keyword, is_manual = forced_keyword, True
        log(f"\n🔄 MANUAL MODE: Targetting '{target_keyword}' in {category}")
    else:
        log(f"\n🚀 INIT PIPELINE: {category}")
        history = get_recent_titles_string(category=category, limit=100)
        plan = generate_step_strict(model_name, PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=history), "SEO Strategy", ["target_keyword"])
        target_keyword = plan['target_keyword']

    # 2. SEMANTIC GUARD (DEDUP)
    # Logic: 7 days lookback for manual, 60 days for AI.
    lookback = 7 if is_manual else 60
    kg_data = load_kg()
    cutoff = datetime.date.today() - datetime.timedelta(days=lookback)
    recent_history = "\n".join([f"- {i['title']}" for i in kg_data if datetime.datetime.strptime(i['date'], "%Y-%m-%d").date() >= cutoff])
    
    if check_semantic_duplication(target_keyword, recent_history):
        log(f"   🚫 Aborting: '{target_keyword}' covered in last {lookback} days.")
        return False

    # 3. SOURCE HUNTING (Deep Research)
    candidates = get_pro_news(target_keyword, category)
    collected = []
    main_link = ""

    for item in candidates:
        f_url, f_title, f_text = resolve_and_scrape(item['link'])
        if f_text:
            log(f"      ✅ Accepted: {urllib.parse.urlparse(f_url).netloc} ({len(f_text)} chars)")
            collected.append({"title": f_title, "text": f_text, "url": f_url, "date": item['date'], "source_image": item.get('image')})
            if not main_link: main_link = f_url
            if len(collected) >= 3: break # Minimum 3 sources for depth
        time.sleep(1)

    if len(collected) < 2:
        log(f"   ❌ Failed to find enough high-quality sources for '{target_keyword}'.")
        return False

    # 4. SYNTHESIS (THE CONTENT ENGINE)
    reddit_ctx = reddit_manager.get_community_intel(target_keyword)
    research_text = "".join([f"\n--- SOURCE {i+1} ---\n{s['text'][:9000]}\n" for i, s in enumerate(collected)])
    payload = f"METADATA: {json.dumps({'keyword': target_keyword})}\nFEEDBACK: {reddit_ctx}\n\nRESEARCH DATA:\n{research_text}"
    
    try:
        # Generation Chain
        json_b = generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)", ["headline", "hook", "article_body", "verdict"])
        kg_links = get_relevant_kg_for_linking(json_b['headline'], category)
        json_c = generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft": json_b, "sources": collected}), knowledge_graph=kg_links), "Step C (SEO)", ["finalTitle", "finalContent", "seo", "imageGenPrompt"])
        json_d = generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D (Humanizer)", ["finalContent"])
        final = generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps({**json_c, **json_d})), "Step E (Polish)", ["finalTitle", "finalContent", "seo", "imageGenPrompt"])

        title = final['finalTitle']
        content_html = final['finalContent']
        
        # 5. ASSETS (IMAGE & VIDEO)
        log("   🎬 Rendering Assets...")
        yt_meta = generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", ["title", "description"])
        fb_dat = generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
        
        # Image
        candidate_imgs = [{"url": s['source_image']} for s in collected if s.get('source_image')]
        best_img_url = select_best_image_with_gemini(model_name, title, candidate_imgs)
        overlay_txt = final.get('imageOverlayText', "LATEST TECH")
        img_cdn = None
        if best_img_url: img_cdn = process_source_image(best_img_url, overlay_txt, title)
        if not img_cdn: img_cdn = generate_and_upload_image(final['imageGenPrompt'], overlay_txt)

        # Video
        summ_clean = re.sub('<[^<]+?>','', content_html)[:2000]
        script = generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ_clean), "Script", ["video_script"])['video_script']
        
        out_dir = os.path.abspath("output")
        os.makedirs(out_dir, exist_ok=True)
        ts = int(time.time())
        vid_html, fb_path, vid_main_id, vid_short_id = "", None, None, None
        
        # Horizontal Video
        try:
            rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
            pm = rr.render_video(script, title, f"main_{ts}.mp4")
            if pm:
                vid_main_id, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta['title'], f"{yt_meta['description']}\n\nFull: {main_link}", yt_meta.get('tags', ["AI"]))
                if vid_main_id: vid_html = f'<div class="video-container"><iframe src="https://www.youtube.com/embed/{vid_main_id}" frameborder="0" allowfullscreen></iframe></div>'
        except: pass

        # Vertical Short
        try:
            rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
            ps = rs.render_video(script, title, f"short_{ts}.mp4")
            if ps:
                fb_path = ps
                vid_short_id, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta['title'][:90]} #Shorts", "Full story in link! #AI", ["shorts"])
        except: pass

        # 6. SELF-HEALING & PUBLISH
        log("   🛡️ Final Self-Healing Check...")
        val_client = genai.Client(api_key=key_manager.get_current_key())
        healer = content_validator_pro.AdvancedContentValidator(val_client)
        final_html_validated = healer.run_professional_validation(content_html, research_text, collected)

        author_box = """
        <div style="margin-top:50px; padding:25px; background:#f8f9fa; border-left: 5px solid #2ecc71; border-radius:8px; font-family:sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:20px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791" 
                     style="width:80px; height:80px; border-radius:50%; object-fit:cover; border:3px solid #fff;" alt="Latest AI">
                <div style="flex:1;">
                    <h4 style="margin:0 0 5px; font-size:20px; color:#2c3e50; font-weight:700;">Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:3px 8px; border-radius:4px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:12px 0; font-size:15px; color:#555;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
                    <div style="display:flex; gap:12px; flex-wrap:wrap;">
                        <a href="https://www.facebook.com/share/1AkVHBNbV1/" target="_blank" title="FB"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="24"></a>
                        <a href="https://x.com/latestaime" target="_blank" title="X"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24"></a>
                        <a href="https://www.instagram.com/latestai.me" target="_blank" title="IG"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="24"></a>
                        <a href="https://m.youtube.com/@0latestai" target="_blank" title="YT"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24"></a>
                        <a href="https://reddit.com/user/Yousefsg/" target="_blank" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24"></a>
                    </div>
                </div>
            </div>
        </div>"""
        
        img_tag = f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><img src="{img_cdn}" style="max-width:100%; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);"></div>'
        full_body = img_tag + vid_html + final_html_validated + author_box
        
        # Publish to Blogger
        published_url = publish_post(title, full_body, [category, "Tech News"])
        if published_url:
            update_kg(title, published_url, category)
            # Update Socials with the URL
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, f"Full Article: {published_url}\n\n{yt_meta['description']}")
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, f"Read Full Breakdown: {published_url}")
            if fb_path: social_manager.post_reel_to_facebook(fb_path, f"{fb_dat['FB_Hook']}\n\nLink: {published_url}")
            log(f"✅ PROCESS COMPLETE: {published_url}")
            return True
        return False
    except Exception as e:
        log(f"❌ Synthesis/Publishing Failed: {e}")
        return False

# ==============================================================================
# 6. SYSTEM UTILITIES (HISTORY & KG)
# ==============================================================================

def check_semantic_duplication(new_keyword, history_string):
    if not history_string or len(history_string) < 10: return False
    # Local Check (Zero Cost)
    target = new_keyword.lower().strip()
    existing = [line.replace("- ", "").strip().lower() for line in history_string.split('\n') if line.strip()]
    for title in existing:
        if difflib.SequenceMatcher(None, target, title).ratio() > 0.85: return True
    # AI Confirmation
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    prompt = f"TASK: Duplicate Check. NEW: {new_keyword}. PAST: {history_string}. Output JSON: {{'is_duplicate': true/false}}"
    try:
        res = generate_step_strict(judge_model, prompt, "Judge", ["is_duplicate"])
        return res['is_duplicate']
    except: return False

def main():
    try: cfg = json.load(open('config_advanced.json','r'))
    except: return log("❌ Config Missing.")
    
    categories = list(cfg['categories'].keys())
    random.shuffle(categories)
    
    success = False
    for cat in categories:
        log(f"\n📁 FOLDER: {cat}")
        if run_pipeline(cat, cfg):
            success = True; break
            
        log(f"   ⚠️ AI Strategy yielded no article. Attempting Manual Topics...")
        manual_topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
        random.shuffle(manual_topics)
        for topic in manual_topics:
            if run_pipeline(cat, cfg, forced_keyword=topic):
                success = True; break
        if success: break

    if success: perform_maintenance_cleanup()
    else: log("❌ SESSION FAILED: No articles could be produced.")

if __name__ == "__main__":
    main()
