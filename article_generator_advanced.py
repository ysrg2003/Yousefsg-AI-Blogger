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

# 🛑 الصق البرومبتات التفصيلية "Beast Mode" هنا 🛑
# (تأكد من أن PROMPT_B يطلب استخدام Source Text)


# ==============================================================================
# 2. PROMPTS DEFINITIONS (v10.0 - THE "CREATOR" MODE)
# ==============================================================================

# ------------------------------------------------------------------
# PROMPT A: TOPIC SELECTION (Filter: "Is this clickable content?")
# ------------------------------------------------------------------
PROMPT_A_TRENDING = """
A: You are a Viral Content Strategist for a Tech Blog.
INPUT RSS DATA: {rss_data}
SECTION: {section_focus}
IGNORE: {recent_titles}

**YOUR GOAL:**
Ignore boring corporate news (stocks, quarterly earnings, lawsuits). 
Find the ONE story that a **YouTuber** or **TikToker** would make a video about today.

**SELECTION CRITERIA (The "WIIFM" Factor - What's In It For Me?):**
1. **Utility:** Does this solve a problem? (e.g., "New tool fixes bad wifi").
2. **Curiosity:** Is it weird or scary? (e.g., "AI can now fake your voice").
3. **Mass Appeal:** Does it affect phones/apps everyone uses? (WhatsApp, Instagram, iPhone, Android).

**OUTPUT JSON:**
{{
  "headline": "Create a 'How-to' or 'Explainer' style headline. (NOT a news headline). Ex: 'The New [Feature] is Here: How to Use It'",
  "original_rss_link": "URL",
  "original_rss_title": "Original Title",
  "topic_focus": "Practical application for the user",
  "why_selected": "High practical value for beginners",
  "date_context": "{today_date}"
}}
**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. No Markdown (```json).
3. No conversational filler.
"""

# ------------------------------------------------------------------
# PROMPT B: CONTENT CREATOR (The "Friendly Expert")
# ------------------------------------------------------------------
PROMPT_B_TEMPLATE = """
B: You are 'LatestAI', a popular Tech Blogger and Creator.
**CONTEXT:** You are NOT a journalist. You are a guide. 
Use the `SOURCE CONTENT` facts, but rewrite them as a helpful blog post.

INPUT: {json_input}
FORBIDDEN WORDS: {forbidden_phrases} (Plus: "Reportedly", "According to sources", "Allegedly").

**STRATEGY:**
- **Tone:** Enthusiastic, Personal, Clear. Use "I", "We", "You".
- **Goal:** Take complex news and turn it into actionable advice.

**STRICT HTML STRUCTURE:**
1. **The Hook (Intro):** Start with a relatable problem. "Don't you hate it when...?" Then introduce the news as the solution.
2. **What Actually Happened:** `<h2>` Title. Simple explanation of the news (No jargon).
3. **The "Cheat Sheet":** 
   - `<h2>` titled "**Quick Summary**".
   - Under it: `<ul>` with 5 bullet points (Emojis allowed here).
4. **Navigation:** Insert: `[[TOC_PLACEHOLDER]]`.
5. **Why This Matters to YOU:** `<h2>` Title. 
   - Explain the *benefit*. Will it save time? Save money?
6. **The Tutorial / How-To (Crucial):** `<h2>` Title (e.g., "**How to Try It**" or "**What to Expect**").
   - Even if the feature isn't out, explain the steps to get ready.
7. **The Verdict:** `<h2>` titled "**My Opinion**". Is it hype or real?
8. **Comparison Table:** HTML `<table>` comparing "Old Way" vs "New Way".

**WRITING RULES:**
- **Short & Punchy:** Paragraphs = 2-3 lines max.
- **Visuals:** Use `<strong>` to highlight cool features.
- **Explain:** If you say "latency", write "(aka lag)".

Output JSON ONLY:
{{
  "draftTitle": "A Title That Sounds Like a YouTube Video (e.g. 'Stop Doing This...')",
  "draftContent": "<html>...Content...</html>",
  "excerpt": "Compelling summary for social media.",
  "sources_used": ["List"]
}}
**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. **ESCAPE QUOTES:** You are writing HTML inside JSON. You MUST escape quotes.
   - WRONG: "content": "<div class="box">"
   - RIGHT: "content": "<div class=\\"box\\">"
3. No Markdown blocks.
"""

