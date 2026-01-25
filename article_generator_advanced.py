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
import textwrap
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
# 0. DEFINITIONS & EXCEPTIONS (CRITICAL: MUST BE DEFINED FIRST)
# ==============================================================================

class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

# Advanced Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RetryEngine")

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils", "unveiled",
    "poised to", "delve into", "game-changer", "paradigm shift", "tapestry", "robust",
    "leverage", "underscore", "testament to", "beacon of", "In conclusion",
    "Remember that", "It is important to note", "Imagine a world", "fast-paced world",
    "cutting-edge", "realm of"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. SMART KEY & MODEL DISCOVERY ENGINE
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
        log("   ⚠️ All keys exhausted. Resetting Cycle for Model Switch...")
        self.current_index = 0
        return False

key_manager = KeyManager()

def discover_fresh_model(current_model_name):
    """Dynamically finds a working Gemini model from the API list."""
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
    except: pass

    # Professional Priority List
    priority_list = [
        "gemini-3-flash-preview", 
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro"
    ]
    
    final_choice = next((p for p in priority_list if p in candidates), None)
    if not final_choice and candidates: final_choice = candidates[0]
    
    if final_choice:
        log(f"   💡 New Model Selected: {final_choice}")
        CURRENT_MODEL_OVERRIDE = final_choice 
        return final_choice
    return None

# --- CORE AI GENERATOR (TENACITY POWERED) ---
@retry(
    stop=stop_after_attempt(15), 
    wait=wait_exponential(multiplier=2, min=5, max=30), 
    retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)), 
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    model_to_use = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else initial_model_name
    model_to_use = model_to_use.replace("models/", "") # Fix for 404 URL issues
    
    log(f"   🔄 [Tenacity] Executing: {step_name} | Model: {model_to_use}")
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    try:
        # Pre-emptive cooling for RPM safety
        time.sleep(random.uniform(4, 7)) 
        
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=STRICT_SYSTEM_PROMPT, 
            temperature=0.3
        )
        
        response = client.models.generate_content(model=model_to_use, contents=prompt, config=generation_config)
        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ JSON Broken. Repairing with AI...")
            time.sleep(3)
            repair_response = client.models.generate_content(
                model=model_to_use, 
                contents=f"Return ONLY pure valid JSON for this content:\n{response.text[:5000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_response.text)
            if not parsed_data: raise JSONParsingError(f"Failed to fix JSON for {step_name}")

        if required_keys: validate_structure(parsed_data, required_keys)
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        if any(x in error_msg for x in ["429", "quota", "exhausted", "403", "permission", "limit"]):
            log(f"      ⚠️ API Hit on Key #{key_manager.current_index + 1}. Rotating...")
            if not key_manager.switch_key():
                log(f"      🛑 All Keys Failed. Initiating Model Discovery...")
                time.sleep(20)
                discover_fresh_model(model_to_use)
            raise e 
        elif "404" in error_msg or "not found" in error_msg:
             discover_fresh_model(model_to_use)
             raise e
        else:
            raise e

# ==============================================================================
# 2. DATA UTILITIES (KG & JSON)
# ==============================================================================

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f: return json.load(f)
    except: pass
    return []

def update_kg(title, url, section):
    try:
        data = load_kg()
        if any(i['url'] == url for i in data): return
        data.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
        with open('knowledge_graph.json', 'w') as f: json.dump(data, f, indent=2)
    except: pass

def get_recent_titles_string(category=None, limit=100):
    kg = load_kg()
    if not kg: return ""
    titles = [f"- {i['title']}" for i in kg if (not category or i['section'] == category)][-limit:]
    return "\n".join(titles)

def perform_maintenance_cleanup():
    try:
        data = load_kg()
        if len(data) > 800:
            with open('knowledge_graph.json', 'w') as f: json.dump(data[-400:], f, indent=2)
    except: pass

def master_json_parser(text):
    if not text: return None
    match = regex.search(r'\{(?:[^{}]|(?R))*\}', text, regex.DOTALL)
    candidate = match.group(0) if match else text
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass
    return None

def validate_structure(data, required_keys):
    if not isinstance(data, dict): raise JSONValidationError("Response is not a JSON object")
    missing = [k for k in required_keys if k not in data]
    if missing: raise JSONValidationError(f"Missing keys: {missing}")
    return True

# ==============================================================================
# 3. PRO RESEARCH & SCRAPING ENGINE (EAGER STRATEGY)
# ==============================================================================

def resolve_and_scrape(google_url):
    """High-precision scraper with Eager strategy to prevent Timeouts."""
    log(f"      🕵️‍♂️ Scraper: {google_url[:50]}...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.page_load_strategy = 'eager' # Fast loading bypasses trackers/heavy ads
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25)
        driver.get(google_url)
        time.sleep(2) # Wait for redirect
        
        extracted_text = trafilatura.extract(driver.page_source, include_comments=False, include_tables=True)
        if not extracted_text:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            for s in soup(["script", "style", "nav", "footer", "header", "aside"]): s.extract()
            extracted_text = soup.get_text(" ", strip=True)

        if len(extracted_text) < 600: return None, None, None
        return driver.current_url, driver.title, extracted_text
    except Exception as e:
        log(f"      ❌ Selenium Error: {str(e)[:50]}")
        return None, None, None
    finally:
        if driver: driver.quit()

def get_pro_news(query, category):
    """Hybrid search: GNews API + Google News RSS."""
    log(f"   📡 Deep Research: '{query}'")
    items = []
    # GNews API
    api_key = os.getenv('GNEWS_API_KEY')
    if api_key:
        try:
            url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(query)}&lang=en&country=us&max=5&apikey={api_key}"
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                for a in r.json().get('articles', []):
                    items.append({"title": a['title'], "link": a['url'], "date": a['publishedAt'], "image": a.get('image')})
        except: pass
    # RSS Fallback
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}+when:2d&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for e in feed.entries[:8]:
            items.append({"title": e.title.split(' - ')[0], "link": e.link, "date": getattr(e, 'published', 'Today')})
    except: pass
    
    # Deduplicate
    unique = []
    for it in items:
        if not any(difflib.SequenceMatcher(None, it['title'].lower(), u['title'].lower()).ratio() > 0.85 for u in unique):
            unique.append(it)
    return unique

