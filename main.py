# FILE: main.py
# ROLE: Orchestrator V15.0 (The Absolute Unit)
# DESCRIPTION: Full integration of Selenium-First Search, Tenacity AI Engine, 
#              Multimedia Production, and Multi-Platform Publishing.
#              NO SHORTCUTS. NO SIMPLIFICATIONS.

import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import logging
import traceback
import ast

# --- External Libraries ---
import feedparser
from bs4 import BeautifulSoup
import trafilatura
import json_repair
import regex
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type, 
    before_sleep_log
)
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from google import genai
from google.genai import types

# --- Selenium & Webdriver ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- Project Modules ---
import config
from config import log
import video_renderer
import social_manager
import youtube_manager
import publisher
import news_fetcher
import ai_researcher
import reddit_manager
from prompts import *

# ==============================================================================
# 0. CONFIGURATION & CONSTANTS
# ==============================================================================

# Logger for Tenacity
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils", "unveiled",
    "poised to", "delve into", "game-changer", "paradigm shift", "tapestry", "robust",
    "leverage", "underscore", "testament to", "beacon of", "In conclusion",
    "Remember that", "It is important to note", "Imagine a world", "fast-paced world",
    "cutting-edge", "realm of"
]

BORING_KEYWORDS = [
    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
]

# Full CSS Style (Unabridged)
ARTICLE_STYLE = """
<style>
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #333; font-size: 18px; max-width: 100%; overflow-x: hidden; }
    h2 { color: #111; font-weight: 800; margin-top: 60px; margin-bottom: 25px; border-bottom: 3px solid #f1c40f; padding-bottom: 10px; font-size: 28px; clear: both; display: block; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 40px; margin-bottom: 20px; font-size: 24px; clear: both; }
    .toc-box { background: #fdfdfd; border: 1px solid #e1e4e8; padding: 25px; margin: 30px 0 50px 0; border-radius: 12px; display: block; width: 100%; box-sizing: border-box; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .toc-box h3 { margin-top: 0; font-size: 22px; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; color: #2c3e50; display: inline-block; }
    .toc-box ul { list-style: none !important; padding: 0 !important; margin: 0 !important; }
    .toc-box li { margin-bottom: 12px; border-bottom: 1px dashed #eee; padding-bottom: 8px; padding-left: 0; position: relative; }
    .toc-box a { color: #444; font-weight: 600; font-size: 18px; text-decoration: none; transition: 0.2s; display: flex; align-items: center; border: none; }
    .toc-box a:before { content: "👉"; margin-right: 10px; font-size: 16px; }
    .toc-box a:hover { color: #3498db; padding-left: 5px; background: none; }
    .takeaways-box { background: linear-gradient(135deg, #fffcf5 0%, #fff 100%); border-left: 6px solid #e67e22; padding: 25px; margin: 40px 0; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.03); }
    .table-wrapper { overflow-x: auto; margin: 40px 0; border-radius: 8px; border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; font-size: 17px; }
    th { background: #2c3e50; color: #fff; padding: 15px; text-align: left; }
    td { padding: 15px; border-bottom: 1px solid #eee; color: #444; }
    blockquote { background: #f8f9fa; border-left: 5px solid #27ae60; margin: 40px 0; padding: 20px 30px; font-style: italic; color: #555; font-size: 1.2em; }
    a { color: #2980b9; text-decoration: none; font-weight: 600; border-bottom: 2px dotted #2980b9; transition: all 0.3s; }
    a:hover { color: #e67e22; border-bottom: 2px solid #e67e22; }
    .faq-section { margin-top: 60px; background: #fdfdfd; padding: 30px; border-radius: 15px; border: 1px solid #eee; }
    .faq-q { color: #d35400; font-weight: bold; font-size: 20px; display: block; margin-bottom: 10px; }
    .Sources { font-size: 0.9em; color: #777; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .Sources ul { list-style-type: disc; padding-left: 20px; }
</style>
"""

# ==============================================================================
# 1. KEY MANAGER (ROTATION SYSTEM)
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        # Load keys from Environment Variables (1 to 10)
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        # Fallback to single key
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} Gemini API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Gemini Key #{self.current_index + 1}...")
            return True
        log("   ❌ ALL GEMINI KEYS EXHAUSTED.")
        return False

key_manager = KeyManager()

