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
# PROMPT ZERO: SEO STRATEGIST (THE BRAIN)
# ------------------------------------------------------------------
PROMPT_ZERO_SEO = """
Role: Aggressive SEO Strategist.
Input Category: "{category}"
Date: {date}

Task: Identify ONE specific, high-potential "Long-Tail Keyword".

**STRICT RULES:**
1. **AVOID GENERAL TOPICS:** Do NOT choose broad terms like "Future of AI", "AI Jobs", "Robotics News".
2. **BE SPECIFIC:** Target specific entities (e.g., "Figure 01 vs Tesla Optimus", "Devin AI update", "Gemini 1.5 Pro features").
3. **CONFLICT/HYPE:** Look for controversy, new releases, or specific problems.

Output JSON ONLY:
{{
  "target_keyword": "Specific search query",
  "reasoning": "Why this specific topic wins"
}}
**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. No Markdown.
"""

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
B: You are 'LatestAI', a popular Tech Analyst.
INPUT: {json_input}
FORBIDDEN: {forbidden_phrases}

**CRITICAL CONTEXT:**
I have provided **MULTIPLE SOURCES** below. 
Your task is to **SYNTHESIZE** them into one Master Guide.
- Cross-reference facts (if Source 1 says X and Source 2 says Y, mention the debate).
- If sources agree, confirm it as fact.
- Use the combined data to form a strong "Verdict" or "Opinion".

**STRICT HTML STRUCTURE:**
1. **Hook:** Why this topic is trending right now.
2. **What's Happening:** Combine facts from all sources.
3. **Quick Summary:** <ul> list.
4. [[TOC_PLACEHOLDER]]
5. **Deep Dive:** Explain the tech/news in detail.
6. **The Verdict (My Take):** Your analysis based on all data.
7. **Comparison Table:** <table>.

**WRITING RULES:**
- Tone: Professional but personal (Use "I", "We").
- Length: 1500+ words (You have plenty of source material now).
- Audience : ordinary people and beginners 
- Imagine you are explaining something to your friend who knows nothing about computers.
- The introduction should be very simple and assure the reader that they will understand everything easily.
- Explain complex concepts and concepts related to the subject itself in a simplified way so that anyone who knows nothing about computers or the subject itself can understand them.
- Headlines: Make them engaging, intriguing, and problem-solving.