# ==============================================================================
# 4. MULTIMEDIA PROCESSING (VISION & BLUR)
# ==============================================================================

def select_best_image_with_gemini(model_name, article_title, images_list):
    if not images_list: return None
    log("   🤖 AI Vision: Selecting most relevant image...")
    valid = []
    for img in images_list[:4]:
        try:
            r = requests.get(img['url'], timeout=10, headers={'User-Agent': random.choice(USER_AGENTS)})
            if r.status_code == 200: valid.append({"mime_type": "image/jpeg", "data": r.content, "url": img['url']})
        except: pass
    if not valid: return None

    # Try Vision support in sequence
    vision_models = ["gemini-3-flash-preview", "gemini-1.5-flash", "gemini-2.0-flash-exp"]
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    prompt = f"TASK: Return ONLY the integer index (0-{len(valid)-1}) of the image that best represents this tech news: '{article_title}'."
    inputs = [prompt] + [types.Part.from_bytes(data=i['data'], mime_type="image/jpeg") for i in valid]

    for v_model in vision_models:
        try:
            resp = client.models.generate_content(model=v_model, contents=inputs)
            match = re.search(r'\d+', resp.text)
            if match:
                idx = int(match.group())
                if 0 <= idx < len(valid): return valid[idx]['url']
        except: continue
    return valid[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    if not source_url or source_url.startswith('/'): return None
    log(f"   🖼️ Processing Original Asset: {source_url[:50]}")
    try:
        r = requests.get(source_url, timeout=15, stream=True, headers={'User-Agent': random.choice(USER_AGENTS)})
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        target_w, target_h = 1200, 630
        
        # Resizing and Cropping
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_w = int(target_h * img_ratio)
            img = img.resize((new_w, target_h), Image.Resampling.LANCZOS)
            img = img.crop(((new_w - target_w)/2, 0, (new_w + target_w)/2, target_h))
        else:
            new_h = int(target_w / img_ratio)
            img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            img = img.crop((0, (new_h - target_h)/2, target_w, (new_h + target_h)/2))
        
        # Privacy Nuclear Blur (OpenCV)
        img_np = np.array(img.convert("RGB"))
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY), 1.1, 4)
        for (x, y, w, h) in faces:
            roi = img_np[y:y+h, x:x+w]
            img_np[y:y+h, x:x+w] = cv2.GaussianBlur(roi, (99, 99), 35)
        
        img_final = Image.fromarray(img_np).convert("RGBA")
        overlay = Image.new('RGBA', img_final.size, (0, 0, 0, 115))
        img_final = Image.alpha_composite(img_final, overlay)
        draw = ImageDraw.Draw(img_final)
        
        try: font = ImageFont.truetype("arialbd.ttf", 85)
        except: font = ImageFont.load_default()
        
        wrapped_lines = textwrap.wrap(overlay_text.upper(), width=18)
        y_text = 315 - (len(wrapped_lines) * 45)
        
        for line in wrapped_lines:
            w_l = draw.textbbox((0,0), line, font=font)[2]
            draw.text(((1200-w_l)/2, y_text), line, font=font, fill="#FFD700", stroke_width=2, stroke_fill="black")
            y_text += 105

        byte_arr = BytesIO()
        img_final.convert("RGB").save(byte_arr, format='WEBP', quality=85)
        safe_name = re.sub(r'\W+', '-', filename_title).lower()[:50] + ".webp"
        return upload_to_github_cdn(byte_arr, safe_name)
    except: return None