# ------------------------------------------------------------------
# PROMPT C: VISUALS & SEO (The "Magazine Editor")
# ------------------------------------------------------------------
PROMPT_C_TEMPLATE = """
C: Polish the content for a high-end blog.
INPUT: {json_input}
KG LINKS: {knowledge_graph}

**TASKS:**

1. **Format Injection:**
   - Replace `[[TOC_PLACEHOLDER]]` with `<div class="toc-box"><h3>Table of Contents</h3><ul>...</ul></div>`.
   - Add `id="sec-X"` to all H2 headers.

2. **Styling Wrappers (Match CSS):**
   - Wrap "Quick Summary" list in: `<div class="takeaways-box">...</div>`.
   - Wrap Table in: `<div class="table-wrapper">...</div>`.
   - **NEW:** Find the "My Opinion" or "Verdict" section and wrap it in: `<blockquote>...</blockquote>` to make it stand out.

3. **FAQ for Beginners:**
   - Add `<div class="faq-section">` at the end.
   - Questions must be basic: "Is it free?", "Is it safe?", "When can I get it?".

4. **Internal Linking:** 
   - Link to other topics naturally.

5. **Schema:** 
   - Use `Article` or `TechArticle` schema (better than NewsArticle for evergreen content).

Output JSON ONLY:
{{
  "finalTitle": "...",
  "finalContent": "<html>...</html>",
  "imageGenPrompt": "Minimalist 3D render of [Subject], abstract technology, soft studio lighting, pastel colors, high quality, --no text, --no faces",
  "imageOverlayText": "Simple Label (e.g. 'NEW UPDATE')",
  "seo": {{
      "metaTitle": "Clicky Title (60 chars)",
      "metaDescription": "Benefit-driven description (150 chars).",
      "tags": ["tag1", "tag2", "tag3"],
      "imageAltText": "Abstract representation of [Topic]"
  }},
  "schemaMarkup": {{ ... }}
}}
**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. **ESCAPE QUOTES:** Ensure all HTML attributes use escaped quotes (\\").
3. Do NOT truncate content.
"""

# ------------------------------------------------------------------
# PROMPT D: HUMANIZER (The "Vibe Check")
# ------------------------------------------------------------------
PROMPT_D_TEMPLATE = """
PROMPT D — Final Polish
Input: {json_input}

**MISSION:** Kill the "Robot". Make it "Human".

**RULES:**
1. **Sentence Length:** If a sentence is too long (20+ words), split it.
2. **Vocabulary:** 
   - Change "Utilize" -> "Use".
   - Change "Facilitate" -> "Help".
   - Change "Furthermore" -> "Also".
   - Change "In conclusion" -> "The Bottom Line".
3. **Formatting:** Ensure the `takeaways-box` and `toc-box` classes are present.

Output JSON ONLY (Keep structure):
{{"finalTitle":"...", "finalContent":"...", "imageGenPrompt":"...", "imageOverlayText":"...", "seo": {{...}}, "schemaMarkup":{{...}}, "sources":[...], "excerpt":"..."}}
**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. Maintain valid HTML escaping.
3. No Markdown.
"""