# ==============================================================================
# 2. ROBUST AI ENGINE (TENACITY + JSON REPAIR)
# ==============================================================================

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
    """Robust JSON extraction using Regex and json_repair."""
    if not text: return None
    
    # 1. Regex Extraction
    match = regex.search(r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]', text, regex.DOTALL)
    candidate = match.group(0) if match else text
    
    # 2. json_repair (Primary)
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass

    # 3. Standard Load (Fallback)
    try:
        clean = candidate.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except: return None

def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")
    return True

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=15),
    retry=retry_if_exception_type((JSONParsingError, JSONValidationError, Exception)),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(model_name, prompt, step_name, required_keys=[]):
    """
    The Unstoppable Generator: Handles Retries, Key Rotation, and Self-Repair.
    """
    log(f"   🧠 [AI Engine] Executing: {step_name}...")
    
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: All API Keys exhausted.")
    
    client = genai.Client(api_key=key)
    
    try:
        config_gen = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=STRICT_SYSTEM_PROMPT,
            temperature=0.3,
            top_p=0.8
        )

        response = client.models.generate_content(
            model=model_name, 
            contents=prompt, 
            config=config_gen
        )
        
        parsed_data = master_json_parser(response.text)
        
        # AI Self-Repair Logic
        if not parsed_data:
            log(f"      🔧 Repairing broken JSON for {step_name}...")
            repair_prompt = f"Fix this broken JSON (Return ONLY valid JSON):\n{response.text[:10000]}"
            repair_resp = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=repair_prompt,
                config=config_gen
            )
            parsed_data = master_json_parser(repair_resp.text)
            
            if not parsed_data:
                raise JSONParsingError(f"Failed to parse JSON for {step_name}")

        if required_keys:
            validate_structure(parsed_data, required_keys)
            
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg:
            log("      ⚠️ Quota Hit. Rotating Key...")
            if key_manager.switch_key(): raise e 
            else: raise RuntimeError("FATAL: Keys exhausted.")
        log(f"      ❌ Error in {step_name}: {str(e)[:100]}")
        raise e

# ==============================================================================
# 3. KNOWLEDGE GRAPH & MEMORY
# ==============================================================================

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): 
            with open('knowledge_graph.json','r') as f: return json.load(f)
    except: pass
    return []

def get_recent_titles_string(category=None, limit=100):
    kg = load_kg()
    if not kg: return "No previous articles found."
    relevant = [i for i in kg if i.get('section') == category] if category else kg
    titles = [f"- {i.get('title','Unknown')}" for i in relevant[-limit:]]
    return "\n".join(titles) if titles else "No previous articles in this category."

def get_relevant_kg_for_linking(category, limit=60):
    kg = load_kg()
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==category][:limit]
    return json.dumps(links)

def update_kg(title, url, section):
    try:
        data = load_kg()
        if any(i['url'] == url for i in data): return
        data.append({"title":title, "url":url, "section":section, "date":str(datetime.date.today())})
        with open('knowledge_graph.json','w') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: d=json.load(f)
            if len(d)>800: 
                with open('knowledge_graph.json','w') as f: json.dump(d[-400:], f, indent=2)
    except: pass

# ==============================================================================
# 4. ADVANCED SCRAPING (SELENIUM + TRAFILATURA)
# ==============================================================================

def resolve_and_scrape(target_url):
    """
    Primary Scraper: Uses Selenium to resolve redirects and Trafilatura for extraction.
    """
    log(f"      🕵️‍♂️ [Selenium] Resolving: {target_url[:60]}...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        
        driver.get(target_url)
        
        # Smart Wait for Redirects (Google News)
        start_wait = time.time()
        final_url = target_url
        while time.time() - start_wait < 15:
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1)
        
        final_title = driver.title
        page_source = driver.page_source
        
        # Filter Video/Gallery Pages
        if any(x in final_url.lower() for x in ["/video/", "/watch", "/gallery/", "youtube.com"]):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None

        # Extract Text
        text = trafilatura.extract(page_source, include_comments=False, include_tables=True, favor_precision=True)
        
        # Fallback Extraction
        if not text:
            soup = BeautifulSoup(page_source, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]): tag.extract()
            text = soup.get_text(" ", strip=True)

        if text and len(text) > 800:
            return final_url, final_title, text
            
        return None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {e}")
        return None, None, None
    finally:
        if driver: driver.quit()