def upload_to_github_cdn(bytes_io, filename):
    try:
        token = os.getenv('MY_GITHUB_TOKEN')
        repo_name = "ysrg2003/latest-ai-assets"
        g = Github(token)
        repo = g.get_repo(repo_name)
        path = f"images/{datetime.datetime.now().strftime('%Y-%m')}/{filename}"
        repo.create_file(path=path, message="Auto-Upload Asset", content=bytes_io.getvalue(), branch="main")
        return f"https://cdn.jsdelivr.net/gh/{repo_name}@main/{path}"
    except: return None

def generate_and_upload_image(prompt, overlay):
    log("   🎨 Flux AI: Generating High-End Fallback Image...")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt + ', masterpiece, 8k, tech')}?width=1280&height=720&model=flux&nologo=true"
    try:
        r = requests.get(url, timeout=60)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        byte_arr = BytesIO()
        img.save(byte_arr, format='WEBP', quality=85)
        return upload_to_github_cdn(byte_arr, f"ai_gen_{int(time.time())}.webp")
    except: return None

def get_relevant_kg_for_linking(current_title, current_category):
    kg = load_kg()
    if not kg: return "[]"
    same_cat = [i for i in kg if i.get('section') == current_category]
    other_cat = [i for i in kg if i.get('section') != current_category]
    relevant_others = []
    kw = set(current_title.lower().split())
    for item in other_cat:
        if len(kw.intersection(set(item['title'].lower().split()))) >= 2:
            relevant_others.append(item)
    final = same_cat[:4] + relevant_others[:2] 
    return json.dumps([{"title": i['title'], "url": i['url']} for i in final])

# ==============================================================================
# 5. CORE PIPELINE (THE PRODUCTION CHAIN)
# ==============================================================================

