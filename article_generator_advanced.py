import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import feedparser
from bs4 import BeautifulSoup  # New requirement: BeautifulSoup for scraping
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING
# ==============================================================================

# Words that indicate AI patterns (Stricter list)
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
# 1. CSS STYLING (Complete)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* Global Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    h2 { color: #111; font-weight: 800; margin-top: 50px; margin-bottom: 20px; border-bottom: 4px solid #f1c40f; padding-bottom: 5px; display: inline-block; font-size: 28px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 35px; font-size: 24px; }
    
    /* Table of Contents */
    .toc-box { background: #fdfdfd; border: 1px solid #e1e4e8; padding: 25px; margin: 30px 0; border-radius: 12px; display: inline-block; min-width: 60%; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    .toc-box h3 { margin-top: 0; font-size: 20px; border-bottom: 2px solid #3498db; padding-bottom: 8px; display: inline-block; margin-bottom: 15px; color: #222; }
    .toc-box ul { list-style: none; padding: 0; margin: 0; }
    .toc-box li { margin-bottom: 10px; border-bottom: 1px dashed #eee; padding-bottom: 5px; padding-left: 20px; position: relative; }
    .toc-box li:before { content: "►"; color: #3498db; position: absolute; left: 0; font-size: 12px; top: 4px; }
    .toc-box a { color: #444; font-weight: 600; font-size: 17px; text-decoration: none; transition: 0.2s; }
    .toc-box a:hover { color: #3498db; padding-left: 5px; }

    /* Tables */
    .table-wrapper { overflow-x: auto; margin: 35px 0; border-radius: 12px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; }
    th { background: #2c3e50; color: #fff; padding: 15px; text-align: left; }
    td { padding: 14px 16px; border-bottom: 1px solid #eee; color: #34495e; }
    tr:nth-child(even) { background-color: #f8f9fa; }

    /* Key Takeaways */
    .takeaways-box { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-left: 6px solid #2c3e50; padding: 25px; margin: 35px 0; border-radius: 8px; }
    .takeaways-box h3 { margin-top: 0; color: #222; font-size: 22px; margin-bottom: 15px; }
    .takeaways-box ul { margin: 0; padding-left: 20px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 500; font-size: 18px; }

    /* FAQ */
    .faq-section { margin-top: 60px; border-top: 2px solid #ecf0f1; padding-top: 40px; background: #fffbf2; padding: 30px; border-radius: 10px; }
    .faq-title { font-size: 26px; font-weight: 800; color: #2c3e50; margin-bottom: 25px; text-align: center; }
    .faq-q { font-weight: 700; font-size: 20px; color: #d35400; margin-bottom: 8px; display: block; }
    .faq-a { font-size: 18px; color: #555; line-height: 1.8; }

    /* Other */
    .separator img { border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.15); max-width: 100%; height: auto; display: block; }
    blockquote { background: #fff; border-left: 5px solid #ffb703; margin: 35px 0; padding: 20px 35px; font-style: italic; color: #555; font-size: 1.2em; line-height: 1.6; }
    a { color: #2980b9; text-decoration: none; font-weight: 500; border-bottom: 2px dotted #2980b9; transition: 0.3s; }
    a:hover { color: #e67e22; border-bottom: 1px solid #e67e22; }
</style>
"""

# ==============================================================================
# 2. PROMPTS DEFINITIONS
# ==============================================================================

# 🛑🛑🛑 [AREA FOR MANUAL PROMPTS] 🛑🛑🛑
# Paste your DETAILED Beast Mode Prompts here.
# NOTE: Update 'PROMPT_B' to acknowledge it will receive 'FULL SOURCE TEXT'.

# ==============================================================================
# 2. PROMPTS DEFINITIONS (FULL, UNABRIDGED, BEAST MODE v7.0)
# ==============================================================================

# ------------------------------------------------------------------
# PROMPT A: RESEARCH (Focus on Analyzable Trends)
# ------------------------------------------------------------------
PROMPT_A_TRENDING = """
A: You are a Viral Tech Trend Hunter & Analyst. I have fetched real-time headlines from RSS.

INPUT RSS DATA:
{rss_data}

SECTION FOCUS:
{section_focus}

ANTI-DUPLICATION RULE:
Do NOT select: {recent_titles}

TASK INSTRUCTIONS:
1. Scan the headlines.
2. Select EXACTLY ONE story that appeals to **General Public and Enthusiasts** (not just scientists).
3. **Selection Logic:**
   - Look for "Conflict" (US vs China).
   - Look for "Daily Life Impact" (Jobs, Privacy, Costs).
   - Look for "Big Releases" (ChatGPT, iPhone, Windows).
   - **AVOID:** Dry academic papers, obscure version updates (e.g. LibTorch 1.1), or minute stock fluctuations.
4. If a headline suggests a specific "Release", assume the role of explaining *if it's worth it* or *what it changes*.

Output JSON only:
{{
  "headline": "A catchy, viral-style headline (e.g. 'Why [Event] Changes Everything')",
  "original_rss_link": "The URL Link from RSS",
  "original_rss_title": "The exact title...",
  "topic_focus": "The core implication/story",
  "why_selected": "High viral potential / Impact on regular users",
  "date_context": "{today_date}"
}}
"""

# Backup Prompt (Keep as is)
PROMPT_A_EVERGREEN = """
A: Expert Technical Educator. 
Task: Outline a comprehensive guide about {section}.
Anti-Duplication: Avoid {recent_titles}.

Output JSON ONLY:
{{
  "headline": "Definitive Guide: [Topic] in 2026",
  "original_rss_link": "https://en.wikipedia.org/wiki/Technology",
  "topic_focus": "Educational Guide",
  "date_context": "Evergreen"
}}
"""

# ------------------------------------------------------------------
# PROMPT B: WRITER (Analyst + Fact Adherence)
# ------------------------------------------------------------------
PROMPT_B_TEMPLATE = """
B: You are an Opinionated Tech Analyst and Editor-in-Chief of 'LatestAI'. 
**CRITICAL CONTEXT:** I have visited the source URL and scraped the content for you. 
Use the provided `SOURCE CONTENT` below as your PRIMARY source of facts.

INPUT DATA: {json_input}
STRICT FORBIDDEN PHRASES: {forbidden_phrases}

**RULES OF ENGAGEMENT (Safety First):**
1. **Fact Fidelity:** If the `SOURCE CONTENT` says "4.8 million", write "4.8 million". If it implies a number but doesn't state it, write "Millions of..." or "A significant number". **DO NOT HALLUCINATE NUMBERS.**
2. **Name Safety:** Only name people explicit in the Source text. Otherwise, use "Officials", "Company Reps", or "Industry Insiders".
3. **The Audience:** Write for the "Smart Beginner". Explain complex terms simply (ELI15). Use analogies.

I. ARCHITECTURE FOR VALUE (The Article Structure):
1. **Headline:** Use the provided headline.
2. **Introduction (The Hook):** Start with the context/problem, then drop the news. End the intro with a bridge: "Here is why this matters to you."
3. **The Bottom Line (Snippet Trap):** An H2 titled "**Quick Summary**". Under it, write a 50-word **Bold** summary of the impact.
4. **Table of Contents:** Insert exact string: `[[TOC_PLACEHOLDER]]`.
5. **Section 1: The Core Story:** Explain WHAT happened using facts from Source Content.
6. **Section 2: The Critical Analysis:** An H2 titled "**The Good, The Bad, and The Scary**". Discuss risks/benefits critically. Don't just hype it up.
7. **Section 3: Future Outlook:** How does this affect the next 6 months?
8. **Comparison Table:** Compare "Old Way vs New Way" or "This Tech vs Competitor".

II. TONE:
- **Analytic:** "We believe...", "This suggests...".
- **Engaging:** Use short paragraphs. Use Bullet points often.

Output JSON ONLY:
{{
  "draftTitle": "Final Headline",
  "draftContent": "<html>... Full Content ...</html>",
  "excerpt": "A short, punchy summary for SEO.",
  "sources_used": ["Entities found in Source Content"]
}}
"""

# ------------------------------------------------------------------
# PROMPT C: SEO (Structure & Schema)
# ------------------------------------------------------------------
PROMPT_C_TEMPLATE = """
C: You are the Strategic Editor & SEO Consultant.
INPUT DRAFT: {json_input}
KNOWLEDGE GRAPH LINKS: {knowledge_graph}

YOUR TASKS (EXECUTE ALL):

1. **TOC Injection:** Replace `[[TOC_PLACEHOLDER]]` with a styled HTML div (class="toc-box") containing a title "Quick Navigation" and a `<ul>` of anchor links to all H2s. **IMPORTANT:** You MUST add unique `id` attributes to all H2 tags in the content so the links work.

2. **FAQ Rich Snippets:** Extract 3 questions a *User* would ask about this topic. Create a VISUAL HTML section at the bottom (class="faq-section", `faq-title`, `faq-q`, `faq-a`).

3. **Styling Wrappers:** 
   - Wrap "Quick Summary/Takeaways" bullets in `class="takeaways-box"`. 
   - Wrap tables in `class="table-wrapper"`.
   - Wrap quotes in `blockquote`.

4. **Internal Linking:** Scan for keywords from `KNOWLEDGE GRAPH LINKS`. Link naturally (Max 3 links).

5. **Schema Generation (Graph):** 
   Generate a valid JSON-LD graph:
   - Node 1: `NewsArticle` (headline, date, author="LatestAI").
   - Node 2: `FAQPage` (the 3 extracted Q&A).

Output JSON ONLY:
{{
  "finalTitle": "...",
  "finalContent": "<html>...Modified HTML with IDs, TOC, Links, Visual FAQ...</html>",
  "imageGenPrompt": "Detailed English prompt for Flux (abstract, futuristic, 3d, cinematic, 8k, no text)",
  "imageOverlayText": "2-3 word Overlay Text",
  "seo": {{
      "metaTitle": "SEO Title (60 chars)",
      "metaDescription": "SEO Description (150 chars)",
      "tags": ["tag1", "tag2", "tag3"],
      "imageAltText": "Alt Text"
  }},
  "schemaMarkup": {{ "@context": "https://schema.org", "@graph": [...] }}
}}
"""

# ------------------------------------------------------------------
# PROMPT D: AUDIT (Final Safety Check)
# ------------------------------------------------------------------
PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Safety Audit
Input: {json_input}

MISSION: Purge robotic patterns and verify logic.

CHECKLIST:
1. **Robotic Word Purge:** Replace "Delve", "Realm", "Tapestry", "Game-changer", "Paramount", "Underscore" with simple human words.
2. **Formatting Logic:** Verify `id` tags exist on H2s for TOC. Verify FAQ section exists.
3. **Safety:** Ensure product names look real based on context (no "Spot Cam 3D" unless source confirms). Generalize if unsure ("New Camera").

Output JSON ONLY (Preserve all fields from Input C):
{{"finalTitle":"...", "finalContent":"...", "imageGenPrompt":"...", "imageOverlayText":"...", "seo": {{...}}, "schemaMarkup":{{...}}, "sources":[...], "excerpt":"..."}}
"""

# ------------------------------------------------------------------
# PROMPT E: PUBLISHER (JSON Hygiene)
# ------------------------------------------------------------------
PROMPT_E_TEMPLATE = """
E: The Publisher Role.
Task: Clean and Finalize JSON for deployment.

CRITICAL: Return raw valid JSON string only. No markdown fences. No preamble.

Input data: {json_input}

Output Structure:
{{"finalTitle":"...", "finalContent":"...", "imageGenPrompt":"...", "imageOverlayText":"...", "seo": {{...}}, "schemaMarkup":{{...}}, "sources":[...], "authorBio": {{...}}}}
"""

# ------------------------------------------------------------------
# VIDEO PROMPTS (Viral Scripts)
# ------------------------------------------------------------------
PROMPT_VIDEO_SCRIPT = """
Role: Viral Tech TikTok Screenwriter.
Input: "{title}" & "{text_summary}"

Task: Create a "WhatsApp" style dialogue script.
Characters:
- "Alex" (Hype Tech Bro, uses emojis 🚀).
- "Sam" (Normal person/Beginner).

Rules:
1. **Opening:** Alex drops a bombshell headline.
2. **Simplicity:** Alex explains the news using a real-world analogy.
3. **Reaction:** Sam asks "Is it free?" or "When?" (Common questions).
4. **CTA:** Alex: "Full details in the link below!".
5. **Length:** 25-30 short bubbles.

Output JSON ONLY array:
[ {{"speaker": "Alex", "type": "send", "text": "..."}}, ... ]
"""

# ------------------------------------------------------------------
# SOCIAL PROMPTS (CTR Optimization)
# ------------------------------------------------------------------
PROMPT_YOUTUBE_METADATA = """
Role: YouTube Clickbait Expert (But Ethical).
Input: {draft_title}

Task: Generate High-CTR metadata.
Output JSON ONLY:
{{
  "title": "Shocking/Viral Title (Max 60 chars) - Use ALL CAPS for keywords",
  "description": "2-line spicy hook teasing the implications. #Hashtags",
  "tags": ["tech", "ai", "news", "trend"]
}}
"""

PROMPT_FACEBOOK_HOOK = """
Role: FB Growth Hacker.
Input: {title}

Rules:
1. Don't start with "Here is". Start with "Did you know?" or "This is scary...".
2. Keep it under 2 lines.
3. Use 2 specific emojis.

Output JSON ONLY:
{{"facebook": "Caption text here"}}
"""

# ==============================================================================
# 3. HELPER FUNCTIONS & CLASSES
# ==============================================================================

class KeyManager:
    """Round-robin Gemini API Keys."""
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
            log(f"🔄 Quota limit. Switching to Key #{self.current_index + 1}...")
            return True
        else:
            log("❌ FATAL: All API Keys exhausted.")
            return False

key_manager = KeyManager()

def clean_json(text):
    """Robust JSON cleaner (Nuclear option)."""
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: text = match.group(1)
    
    if text.startswith("[") or (text.find("[") != -1 and text.find("[") < text.find("{")):
        start = text.find('[')
        end = text.rfind(']')
    else:
        start = text.find('{')
        end = text.rfind('}')
    
    if start != -1 and end != -1: return text[start:end+1].strip()
    return text.strip()

def try_parse_json(text, context=""):
    try: return json.loads(text)
    except:
        try:
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except:
            log(f"      ❌ JSON Parse Error in {context}")
            return None

def fetch_full_article(url):
    """
    🌟 NEW: SCRAPER ENGINE 🌟
    Visits the real URL, grabs the body text to provide factual data to AI.
    """
    log(f"   🕷️ Scraping Article Source: {url}")
    try:
        # User-Agent to mimic real Chrome browser (bypass some blocks)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # If scraper fails (403/404), return None to fallback
        if response.status_code != 200:
            log(f"      ⚠️ Scrape blocked ({response.status_code}). Using RSS summary.")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Cleanup DOM
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'ads', 'iframe']):
            tag.decompose()
            
        # Extract meaningful text (Paragraphs)
        # Filters out short nav links or empty lines
        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text()) > 25]
        
        # Combine text (Limit to first 12,000 chars to respect Token Limits)
        full_text = "\n\n".join(paragraphs)[:12000]
        
        if len(full_text) < 200:
            log("      ⚠️ Scraped content too short. Using RSS summary.")
            return None
            
        return full_text
        
    except Exception as e:
        log(f"      ⚠️ Scrape Exception: {e}")
        return None

def get_real_news_rss(query_keywords, category):
    try:
        # Smart Niche Selector
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
            for entry in feed.entries[:7]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                # Note: 'link' here is passed to scraper later
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        else:
            # Fallback Logic
            log(f"   ⚠️ RSS Empty. Fallback to category.")
            fallback_q = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fallback_q)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
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
    
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    
    # 🔴 التغيير الهام هنا:
    # إضافة parameter "?isDraft=false" للرابط مباشرة.
    # هذا يجبر جوجل على نشر المقال فوراً للملأ (Public/Live).
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts?isDraft=false"
    
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
    # لا نرسل published date لكي يأخذ توقيت السيرفر الحالي (الآن)
    data = {
        "title": title, 
        "content": content, 
        "labels": labels
    }
    
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            post_data = r.json()
            real_url = post_data.get('url')
            log(f"✅ Published INSTANTLY: {real_url}")
            return real_url
        else:
            log(f"❌ Publish Error: {r.text}")
            return None
    except Exception as e:
        log(f"❌ Connection Error: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    log(f"   🎨 Generating Image (Flux)...")
    for attempt in range(3):
        try:
            safe = urllib.parse.quote(f"{prompt_text}, abstract tech, 8k, --no text")
            txt = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white" if overlay_text else ""
            url = f"https://image.pollinations.ai/prompt/{safe}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,999)}{txt}"
            r = requests.get(url, timeout=50)
            if r.status_code == 200:
                res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if res.status_code == 200:
                    link = res.json()['data']['url']
                    log(f"   ✅ Image URL: {link}")
                    return link
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

def get_relevant_kg_for_linking(current_category, limit=60):
    kg = load_kg()
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==current_category][:limit]
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
                log(f"      ⚠️ Key Quota. Switching...")
                if not key_manager.switch_key(): return None
            else:
                log(f"      ❌ AI Error: {e}")
                return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (RSS + SCRAPING + 5 STEPS)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} ({mode})")
    recent = get_recent_titles_string()

    # 1. RSS
    rss_items = get_real_news_rss(cat_conf.get('trending_focus',''), category)
    if not rss_items: return # Stop if empty

    # Flatten RSS for prompt
    rss_prompt_data = "\n".join([f"- Title: {i['title']}\n  Link: {i['link']}\n  Date: {i['date']}" for i in rss_items])

    # 2. Step A: Research Selection
    prompt_a = PROMPT_A_TRENDING.format(rss_data=rss_prompt_data, section=category, section_focus=cat_conf['trending_focus'], recent_titles=recent, today_date=str(datetime.date.today()))
    json_a = try_parse_json(generate_step(model, prompt_a, "Step A (Research)"), "A")
    if not json_a: return
    
    # 2.5: SCRAPING ENGINE (The Fact Checker)
    target_link = json_a.get('original_rss_link')
    log(f"   🗞️ Topic: {json_a.get('headline')} \n   🔗 Fetching source: {target_link}")
    
    full_source_text = fetch_full_article(target_link)
    
    if full_source_text:
        log("   ✅ Source Content Acquired. Using Factual Mode.")
        input_payload = f"*** REAL SOURCE CONTENT (USE THIS FACTS): ***\n\n{full_source_text}\n\n*** END SOURCE ***\n\n(Context: {json.dumps(json_a)})"
    else:
        log("   ⚠️ Source Blocked. Falling back to Analytical Mode.")
        input_payload = f"*** SOURCE UNAVAILABLE ***\n(Analyze the headline implications: {json.dumps(json_a)})"

    time.sleep(3)

    # 3. Step B: Drafting (Uses Scraped Input)
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=input_payload, forbidden_phrases=str(FORBIDDEN_PHRASES))
    json_b = try_parse_json(generate_step(model, prompt_b, "Step B (Drafting)"), "B")
    if not json_b: return
    time.sleep(3)

    # 4. Step C: Format & SEO
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
    json_c = try_parse_json(generate_step(model, prompt_c, "Step C (SEO)"), "C")
    if not json_c: return
    time.sleep(3)

    # 5. Step D: Audit
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
    json_d = try_parse_json(generate_step(model, prompt_d, "Step D (Audit)"), "D")
    if not json_d: return
    time.sleep(3)

    # 6. Step E: Publish
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
    final_data = try_parse_json(generate_step(model, prompt_e, "Step E"), "E")
    
    # Failover if E returns text not json
    if not final_data: final_data = json_d 

    title = final_data.get('finalTitle', f"{category} News")

    # ========================================================
    # 🎥 MEDIA & SOCIAL
    # ========================================================
    log("   🧠 Generating Hooks...")
    yt_meta = try_parse_json(generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta")) or {"title":title, "description":"", "tags":[]}
    fb_data = try_parse_json(generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Hook"))
    fb_cap = fb_data.get('facebook', title) if fb_data else title

    video_html, vid_main, vid_short, vid_path_fb = "", None, None, None
    try:
        # Pass scraped text summary for script accuracy
        script = try_parse_json(generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=final_data['excerpt']), "Script"))
        
        if script:
            rr = video_renderer.VideoRenderer()
            # 16:9
            pm = rr.render_video(script, title, f"main_{int(time.time())}.mp4")
            if pm:
                desc = f"{yt_meta['description']}\n\n👉 Full Story Link Soon.\n\n#AI #Tech"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                if vid_main:
                    video_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            # 9:16
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            ps = rs.render_video(script, title, f"short_{int(time.time())}.mp4")
            vid_path_fb = ps
            if ps: vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
    except Exception as e: log(f"⚠️ Video: {e}")

    # ========================================================
    # 📝 PUBLISH
    # ========================================================
    html_body = ARTICLE_STYLE
    img = generate_and_upload_image(final_data.get('imageGenPrompt', title), final_data.get('imageOverlayText', 'News'))
    if img: html_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{final_data["seo"]["imageAltText"]}" /></a></div>'
    
    if video_html: html_body += video_html
    html_body += final_data.get('finalContent', '')
    
    if 'schemaMarkup' in final_data:
        try: html_body += f'\n<script type="application/ld+json">\n{json.dumps(final_data["schemaMarkup"])}\n</script>'
        except: pass
    
    url = publish_post(title, html_body, [category])
    
    # Social Update
    if url:
        update_kg(title, url, category)
        upd = f"\n\n🚀 FULL LINK: {url}"
        if vid_main: youtube_manager.update_video_description(vid_main, upd)
        if vid_short: youtube_manager.update_video_description(vid_short, upd)
        
        try:
            if vid_path_fb: social_manager.post_reel_to_facebook(vid_path_fb, f"{fb_cap}\n\nRead: {url} #Tech")
            time.sleep(10)
            if img: social_manager.distribute_content(f"{fb_cap}\n\n👇 BREAKDOWN:\n{url}", url, img)
        except: pass

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