# ==============================================================================
# 5. IMAGE GENERATION
# ==============================================================================

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    
    log(f"   🎨 Generating Thumbnail (Flux)...")
    enhancers = ", photorealistic, shot on Sony A7R IV, 85mm lens, f/1.8, cinematic lighting, youtube thumbnail style, 8k, --no cartoon"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}")
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"

    try:
        r = requests.get(image_url, timeout=60)
        if r.status_code != 200: return None
        
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        if overlay_text:
            draw = ImageDraw.Draw(img)
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arial.ttf"
                font = ImageFont.truetype(font_path, 80)
            except: font = ImageFont.load_default()
            
            text = overlay_text.upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            x = (img.width - (bbox[2] - bbox[0])) / 2
            y = img.height - (bbox[3] - bbox[1]) - 50
            
            # Stroke
            for adj in range(-4, 5):
                draw.text((x+adj, y), text, font=font, fill="black")
                draw.text((x, y+adj), text, font=font, fill="black")
            draw.text((x, y), text, font=font, fill="yellow")

        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        
        res = requests.post("https://api.imgbb.com/1/upload", data={"key": key, "name": f"thumb_{seed}"}, files={"image": img_byte_arr}, timeout=60)
        if res.status_code == 200: return res.json()['data']['url']
            
    except Exception as e:
        log(f"      ⚠️ Image Error: {e}")
    return None

# ==============================================================================
# 6. MASTER PIPELINE (THE ORCHESTRATOR)
# ==============================================================================