# ------------------------------------------------------------------
# PROMPT E: CLEANER
# ------------------------------------------------------------------
PROMPT_E_TEMPLATE = """
E: You are a JSON Formatter.
Input: {json_input}

Task: Output the exact same JSON, but ensure it is syntactically correct.
1. Escape all double quotes inside HTML attributes (e.g. `class=\\"box\\"`)
2. Do NOT change the content logic.

**CRITICAL OUTPUT RULES:**
1. Return RAW JSON STRING ONLY.
2. Remove any markdown fences (```).
3. Ensure no trailing commas.
"""
# ------------------------------------------------------------------
# SOCIAL: ENGAGEMENT FOCUSED
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# SOCIAL: VIDEO SCRIPT (FIXED KEYS)
# ------------------------------------------------------------------
PROMPT_VIDEO_SCRIPT = """
Role: Scriptwriter for Viral Tech Shorts.
Input: "{title}" & "{text_summary}"

Task: Create a dialogue script between two characters.
Characters:
- "User" (Curious, asks questions).
- "Pro" (Expert, explains solution).

**CRITICAL JSON RULES:**
1. You MUST use exactly these keys: "speaker", "type", "text".
2. "type" must be either "send" (Right side) or "receive" (Left side).
3. "text" is the dialogue.

Example Output:
[
  {{"speaker": "User", "type": "receive", "text": "Wait, did you see this update?"}},
  {{"speaker": "Pro", "type": "send", "text": "Yes! It's actually insane. Here is why..."}}
]

**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ARRAY ONLY ( [ ... ] ).
2. No Markdown.
"""

PROMPT_YOUTUBE_METADATA = """
Role: YouTube Expert.
Input: {draft_title}

Output JSON: {{"title": "...", "description": "...", "tags": [...]}}

**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. No Markdown.
"""