def check_semantic_duplication(target, history):
    if not history: return False
    # 1. Local Fuzzy Logic
    for line in history.split('\n'):
        if difflib.SequenceMatcher(None, target.lower(), line.lower()).ratio() > 0.85:
            log(f"      ⛔ Match Found (Local): {line}")
            return True
    # 2. AI Semantic Check
    judge_model = CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else "gemini-3-flash-preview"
    prompt = f"TASK: Deduplication. Is this new topic COVERED in past history?\nNEW: {target}\nPAST:\n{history}\nOutput JSON: {{'is_duplicate': true/false}}"
    try:
        res = generate_step_strict(judge_model, prompt, "Judge", ["is_duplicate"])
        return res.get('is_duplicate', False)
    except: return False

# ==============================================================================
# BLOGGER PUBLISHING ENGINE
# ==============================================================================

def get_blogger_token():
    """Generates a fresh access token for Blogger API."""
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    try:
        r = requests.post('https://oauth2.googleapis.com/token', data=payload, timeout=10)
        return r.json().get('access_token') if r.status_code == 200 else None
    except:
        return None

def publish_post(title, content, labels):
    """Publishes the final article to Blogger."""
    token = get_blogger_token()
    if not token:
        log("❌ Could not generate Blogger Token.")
        return None
        
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts?isDraft=false"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels}
    
    try:
        r = requests.post(url, headers=headers, json=body, timeout=20)
        if r.status_code == 200:
            post_url = r.json().get('url')
            log(f"✅ Published LIVE: {post_url}")
            return post_url
        else:
            log(f"❌ Blogger API Error: {r.text}")
            return None
    except Exception as e:
        log(f"❌ Connection Fail during publishing: {e}")
        return None

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
    # 1. STRATEGY
    target_keyword, is_manual = "", False
    if forced_keyword:
        target_keyword, is_manual = forced_keyword, True
        log(f"\n🔄 RETRY MODE: Forced Target '{target_keyword}'")
    else:
        log(f"\n🚀 INIT PIPELINE: {category}")
        history = get_recent_titles_string(category=category, limit=100)
        plan = generate_step_strict(model_name, PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=history), "SEO Strategy", ["target_keyword"])
        target_keyword = plan['target_keyword']

    # 2. SEMANTIC GUARD
    lookback = 7 if is_manual else 60
    kg_data = load_kg()
    cutoff = datetime.date.today() - datetime.timedelta(days=lookback)
    history_str = "\n".join([f"- {i['title']}" for i in kg_data if datetime.datetime.strptime(i['date'], "%Y-%m-%d").date() >= cutoff])
    if check_semantic_duplication(target_keyword, history_str): return False

    # 3. PRO RESEARCH
    candidates = get_pro_news(target_keyword, category)
    collected = []
    main_link = ""
    for item in candidates:
        f_url, f_title, f_text = resolve_and_scrape(item['link'])
        if f_text:
            log(f"      ✅ Source Accepted: {urllib.parse.urlparse(f_url).netloc}")
            collected.append({"title": f_title, "text": f_text, "url": f_url, "date": item['date'], "source_image": item.get('image')})
            if not main_link: main_link = f_url
            if len(collected) >= 3: break
    if len(collected) < 2: return False

    # 4. CONTENT SYNTHESIS
    reddit_ctx = reddit_manager.get_community_intel(target_keyword)
    research_text = "".join([f"\n--- S{i+1} ---\n{s['text'][:8500]}\n" for i, s in enumerate(collected)])
    payload = f"TOPIC: {target_keyword}\nSOCIAL: {reddit_ctx}\n\nRESEARCH:\n{research_text}"
    
    try:
        # Synthesis Chain
        json_b = generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Critic)", ["headline", "article_body"])
        links = get_relevant_kg_for_linking(json_b['headline'], category)
        json_c = generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft": json_b, "sources": collected}), knowledge_graph=links), "Step C (SEO)", ["finalContent"])
        json_d = generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D (Human)", ["finalContent"])
        final = generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps({**json_c, **json_d})), "Step E (Polish)", ["finalTitle", "finalContent", "seo", "imageGenPrompt"])

        # 5. ASSETS & VIDEO
        yt_meta = generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=final['finalTitle']), "YT", ["title", "description"])
        fb_hook = generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=final['finalTitle']), "FB", ["FB_Hook"])
        
        # Image
        c_imgs = [{"url": s['source_image']} for s in collected if s.get('source_image')]
        best_img = select_best_image_with_gemini(model_name, final['finalTitle'], c_imgs)
        img_cdn = process_source_image(best_img, final.get('imageOverlayText', 'LATEST'), final['finalTitle'])
        if not img_cdn: img_cdn = generate_and_upload_image(final['imageGenPrompt'], "AI NEWS")

        # Video Rendering
        summ = re.sub('<[^<]+?>','', final['finalContent'])[:2000]
        script = generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=final['finalTitle'], text_summary=summ), "Script", ["video_script"])['video_script']
        
        out_dir, ts = os.path.abspath("output"), int(time.time())
        os.makedirs(out_dir, exist_ok=True)
        vid_html, fb_path, vid_id = "", None, None
        
        try:
            rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
            pm = rr.render_video(script, final['finalTitle'], f"main_{ts}.mp4")
            if pm:
                vid_id, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta['title'], f"{yt_meta['description']}\n\nFull: {main_link}", ["AI"])
                if vid_id: vid_html = f'<div class="video-container" style="margin:30px 0;"><iframe src="https://www.youtube.com/embed/{vid_id}" frameborder="0" allowfullscreen style="width:100%; height:450px; border-radius:12px;"></iframe></div>'
        except: pass

        # 6. SELF-HEALING & PUBLISH
        val_client = genai.Client(api_key=key_manager.get_current_key())
        final_html = content_validator_pro.AdvancedContentValidator(val_client).run_professional_validation(final['finalContent'], research_text, collected)

        # High-End Author Box
        author_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
                    <div style="display:flex; gap:14px; flex-wrap:wrap;">
                        <a href="https://www.facebook.com/share/1AkVHBNbV1/" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="26"></a>
                        <a href="https://x.com/latestaime" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="26"></a>
                        <a href="https://www.instagram.com/latestai.me" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="26"></a>
                        <a href="https://m.youtube.com/@0latestai" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="26"></a>
                        <a href="https://pinterest.com/latestaime" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/145/145808.png" width="26"></a>
                        <a href="https://reddit.com/user/Yousefsg/" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="26"></a>
                    </div>
                </div>
            </div>
        </div>"""
        
        img_block = f'<div style="text-align:center; margin-bottom:35px;"><img src="{img_cdn}" style="max-width:100%; border-radius:15px; box-shadow:0 8px 20px rgba(0,0,0,0.15);"></div>'
        full_body = img_block + vid_html + final_html + author_box
        
        # Publish
        published_url = publish_post(final['finalTitle'], full_body, [category, "Tech News"])
        if published_url:
            update_kg(final['finalTitle'], published_url, category)
            if vid_id: youtube_manager.update_video_description(vid_id, f"Full Article: {published_url}\n\n{yt_meta['description']}")
            log(f"✅ SUCCESS: {published_url}")
            return True
    except Exception as e:
        log(f"❌ SYNTHESIS CRASH: {e}")
    return False

# ==============================================================================
# 6. SYSTEM ENTRY POINT
# ==============================================================================

def main():
    try: cfg = json.load(open('config_advanced.json', 'r'))
    except: return log("❌ Config Missing.")
    
    categories = list(cfg['categories'].keys())
    random.shuffle(categories)
    
    published_today = False
    for cat in categories:
        log(f"\n📂 FOLDER: {cat}")
        if run_pipeline(cat, cfg):
            published_today = True; break
            
        # Try Manual Fallback
        manual_topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
        random.shuffle(manual_topics)
        for topic in manual_topics:
            if run_pipeline(cat, cfg, forced_keyword=topic):
                published_today = True; break
        if published_today: break

    if published_today: perform_maintenance_cleanup()
    else: log("❌ SESSION ENDED: No articles published.")

if __name__ == "__main__":
    main()