def run_pipeline(category, config):
    """
    Executes the full content lifecycle:
    Strategy -> Search (Selenium > GNews > AI) -> Draft -> Multimedia -> Publish -> Distribute.
    """
    model_name = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 STARTING PIPELINE: {category}")
    
    # --- STEP 0: SEO STRATEGY ---
    log("   🧠 [Step 0] Developing SEO Strategy...")
    target_keyword = ""
    try:
        seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today())
        seo_plan = generate_step_strict(model_name, seo_prompt, "SEO Strategy", ["target_keyword"])
        target_keyword = seo_plan.get('target_keyword')
        log(f"   🎯 Target Keyword: '{target_keyword}'")
    except:
        target_keyword = cat_conf.get('trending_focus', category).split(',')[0]
        log(f"   ⚠️ SEO Failed. Using default: {target_keyword}")

    # --- STEP 1: THE OMNI-HUNT (Waterfall Search) ---
    log(f"   🕵️‍♂️ [Step 1] Starting Omni-Hunt for: '{target_keyword}'")
    collected_sources = []
    main_headline = ""
    main_link = ""

    # 1.1: RSS Discovery
    rss_items = []
    try:
        # Try specific query first
        rss_items = news_fetcher.get_real_news_rss(f"{target_keyword} when:3d", category)
        if not rss_items:
            # Fallback to broad category
            rss_items = news_fetcher.get_real_news_rss(f"{category} news when:1d", category)
    except: pass

    # 1.2: Selenium Scraping (Primary)
    if rss_items:
        log(f"      👉 Attempting Selenium Scraping on {len(rss_items)} RSS items...")
        for item in rss_items[:6]:
            if len(collected_sources) >= 3: break
            if any(b in item['title'].lower() for b in BORING_KEYWORDS): continue
            
            url, title, text = resolve_and_scrape(item['link'])
            if text:
                domain = urllib.parse.urlparse(url).netloc
                collected_sources.append({"title": title, "text": text, "domain": domain, "url": url, "date": item['date']})
                if not main_headline: main_headline, main_link = title, url
                log(f"         ✅ Scraped: {title[:30]}...")
            time.sleep(2)

    # 1.3: GNews API Fallback (Secondary)
    if len(collected_sources) < 3:
        log("      ⚠️ Selenium yielded low results. Activating GNews API Fallback...")
        try:
            gnews_items = news_fetcher.get_gnews_api_sources(target_keyword, category)
            for item in gnews_items:
                if len(collected_sources) >= 3: break
                # Check duplication
                if any(s['url'] == item['link'] for s in collected_sources): continue
                
                url, title, text = resolve_and_scrape(item['link'])
                if text:
                    domain = urllib.parse.urlparse(url).netloc
                    collected_sources.append({"title": title, "text": text, "domain": domain, "url": url, "date": item['date']})
                    if not main_headline: main_headline, main_link = title, url
        except Exception as e:
            log(f"      ❌ GNews Error: {e}")

    # 1.4: AI Researcher / Google Search Fallback (Tertiary)
    if len(collected_sources) < 3:
        log("      ⚠️ GNews yielded low results. Activating AI Deep Search (Google Grounding)...")
        try:
            ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
            for item in ai_results:
                if len(collected_sources) >= 3: break
                if any(s['url'] == item['link'] for s in collected_sources): continue
                
                url, title, text = resolve_and_scrape(item['link'])
                if text:
                    domain = urllib.parse.urlparse(url).netloc
                    collected_sources.append({"title": title, "text": text, "domain": domain, "url": url, "date": "Today"})
                    if not main_headline: main_headline, main_link = title, url
        except Exception as e:
            log(f"      ❌ AI Search Error: {e}")



    
    
    # ... (الكود السابق)
    # Final Check
    if not collected_sources:
        log("❌ FATAL: All search methods failed. Aborting pipeline.")
        return

    # --- STEP 1.25: TOPIC REALIGNMENT ---
    # يضمن أننا نبحث في Reddit عن الموضوع الذي وجدنا له مصادر فعلاً
    try:
        headlines = [f"- {s['title']}" for s in collected_sources]
        headlines_str = "\n".join(headlines)
        
        # إذا كان الموضوع الرئيسي مختلفاً عن الكلمة المفتاحية الأصلية، نطلب إعادة توجيه
        first_headline = headlines[0] if headlines else ""
        if target_keyword.lower() not in first_headline.lower():
            log(f"   🎯 [Step 1.25] Realigning topic from '{target_keyword}' based on found articles...")
            
            realign_prompt = PROMPT_REALIGN_TOPIC.format(
                original_keyword=target_keyword,
                headlines_list=headlines_str
            )
            
            realign_result = generate_step_strict(
                "gemini-2.5-flash",  # نستخدم موديل سريع لهذه المهمة
                realign_prompt,
                "Topic Realignment",
                ["realigned_keyword"]
            )
            
            new_keyword = realign_result.get('realigned_keyword')
            
            if new_keyword:
                log(f"      ✅ New Aligned Keyword: '{new_keyword}'")
                target_keyword = new_keyword # <-- أهم سطر: نقوم بتحديث المتغير
            else:
                 log(f"      ⚠️ Realignment failed. Sticking with original keyword.")
    except Exception as e:
        log(f"      ⚠️ Topic Realignment failed: {e}. Using original keyword for subsequent steps.")


    # --- STEP 1.5: REDDIT INTEL (Injecting Human Experience) ---
    # ... (باقي الكود)
    # --- STEP 1.5: REDDIT INTEL (Injecting Human Experience) ---
    log(f"   🧠 [Step 1.5] Gathering Human Intelligence from Reddit...")
    reddit_intel_report, reddit_media = "", []
    try:
        # نستدعي الوحدة الجديدة باستخدام الكلمة المفتاحية المستهدفة
        reddit_intel_report, reddit_media = reddit_manager.get_community_intel(target_keyword)
        if not reddit_intel_report:
            log("      - No significant Reddit intel found. Proceeding with news sources only.")
    except Exception as e:
        log(f"      ⚠️ Reddit Intel module failed: {e}")


    # --- STEP 2: DRAFTING (The Strict Chain) ---
    log(f"   ✍️ [Step 2] Drafting Content from {len(collected_sources)} sources...")

    # تعديل: ندمج تقرير Reddit مع البيانات التي ستُرسل للكاتب
    source_texts = "\n".join([f"SOURCE {i+1}: {s['domain']}\nTitle: {s['title']}\nTEXT:\n{s['text'][:8000]}" for i, s in enumerate(collected_sources)])
    combined_text = f"{reddit_intel_report}\n\n*** OFFICIAL NEWS SOURCES ***\n{source_texts}"

    sources_list = [{"title": s['title'], "url": s['url']} for s in collected_sources]

    
    json_ctx = {
        "rss_headline": main_headline,
        "keyword_focus": target_keyword,
        "date": str(datetime.date.today()),
        "style_guide": "Critical, First-Person, Beginner-Focused"
    }
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** RESEARCH DATA ***\n{combined_text}"

    try:
        # Step B: Writer
        json_b = generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Writer", ["headline", "article_body"])
        
        # Step C: SEO
        kg_links = get_relevant_kg_for_linking(category)
        input_c = {"draft_content": json_b, "sources_data": sources_list}
        json_c = generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), "SEO", ["finalTitle", "finalContent", "imageGenPrompt"])
        
        # Step D: Humanizer
        json_d = generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalTitle", "finalContent"])
        
        # Step E: Polish
        final = generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), "Final Polish", ["finalTitle", "finalContent", "imageGenPrompt", "seo"])
        
        title = final['finalTitle']
        content_html = final['finalContent']
        seo_data = final.get('seo', {})
        img_prompt = final.get('imageGenPrompt', title)
        img_overlay = final.get('imageOverlayText', 'UPDATE')

    except Exception as e:
        log(f"❌ Drafting Error: {e}")
        traceback.print_exc()
        return

    # --- STEP 3: MULTIMEDIA ---
    log("   🎬 [Step 3] Generating Multimedia Assets...")
    
    # Inject Reddit Media into available visuals if needed
    if reddit_media:
        log(f"      📸 Found {len(reddit_media)} Reddit visual assets to consider.")
        # We could potentially use these URLs in the article or for video generation
    
    yt_meta = {}
    vid_main, vid_short = None, None
    fb_path, img_url = None, None
    vid_html = ""

    try:
        # Metadata & Image
        yt_meta = generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", ["title", "description", "tags"])
        fb_dat = generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)
        
        img_url = generate_and_upload_image(img_prompt, img_overlay)

        # Video Script & Render
        summ_clean = re.sub('<[^<]+?>','', content_html)[:2500]
        script_json = None
        
        for attempt in range(3):
            try:
                raw = generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ_clean), f"Script Att {attempt}")
                if 'video_script' in raw and isinstance(raw['video_script'], list):
                    script_json = raw['video_script']
                    break
            except: pass
        
        if script_json:
            ts = int(time.time())
            out_dir = os.path.abspath("output")
            os.makedirs(out_dir, exist_ok=True)
            
            # Main Video
            rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
            pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
            if pm:
                desc = f"{yt_meta.get('description','')}\n\n🚀 Full Story: {main_link}\n\n#{category.replace(' ','')}"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                if vid_main:
                    vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'

            # Short Video
            rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
            ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
            if ps:
                fb_path = ps
                vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])

    except Exception as e:
        log(f"⚠️ Multimedia Error: {e}")

    # --- STEP 4: PUBLISHING ---
    log("   🚀 [Step 4] Publishing to Blogger...")
    
    # Author Box
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
    
    # Sanitize Links
    content_html = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
    content_html = content_html.replace('href=""', 'href="').replace('"" target', '" target')
    content_html = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', content_html)

    # Assemble Body
    full_body = ARTICLE_STYLE
    if img_url:
        alt = seo_data.get("imageAltText", title)
        full_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" alt="{alt}" style="max-width:100%; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" /></a></div>'
    
    if vid_html: full_body += vid_html
    full_body += content_html + author_box
    
    if 'schemaMarkup' in final:
        try: full_body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass

    published_url = publisher.publish_post(title, full_body, [category, "Tech News", "Explainers"])

    # --- STEP 5: DISTRIBUTION ---
    if published_url:
        log(f"✅ PUBLISHED: {published_url}")
        update_kg(title, published_url, category)
        
        # Update YouTube Desc
        new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL ARTICLE HERE:\n{published_url}\n\n#AI #TechNews"
        if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
        if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
        
        # Facebook
        try:
            log("   📢 Distributing to Facebook...")
            if fb_path and os.path.exists(fb_path):
                social_manager.post_reel_to_facebook(fb_path, f"{fb_cap}\n\nRead more: {published_url}\n\n#AI", published_url)
            elif img_url:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{published_url}", published_url, img_url)
        except Exception as e:
            log(f"   ⚠️ Social Error: {e}")
    else:
        log("❌ Blogger Publish Failed.")

# ==============================================================================
# 7. MAIN ENTRY POINT
# ==============================================================================

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ No Config Found.")
        return
    
    # Pick a random category
    cat = random.choice(list(cfg['categories'].keys()))
    
    # Run
    run_pipeline(cat, cfg)
    
    # Cleanup
    perform_maintenance_cleanup()
    log("✅ Mission Complete.")

if __name__ == "__main__":
    main()