PROMPT_FACEBOOK_HOOK = """
Role: Community Manager.
Input: {title}

**Strategy:** 
- Start with a question.
- "Tag a friend who needs this".
- Keep it under 280 chars.

**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. No Markdown.
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


# ==============================================================================
# UPDATED JSON UTILITIES (AUTO-REPAIR MODE)
# ==============================================================================

def clean_json(text):
    """
    Advanced cleaner: Removes Markdown, extracts the JSON array/object only.
    """
    if not text: return ""
    text = text.strip()
    
    # 1. تنظيف كود الماركدوان
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    
    # 2. البحث عن أول قوس { أو [ وآخر قوس } أو ]
    # هذا يزيل أي مقدمات مثل "Here is the JSON code:"
    start_brace = text.find('{')
    start_bracket = text.find('[')
    
    start_index = -1
    if start_brace != -1 and start_bracket != -1:
        start_index = min(start_brace, start_bracket)
    elif start_brace != -1:
        start_index = start_brace
    elif start_bracket != -1:
        start_index = start_bracket
        
    if start_index != -1:
        text = text[start_index:]
        
    # البحث عن النهاية
    end_brace = text.rfind('}')
    end_bracket = text.rfind(']')
    
    end_index = -1
    if end_brace != -1 and end_bracket != -1:
        end_index = max(end_brace, end_bracket)
    elif end_brace != -1:
        end_index = end_brace
    elif end_bracket != -1:
        end_index = end_bracket
        
    if end_index != -1:
        text = text[:end_index+1]
        
    return text.strip()

def try_parse_json(text, context=""):
    """
    Robust parser: Tries standard JSON, then Python Eval, then manual fixes.
    """
    if not text: return None
    
    # المحاولة 1: JSON قياسي
    try:
        return json.loads(text)
    except:
        pass

    # المحاولة 2: Python Literal Eval
    # (موديلات AI غالباً تستخدم ' بدلاً من " وهذا يكسر JSON لكنه مقبول في بايثون)
    try:
        return ast.literal_eval(text)
    except:
        pass

    # المحاولة 3: إصلاح الهروب (Escaping Fix) - لمحاولة إنقاذ HTML المكسور
    try:
        # استبدال الأسطر الجديدة الحقيقية بـ \n
        fixed_text = text.replace('\n', '\\n').replace('\r', '')
        # محاولة أخيرة بوضع strict=False
        return json.loads(fixed_text, strict=False)
    except:
        log(f"      ❌ JSON Parse Error ({context}). Input length: {len(text)}")
        # في حال الفشل التام، نطبع جزءاً من النص لنعرف السبب
        log(f"      🔍 Broken Snippet: {text[:100]}...")
        return None


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


# ==============================================================================
# 5. CORE PIPELINE LOGIC (OFFLINE DECODER + JINA)
# ==============================================================================


def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} (High Quality Mode)")
    
    # تحميل قاعدة المعرفة لتجنب التكرار
    recent_titles = get_recent_titles_string(limit=60)
    
    # إعداد محاولات البحث (لتغيير الكلمة المفتاحية اذا لم نجد مقالات)
    max_global_retries = 6 
    article_found = False
    
    selected_item = None
    source_content = None
    final_resolved_url = None
    
    # 🔄 الحلقة الكبرى: تدور وتغير الكلمات المفتاحية حتى تجد مقالاً مناسباً
    for attempt in range(max_global_retries):
        if article_found: break
        
        log(f"\n🔎 Attempt #{attempt+1} of {max_global_retries}")
        
        # 1. اختيار موضوع عشوائي (Keyword Rotation)
        query_keywords = cat_conf.get('trending_focus', category)
        current_topic = category # Default
        
        if "," in query_keywords:
            topics = [t.strip() for t in query_keywords.split(',') if t.strip()]
            # اختيار عشوائي لضمان التنوع في كل محاولة
            current_topic = random.choice(topics)
            log(f"   🎯 Targeted Search: '{current_topic}'")
            # نضيف 'when:1d' لأخبار اليوم، أو 'when:3d' إذا أردت نطاق أوسع
            rss_query = f"{current_topic} when:2d" 
        else:
            rss_query = f"{query_keywords} when:2d"

        # 2. جلب RSS
        rss_items = get_real_news_rss(rss_query.replace("when:2d","").strip(), category)
        
        if not rss_items:
            log("   ⚠️ No RSS items found for this keyword. Retrying next...")
            continue
            
        # 3. حلقة فحص المقالات داخل RSS
        for item in rss_items:
            # فلترة التكرار
            if item['title'][:20] in recent_titles: 
                log(f"   ⏭️ Skipped duplicate: {item['title'][:30]}")
                continue
            
            log(f"   📌 Checking RSS Item: {item['title'][:50]}...")
            
            # محاولة الفك والجلب
            r_url, r_title, text = resolve_and_scrape(item['link'])
            
            # --- شرط الجودة (The Quality Check) ---
            # 1. يجب أن يوجد نص
            # 2. يجب أن يكون النص أطول من 1500 حرف (لضمان أنه مقال كامل وليس فيديو أو خبر قصير)
            if text and len(text) >= 1500:
                log(f"      ✅ High Quality Content Found! ({len(text)} chars)")
                log(f"      ⚖️  Match Check:\n          RSS: {item['title']}\n          Pg : {r_title}")
                
                selected_item = item
                selected_item['link'] = r_url # تحديث الرابط بالرابط الحقيقي
                selected_item['real_title'] = r_title # حفظ العنوان الحقيقي للمقارنة لاحقاً
                source_content = text
                article_found = True
                break # نخرج من حلقة المقالات
            else:
                current_len = len(text) if text else 0
                log(f"      ⚠️ Content too short ({current_len} chars) or failed. Looking for better article...")
                time.sleep(2) # راحة قصيرة
        
        if not article_found:
            log("   ⚠️ None of the RSS items met the quality standards. Switching topic...")
            time.sleep(3)

    # 4. إذا انتهت كل المحاولات ولم نجد شيئاً
    if not selected_item or not source_content:
        log("❌ FATAL: Could not find ANY high-quality article after multiple attempts.")
        log("❌ Skipping this run to preserve quality.")
        return

    # =======================================================
    # B. DRAFTING PHASE (Now we are sure we have good content)
    # =======================================================
    log(f"\n✍️ Starting Writing Process for: {selected_item['title']}")
    
    # تحضير الـ Payload
    json_ctx = {
        "rss_headline": selected_item['title'],
        "resolved_headline": selected_item.get('real_title', ''),
        "original_link": selected_item['link'],
        "date": selected_item['date']
    }
    
    # دمج العنوانين للموديل ليفهم السياق أفضل
    prefix = "*** FULL SOURCE TEXT (High Quality Scrape) ***"
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n{prefix}\n\n{source_content}"
    
    # Step B
    json_b = try_parse_json(generate_step(model, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B"), "B")
    if not json_b: return

    # Step C (SEO)
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
    json_c = try_parse_json(generate_step(model, prompt_c, "Step C"), "C")
    if not json_c: return

    # Step D (Audit)
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
    json_d = try_parse_json(generate_step(model, prompt_d, "Step D"), "D")
    if not json_d: return

    # Step E (Publish)
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
    final = try_parse_json(generate_step(model, prompt_e, "Step E"), "E")
    if not final: final = json_d 

    title = final.get('finalTitle', selected_item['title'])
    
    # =======================================================
    # SOCIALS & VIDEO
    # =======================================================
    log("   🧠 Socials...")
    yt_meta = try_parse_json(generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta"))
    # تأمين البيانات الافتراضية
    if not yt_meta: yt_meta = {"title": title, "description": f"Read full story: {selected_item['link']}", "tags": []}
    
    fb_dat = try_parse_json(generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Hook"))
    fb_cap = fb_dat.get('facebook', title) if fb_dat else title

    # Video Gen
    vid_html, vid_main, vid_short, fb_path = "", None, None, None
    try:
        # استخراج ملخص نصي نظيف للسكربت
        summ = re.sub('<[^<]+?>','', final.get('finalContent',''))[:2000]
        
        # التأكد من تمرير النص الكامل لتوليد سكريبت جيد
        script = try_parse_json(generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Script"))
        
        if script:
            os.makedirs("output", exist_ok=True)
            rr = video_renderer.VideoRenderer()
            # فيديو عرضي لليوتيوب
            pm = rr.render_video(script, title, f"output/main_{int(time.time())}.mp4")
            if pm:
                desc = f"{yt_meta.get('description','')}\n\n🚀 Article Link Coming Soon.\n\n#{category.replace(' ','')} #AI"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                if vid_main:
                    vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            
            # فيديو طولي (Reels/Shorts)
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            ps = rs.render_video(script, title, f"output/short_{int(time.time())}.mp4")
            if ps:
                fb_path = ps
                vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
    except Exception as e: log(f"⚠️ Video Error: {e}")

    # =======================================================
    # PUBLISHING
    # =======================================================
    body = ARTICLE_STYLE
    img = generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText', 'News'))
    if img: body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{final.get("seo",{}).get("imageAltText","News")}" /></a></div>'
    
    if vid_html: body += vid_html
    body += final.get('finalContent', '')
    
    if 'schemaMarkup' in final:
        try: body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass
    
    url = publish_post(title, body, [category])
    
    if url:
        update_kg(title, url, category)
        # تحديث الوصف بالرابط
        upd_desc = f"{yt_meta.get('description','')}\n\n👇 FULL STORY:\n{url}\n\n#AI #TechNews"
        if vid_main: youtube_manager.update_video_description(vid_main, upd_desc)
        if vid_short: youtube_manager.update_video_description(vid_short, upd_desc)
        
        try:
            if fb_path: 
                # نشر الريلز مع الهاشتاغات والرابط
                fb_full_text = f"{fb_cap}\n\nRead more: {url}\n\n#AI #Technology #{category.replace(' ','')}"
                social_manager.post_reel_to_facebook(fb_path, fb_full_text)
                time.sleep(15)
            elif img:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{url}", url, img)
        except Exception as e: log(f"Social Post Error: {e}")

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
