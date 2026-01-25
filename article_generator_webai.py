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
from openai import OpenAI  # المكتبة الأساسية للاتصال بالسيرفر الجديد
import url_resolver
import trafilatura
import json_repair 
import regex 
import difflib
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from github import Github
import cv2
import numpy as np
import content_validator_webai # المدقق المخصص للسيرفر الجديد
import reddit_manager
from prompts import *

# ==============================================================================
# 0. CONFIGURATION & CLIENT INITIALIZATION
# ==============================================================================

# قراءة رابط السيرفر من GitHub Secrets
WEBAI_URL = os.getenv('WEBAI_BASE_URL')

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [WebAI-Engine] {msg}", flush=True)

if not WEBAI_URL:
    log("❌ FATAL: WEBAI_BASE_URL secret is missing!")
    sys.exit(1)

# تهيئة عميل OpenAI للاتصال بسيرفر WebAI
client = OpenAI(
    base_url=WEBAI_URL,
    api_key="webai-free-access", # مفتاح وهمي لأن السيرفر لا يتطلبه
    timeout=180.0 # مهلة طويلة لأن التوليد قد يستغرق وقتاً
)

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils",
    "unveiled", "poised to", "delve into", "game-changer", "paradigm shift",
    "tapestry", "robust", "leverage", "underscore", "testament to", "beacon of",
    "In conclusion", "Remember that", "It is important to note", "Imagine a world",
    "fast-paced world", "cutting-edge", "realm of"
]

ARTICLE_STYLE = "" # يمكن إضافة CSS مخصص هنا

# ==============================================================================
# 1. CORE GENERATION ENGINE (OPENAI WRAPPER)
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

def generate_step_webai(prompt, step_name, required_keys=[]):
    """
    الدالة البديلة لـ generate_step_strict. 
    تقوم بإرسال الطلب للسيرفر الخاص بك وتنتظر الرد بصيغة JSON.
    """
    log(f"   🚀 Executing: {step_name} via WebAI Server...")
    
    # السيرفر مبرمج لاستقبال موديل باسم "gemini" لتحويله للويب
    target_model = "gemini" 

    for attempt in range(1, 3): # محاولتان لكل خطوة
        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": STRICT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            raw_content = response.choices[0].message.content
            parsed_data = master_json_parser(raw_content)

            if not parsed_data:
                log(f"      ⚠️ Invalid JSON in {step_name}. Attempting repair...")
                continue

            if required_keys:
                missing = [k for k in required_keys if k not in parsed_data]
                if missing:
                    log(f"      ⚠️ Missing keys {missing} in attempt {attempt}.")
                    continue
            
            log(f"      ✅ Step {step_name} succeeded.")
            return parsed_data

        except Exception as e:
            log(f"      ❌ WebAI Request Failed (Attempt {attempt}): {e}")
            time.sleep(10) # انتظار قبل المحاولة التالية

    return None

# ==============================================================================
# 2. RESEARCH & NEWS UTILITIES
# ==============================================================================

def get_gnews_sources(query, category):
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key: return []
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(query)}&lang=en&apikey={api_key}"
    try:
        r = requests.get(url, timeout=15)
        return [{"title": a['title'], "link": a['url'], "date": a.get('publishedAt', 'Today'), "image": a.get('image')} for a in r.json().get('articles', [])]
    except: return []

def get_google_rss(query):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query + ' when:1d')}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        return [{"title": e.title.split(' - ')[0], "link": e.link, "date": "Today"} for e in feed.entries[:8]]
    except: return []

# ==============================================================================
# 3. KNOWLEDGE GRAPH & DUPLICATION GUARD
# ==============================================================================

def load_kg():
    if os.path.exists('knowledge_graph.json'):
        try: return json.load(open('knowledge_graph.json', 'r'))
        except: return []
    return []

def update_kg(title, url, section):
    kg = load_kg()
    kg.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
    with open('knowledge_graph.json', 'w') as f: json.dump(kg, f, indent=2)

def check_duplication(title, history_string):
    if not history_string or history_string == "No previous articles.": return False
    target = title.lower().strip()
    if target in history_string.lower(): return True
    
    # AI Semantic Duplication Check
    prompt = f"Is the topic '{title}' a duplicate of any of these: {history_string}? Return JSON {{'is_duplicate': true/false}}"
    res = generate_step_webai(prompt, "Duplication Check", ["is_duplicate"])
    return res.get('is_duplicate', False) if res else False

# ==============================================================================
# 4. MULTIMEDIA & IMAGE PROCESSING
# ==============================================================================