**CRITICAL OUTPUT RULES:**
1. Return PURE VALID JSON ONLY.
2. ESCAPE ALL QUOTES inside HTML.
3. No Markdown.
4. Ensure that all HTML attributes utilize escaped double quotes (e.g. class=\"classname\") and avoid unescaped newlines inside JSON values.
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

6. *"Sources:**
   - Add `<div class="Sources">` 
   - Add titles of sources of the article with their linkes

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
4. Ensure that all HTML attributes utilize escaped double quotes (e.g. class=\"classname\") and avoid unescaped newlines inside JSON values.
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
3. *"Paragraphs:** Vary the length of the paragraphs, but do not exceed 5 lines.
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
4. Ensure that all HTML attributes utilize escaped double quotes (e.g. class=\"classname\") and avoid unescaped newlines inside JSON values.
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
4. Ensure that all HTML attributes utilize escaped double quotes (e.g. class=\"classname\") and avoid unescaped newlines inside JSON values.
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
4. The sentences must be short, and it's okay for the same person to have more than one message under each other.

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

Output JSON: {{"title": "...", "FB_Hook": "...", "description": "...", "tags": [...]}}


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

# ==============================================================================
# UPDATED JSON UTILITIES (AUTO-REPAIR MODE v2.0)
# ==============================================================================

           # ==============================================================================
# 5-LAYER ROBUST JSON PARSER (THE "UNBREAKABLE" ENGINE)
# ==============================================================================

def master_json_parser(text, context=""):
    """
    يحاول إصلاح الـ JSON بـ 5 طرق مختلفة متتالية.
    إذا نجحت واحدة، يعيد النتيجة. إذا فشل الكل، يعيد None.
    """
    if not text: return None
    
    log(f"      🛡️ [Parser] analyzing output for {context}...")

    # --- المستوى 1: التنظيف البسيط والتحويل المباشر ---
    # إزالة علامات الماركداون ```json ... ```
    cleaned = re.sub(r'```(?:json)?', '', text).strip()
    cleaned = cleaned.replace('```', '')
    
    try:
        return json.loads(cleaned)
    except:
        pass

    # --- المستوى 2: مكتبة json_repair (الحل السحري) ---
    # هذه المكتبة مخصصة لإصلاح أخطاء LLMs مثل الأقواس الناقصة
    try:
        repaired_obj = json_repair.repair_json(cleaned, return_objects=True)
        if repaired_obj:
            log(f"      🔧 [Parser] json_repair fixed the data!")
            return repaired_obj
    except:
        pass

    # --- المستوى 3: البحث عن JSON باستخدام Regex ---
    # أحياناً يضع الذكاء الاصطناعي مقدمة نصية طويلة قبل الـ JSON
    try:
        # البحث عن أول قوس { وآخر قوس }
        match = regex.search(r'\{(?:[^{}]|(?R))*\}', text, regex.DOTALL)
        if match:
            potential_json = match.group(0)
            return json_repair.repair_json(potential_json, return_objects=True)
    except:
        pass

    # --- المستوى 4: Python AST (لتعامل مع Single Quotes) ---
    # أحياناً يستخدم الموديل ' بدلاً من " وهذا خطأ في JSON لكنه صحيح في Python
    try:
        # خطير قليلاً لكنه فعال كحل أخير
        return ast.literal_eval(cleaned)
    except:
        pass

    log(f"      ❌ [Parser] All local methods failed for {context}.")
    return None

def generate_step_robust(model, prompt, step_name):
    """
    دالة التوليد الذكية مع خاصية الإصلاح الذاتي (Self-Correction)
    """
    log(f"   👉 Generating: {step_name}")
    
    # 3 محاولات للتوليد
    for attempt in range(3):
        key = key_manager.get_current_key()
        if not key: return None
        
        client = genai.Client(api_key=key)
        
        try:
            # 1. الطلب من API
            r = client.models.generate_content(
                model=model, 
                contents=prompt, 
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            raw_text = r.text
            
            # 2. محاولة التحليل باستخدام "المحرك الخماسي"
            parsed_data = master_json_parser(raw_text, step_name)
            
            # 3. التحقق من النتيجة
            if parsed_data and isinstance(parsed_data, (dict, list)):
                return parsed_data # ✅ نجاح!
            
            # --- المستوى 5: الإصلاح عبر الذكاء الاصطناعي (AI Repair) ---
            # إذا فشلت كل الطرق البرمجية، نطلب من الذكاء الاصطناعي إصلاح نفسه
            log(f"      ⚠️ parsing failed. Triggering AI Self-Correction (Attempt {attempt+1}/3)...")
            
            repair_prompt = f"""
            SYSTEM ALERT: You generated INVALID JSON.
            Error Context: The parser could not read your previous output.
            
            YOUR TASK: Fix the syntax errors in the content below. 
            RULES:
            1. Output ONLY valid JSON.
            2. Check for unescaped quotes inside strings.
            3. Remove any trailing commas.
            
            BROKEN CONTENT:
            {raw_text[:8000]}
            """
            
            # محاولة الإصلاح بموديل سريع
            r_fix = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=repair_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            # فحص نتيجة الإصلاح
            fixed_data = master_json_parser(r_fix.text, f"{step_name}_FIX")
            if fixed_data and isinstance(fixed_data, (dict, list)):
                log("      ✅ AI successfully repaired the JSON!")
                return fixed_data
                
        except Exception as e:
            if "429" in str(e):
                key_manager.switch_key()
            else:
                log(f"❌ Error: {e}")
                
    log(f"❌ FATAL: Could not generate valid JSON for {step_name} after all attempts.")
    return None # نعيد None بدلاً من String لتجنب AttributeError     
            

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
    The Master Pipeline v11.0 (Smart Analyst Mode).
    1. SEO Strategy (AI decides the keyword).
    2. Multi-Source Scraping (Collects top 3 sources).
    3. Synthesis & Drafting (Writes a comprehensive guide).
    4. Multimedia Gen (Video/Image) with Absolute Path fixes.
    5. Publishing & Distribution.
    """
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} (Smart Analyst Mode 🧠)")
    
    # تحميل قاعدة المعرفة لتجنب التكرار
    recent_titles = get_recent_titles_string(limit=60)

    # =====================================================
    # STEP 0: SEO STRATEGY (THE BRAIN)
    # =====================================================
    log("   🧠 Consulting SEO Strategist for a winning keyword...")
    
    # طلب كلمة مفتاحية ذكية من الذكاء الاصطناعي بناءً على الفئة والتاريخ
    seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today())
    seo_plan = try_parse_json(generate_step(model, seo_prompt, "Step 0 (SEO Strategy)"), "SEO")
    
    target_keyword = ""
    if seo_plan and 'target_keyword' in seo_plan:
        target_keyword = seo_plan.get('target_keyword')
        log(f"   🎯 Strategy Defined: Targeting keyword '{target_keyword}'")
        log(f"   📝 Reasoning: {seo_plan.get('reasoning', 'No reasoning provided')}")
    else:
        # Fallback: في حال فشل الذكاء الاصطناعي، نعود للكلمات الموجودة في الإعدادات
        target_keyword = cat_conf.get('trending_focus', category)
        if "," in target_keyword:
            target_keyword = random.choice([t.strip() for t in target_keyword.split(',')])
        log(f"   ⚠️ SEO Step failed or timed out. Using fallback keyword: '{target_keyword}'")

    # =====================================================
    # STEP 1: MULTI-SOURCE RESEARCH (THE HUNTER)
    # =====================================================
    # البحث في أخبار جوجل عن الكلمة المفتاحية المحددة (آخر 3 أيام لضمان الحداثة ووفرة المصادر)
    rss_query = f"{target_keyword} when:3d"
    rss_items = get_real_news_rss(rss_query.replace("when:3d","").strip(), category)
    
    # محاولة ثانية بنطاق أوسع إذا لم نجد نتائج دقيقة
    if not rss_items:
        log("   ⚠️ No specific news found for this keyword. Retrying with broad category search...")
        rss_items = get_real_news_rss(category, category)
        if not rss_items:
            log("❌ FATAL: No RSS items found even after fallback. Aborting.")
            return

    collected_sources = []
    main_headline = ""
    main_link = ""
    
    log(f"   🕵️‍♂️ Investigating multiple sources for: '{target_keyword}'...")
    
    # حلقة الفحص: نفحص أول 6 نتائج لنستخرج أفضل 3 منها
    for item in rss_items[:6]:
        # 1. فلترة التكرار (تجاهل ما تم نشره سابقاً)
        if item['title'][:20] in recent_titles: 
            log(f"      ⏭️ Skipped duplicate title: {item['title'][:30]}...")
            continue
        
        # 2. فلترة المصدر المكرر (لا نأخذ مقالين من نفس الموقع)
        if any(src['domain'] in item['link'] for src in collected_sources): 
            continue

        log(f"      📌 Checking Source: {item['title'][:40]}...")
        
        # محاولة فك الرابط وجلب المحتوى
        r_url, r_title, text = resolve_and_scrape(item['link'])
        
        # 3. فلترة الجودة (The Quality Filter)
        # نرفض المقالات القصيرة جداً (أقل من 800 حرف) لأنها لا تصلح لبناء محتوى دسم
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
            
            # نعتمد بيانات أول مصدر كبيانات أساسية (للعنوان والرابط)
            if not main_headline:
                main_headline = item['title']
                main_link = item['link']
            
            # نكتفي بـ 3 مصادر قوية
            if len(collected_sources) >= 3: 
                log("      ✨ Collected sufficient data (3 robust sources). Proceeding to draft.")
                break
        else:
            current_len = len(text) if text else 0
            log(f"         ⚠️ Rejected (Weak/Short Content). Length: {current_len}")
            time.sleep(1) # راحة لتجنب الحظر

    # إذا لم ننجح في جمع أي مصدر صالح
    if not collected_sources:
        log("❌ FATAL: No valid high-quality sources found after filtering. Skipping execution.")
        return

    # =====================================================
    # STEP 2: DRAFTING & SYNTHESIS (THE WRITER)
    # =====================================================
    log(f"\n✍️ Synthesizing Content from {len(collected_sources)} sources...")
    
    # دمج النصوص المستخرجة في كتلة نصية واحدة منظمة
    combined_text = ""
    for i, src in enumerate(collected_sources):
        combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nTitle: {src['title']}\nDate: {src['date']}\nCONTENT:\n{src['text'][:9000]}\n"

    # تحضير الـ Payload للنموذج
    json_ctx = {
        "rss_headline": main_headline, # العنوان المقترح من المصدر الأول
        "keyword_focus": target_keyword,
        "source_count": len(collected_sources),
        "date": str(datetime.date.today())
    }
    
    # توجيه الموديل لاستخدام المصادر المتعددة
    prefix = "*** MULTI-SOURCE RESEARCH DATA (SYNTHESIZE THIS) ***"
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n{prefix}\n{combined_text}"
    
    # توليد المسودة (Step B)
    json_b = try_parse_json(generate_step(model, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)"), "B")
    if not json_b: return

    # تحسين السيو والتنسيق (Step C)
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
    json_c = try_parse_json(generate_step(model, prompt_c, "Step C (SEO & Style)"), "C")
    if not json_c: return

    # التدقيق وأنسنة النص (Step D)
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
    json_d = try_parse_json(generate_step(model, prompt_d, "Step D (Humanizer)"), "D")
    if not json_d: return

    # التنظيف النهائي للكود (Step E)
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
    final = try_parse_json(generate_step(model, prompt_e, "Step E (Final Polish)"), "E")
    
    # في حال فشل الخطوة الأخيرة، نعود للخطوة السابقة
    if not final: final = json_d 

    # اعتماد العنوان النهائي
    title = final.get('finalTitle', main_headline)
    
    # =====================================================
    # STEP 3: MULTIMEDIA GENERATION (VIDEO & IMAGE)
    # =====================================================
    log("   🧠 Generating Multimedia Assets...")
    
    # 1. Social Metadata
    yt_meta = try_parse_json(generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta"))
    if not yt_meta: 
        yt_meta = {"title": title, "description": f"Read full story: {main_link}", "tags": []}
    
    fb_dat = try_parse_json(generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Hook"))
    fb_cap = fb_dat.get('facebook', title ) if fb_dat else title

    # 2. Video Generation (With Absolute Path Fix)
    vid_html, vid_main, vid_short, fb_path = "", None, None, None
    
    try:
        # إصلاح المسار: استخدام مسار مطلق (Absolute Path) لتجنب أخطاء ffmpeg
        base_output_dir = os.path.abspath("output")
        os.makedirs(base_output_dir, exist_ok=True) # إنشاء المجلد إذا لم يكن موجوداً
        
        # استخراج ملخص للنص لعمل السكربت
        summ = re.sub('<[^<]+?>','', final.get('finalContent',''))[:2500]
        
        # توليد السكربت
        script = try_parse_json(generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script"))
        
        if script:
            timestamp = int(time.time())
            rr = video_renderer.VideoRenderer()
            
            # --- Main Video (Landscape) ---
            main_video_filename = f"main_{timestamp}.mp4"
            main_video_path = os.path.join(base_output_dir, main_video_filename)
            
            log(f"      🎬 Rendering Main Video to: {main_video_path}")
            pm = rr.render_video(script, title, main_video_path)
            
            if pm and os.path.exists(pm):
                # رفع الفيديو لليوتيوب
                desc = f"{yt_meta.get('description','')}\n\n🚀 Full Article Link Coming Soon.\n\n#{category.replace(' ','')} #AI #TechNews"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                
                if vid_main:
                    # تضمين الفيديو في المقال
                    vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            else:
                log("      ⚠️ Main video render returned None or file missing.")

            # --- Short Video (Portrait/Reel) ---
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            short_video_filename = f"short_{timestamp}.mp4"
            short_video_path = os.path.join(base_output_dir, short_video_filename)
            
            log(f"      🎬 Rendering Short Video to: {short_video_path}")
            ps = rs.render_video(script, title, short_video_path)
            
            if ps and os.path.exists(ps):
                fb_path = ps # نحتفظ بالمسار للفيسبوك
                # رفع الشورت لليوتيوب
                vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
            else:
                log("      ⚠️ Short video render returned None or file missing.")
                
    except Exception as e: 
        log(f"⚠️ Video Generation Logic Error: {e}")
        # طباعة تتبع الخطأ في الكونسول للمساعدة في التصحيح
        import traceback
        traceback.print_exc()

    # 3. Image Generation
    img = generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText', 'News'))

    # =====================================================
    # STEP 4: PUBLISHING
    # =====================================================
    log("   🚀 Publishing to Blogger...")
    
    # تجميع جسم المقال (HTML)
    body = ARTICLE_STYLE # الستايلات
    
    # إضافة الصورة البارزة
    if img: 
        alt_text = final.get("seo",{}).get("imageAltText","Tech News")
        body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{alt_text}" /></a></div>'
    
    # إضافة الفيديو (إذا وجد)
    if vid_html: body += vid_html
    
    # إضافة المحتوى النصي
    body += final.get('finalContent', '')
    
    # إضافة Schema (JSON-LD)
    if 'schemaMarkup' in final:
        try: 
            body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass
    
    # النشر الفعلي
    url = publish_post(title, body, [category])
    
    # =====================================================
    # STEP 5: DISTRIBUTION & UPDATES
    # =====================================================
    if url:
        # تحديث قاعدة المعرفة
        update_kg(title, url, category)
        
        # تحديث وصف فيديوهات اليوتيوب بالرابط الجديد
        upd_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL STORY HERE:\n{url}\n\n#AI #Technology #{category.replace(' ','')}"
        if vid_main: youtube_manager.update_video_description(vid_main, upd_desc)
        if vid_short: youtube_manager.update_video_description(vid_short, upd_desc)
        
        try:
            # النشر على فيسبوك
            log("   📢 Distributing to Social Media...")
            
            # الخيار الأول: نشر الفيديو القصير (Reel)
            if fb_path and os.path.exists(fb_path): 
                fb_full_text = f"{fb_cap}\n\nRead more: {url}\n\n#AI #{category.replace(' ','')}"
                social_manager.post_reel_to_facebook(fb_path, fb_full_text)
                time.sleep(15) # انتظار للمعالجة
            
            # الخيار الثاني: نشر الصورة مع الرابط (إذا لم ينجح الفيديو)
            elif img:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read Article:\n{url}", url, img)
                
        except Exception as e: 
            log(f"   ⚠️ Social Distribution Error: {e}")
# ==============================================================================
# 5. CORE PIPELINE LOGIC (OFFLINE DECODER + JINA)
# ==============================================================================


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