def upload_to_github(image_bytes, filename):
    try:
        gh = Github(os.getenv('MY_GITHUB_TOKEN'))
        repo = gh.get_repo(os.getenv('GITHUB_REPO_NAME'))
        path = f"images/{datetime.datetime.now().strftime('%Y-%m')}/{filename}"
        repo.create_file(path, f"Upload {filename}", image_bytes.getvalue(), branch="main")
        return f"https://cdn.jsdelivr.net/gh/{os.getenv('GITHUB_REPO_NAME')}@main/{path}"
    except Exception as e:
        log(f"      ❌ GitHub Upload Fail: {e}")
        return None

def process_and_upload_image(url, text, title):
    try:
        r = requests.get(url, timeout=20)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize((1200, 630), Image.Resampling.LANCZOS)
        
        if text:
            draw = ImageDraw.Draw(img)
            # محاولة تحميل خط عريض للعنوان
            try: font = ImageFont.truetype("arial.ttf", 70)
            except: font = ImageFont.load_default()
            draw.text((60, 500), text.upper(), font=font, fill="yellow", stroke_width=4, stroke_fill="black")
            
        byte_arr = BytesIO()
        img.save(byte_arr, format='WEBP', quality=85)
        filename = re.sub(r'[^a-zA-Z0-9]', '', title[:30]) + ".webp"
        return upload_to_github(byte_arr, filename)
    except: return None

def generate_ai_image(prompt, overlay):
    log("   🎨 Creating AI Image via Pollinations...")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1280&height=720&model=flux&nologo=true"
    try:
        r = requests.get(url, timeout=40)
        img = Image.open(BytesIO(r.content))
        byte_arr = BytesIO()
        img.save(byte_arr, format='WEBP')
        return upload_to_github(byte_arr, f"ai_{random.randint(100,999)}.webp")
    except: return None

# ==============================================================================
# 5. PUBLISHING ENGINE
# ==============================================================================

def publish_to_blogger(title, content, labels):
    token = social_manager.check_and_renew_facebook_token() # استغلال وظيفة التجديد الموجودة
    # ملاحظة: المشروع الأصلي يستخدم وظيفة مستقلة لبلوجر
    # هنا سنستخدم الـ Token المستخرج يدوياً من الـ Secrets كما في المشروع الأصلي
    auth_token = social_manager.requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }).json().get('access_token')

    if not auth_token: return None
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts?isDraft=false"
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    payload = {"title": title, "content": content, "labels": labels}
    
    r = requests.post(url, headers=headers, json=payload)
    return r.json().get('url') if r.status_code == 200 else None

# ==============================================================================
# 6. THE MASTER PIPELINE
# ==============================================================================

def run_webai_pipeline(category, config, manual_keyword=None):
    log(f"🏁 Starting Pipeline for: {category}")
    
    # 1. SEO Strategy
    target_keyword = manual_keyword
    if not target_keyword:
        kg = load_kg()
        history = "\n".join([f"- {i['title']}" for i in kg[-50:]]) if kg else "No previous articles."
        seo_res = generate_step_webai(PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=history), "SEO Strategy", ["target_keyword"])
        target_keyword = seo_res.get('target_keyword') if seo_res else None

    if not target_keyword: return False
    log(f"🎯 Target Keyword: {target_keyword}")

    if check_duplication(target_keyword, history):
        log("🚫 Topic already covered. Skipping...")
        return False

    # 2. Source Discovery
    log("📡 Searching for high-quality sources...")
    news_items = get_gnews_sources(target_keyword, category)
    if not news_items: news_items = get_google_rss(target_keyword)

    collected_sources = []
    full_research_text = ""
    for item in news_items[:4]:
        res = url_resolver.get_page_html(item['link'])
        if res and res.get('html'):
            txt = trafilatura.extract(res['html'])
            if txt and len(txt) > 500:
                collected_sources.append({"title": item['title'], "url": res['url'], "text": txt, "img": item.get('image')})
                full_research_text += f"\n--- SOURCE: {item['title']} ---\n{txt[:4000]}\n"
    
    if not collected_sources:
        log("❌ No readable sources found.")
        return False

    # 3. Writing Phase (B -> C -> D -> E)
    log("✍️ Generating Article Draft...")
    reddit_intel = reddit_manager.get_community_intel(target_keyword)
    payload_b = f"METADATA: {json.dumps({'keyword': target_keyword})}\nRESEARCH:\n{full_research_text}\nREDDIT:\n{reddit_intel}"
    
    json_b = generate_step_webai(PROMPT_B_TEMPLATE.format(json_input=payload_b, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Drafting", ["headline", "article_body"])
    if not json_b: return False

    log("SEO Polishing...")
    json_c = generate_step_webai(PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph="[]"), "SEO Polish", ["finalTitle", "finalContent", "imageGenPrompt"])
    if not json_c: return False

    log("Humanizing Content...")
    json_d = generate_step_webai(PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalContent"])
    if not json_d: return False

    log("Final Polish...")
    final = generate_step_webai(PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), "Finalizer", ["finalTitle", "finalContent"])
    if not final: return False

    # 4. Multimedia Production
    title = final['finalTitle']
    content = final['finalContent']
    
    log("🖼️ Processing Images...")
    main_img = None
    if collected_sources[0].get('img'):
        main_img = process_and_upload_image(collected_sources[0]['img'], final.get('imageOverlayText', 'News'), title)
    if not main_img:
        main_img = generate_ai_image(final.get('imageGenPrompt', title), final.get('imageOverlayText'))

    log("🎬 Rendering Video Shorts & Main...")
    vid_main_id, vid_short_id = None, None
    script_data = generate_step_webai(PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=content[:2000]), "Video Script", ["video_script"])
    
    if script_data and 'video_script' in script_data:
        # فيديو عرضي (16:9)
        rv_main = video_renderer.VideoRenderer(width=1920, height=1080)
        p_main = rv_main.render_video(script_data['video_script'], title, f"main_{int(time.time())}.mp4")
        
        # فيديو طولي (9:16)
        rv_short = video_renderer.VideoRenderer(width=1080, height=1920)
        p_short = rv_short.render_video(script_data['video_script'], title, f"short_{int(time.time())}.mp4")
        
        yt_meta = generate_step_webai(PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", ["title", "description"])
        
        if p_main:
            vid_main_id, _ = youtube_manager.upload_video_to_youtube(p_main, title, yt_meta.get('description',''), yt_meta.get('tags',[]))
        if p_short:
            vid_short_id, _ = youtube_manager.upload_video_to_youtube(p_short, title + " #Shorts", yt_meta.get('description',''), yt_meta.get('tags',[]))

    # 5. Professional Validation
    log("🛡️ Running Professional Self-Healing...")
    validator = content_validator_webai.AdvancedContentValidator(client)
    final_html = validator.run_professional_validation(content, full_research_text, collected_sources)

    # 6. Assembly & Final Post
    author_box = """<div style="margin-top:50px; padding:20px; background:#f4f4f4; border-radius:10px;"><h4>Written by Yousef Sameer</h4><p>Tech enthusiast and AI researcher.</p></div>"""
    img_html = f'<div class="main-image" style="text-align:center; margin-bottom:30px;"><img src="{main_img}" style="width:100%; border-radius:15px; box-shadow:0 10px 20px rgba(0,0,0,0.1);" /></div>' if main_img else ""
    vid_html = f'<div class="video-embed" style="margin:30px 0;"><iframe width="100%" height="450" src="https://www.youtube.com/embed/{vid_main_id}" frameborder="0" allowfullscreen></iframe></div>' if vid_main_id else ""
    
    full_body = ARTICLE_STYLE + img_html + vid_html + final_html + author_box
    
    # Publish
    log("🚀 Publishing to Blogger...")
    live_url = publish_to_blogger(title, full_body, [category, "AI News"])
    
    if live_url:
        log(f"✅ LIVE AT: {live_url}")
        update_kg(title, live_url, category)
        
        # Update YT descriptions with link
        if vid_main_id: youtube_manager.update_video_description(vid_main_id, f"Read the full article: {live_url}")
        if vid_short_id: youtube_manager.update_video_description(vid_short_id, f"Full Story: {live_url}")
        
        # Social Distribution (Facebook)
        fb_hook = generate_step_webai(PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
        if fb_hook:
            social_manager.distribute_content(fb_hook['FB_Hook'], live_url, main_img)
        
        return True
    
    return False

# ==============================================================================
# 7. EXECUTION ENTRY POINT
# ==============================================================================

def main():
    log("🌟 WebAI-to-API Blogger Engine Activated.")
    try:
        with open('config_advanced.json', 'r') as f:
            cfg = json.load(f)
    except:
        log("❌ config_advanced.json not found!")
        return

    categories = list(cfg['categories'].keys())
    random.shuffle(categories)
    
    success = False
    for cat in categories:
        if run_webai_pipeline(cat, cfg):
            success = True
            break # ننشر مقال واحد فقط في كل دورة
            
    if not success:
        log("⚠️ No articles published. Trying manual fallback from config...")
        for cat in categories:
            topics = cfg['categories'][cat].get('trending_focus', '').split(',')
            if topics:
                if run_webai_pipeline(cat, cfg, manual_keyword=random.choice(topics).strip()):
                    success = True
                    break

if __name__ == "__main__":
    main()
