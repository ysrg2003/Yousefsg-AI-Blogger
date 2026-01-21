import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import feedparser  # يجب التأكد من وجود هذه المكتبة
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING & HUMANIZATION
# ==============================================================================

# قائمة الكلمات المحظورة (إضافة جديدة لتحسين الجودة)
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
    "Imagine a world"
]

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING (MODERN TECH LOOK)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* General Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #2c3e50; font-size: 19px; }
    h2 { color: #1a252f; font-weight: 800; margin-top: 45px; margin-bottom: 25px; border-bottom: 3px solid #ffd700; padding-bottom: 5px; display: inline-block; font-size: 28px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 35px; font-size: 24px; }
    
    /* Key Takeaways Box */
    .takeaways-box {
        background: #f8f9fa;
        border-left: 6px solid #2c3e50;
        padding: 25px;
        margin: 35px 0;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .takeaways-box h3 { margin-top: 0; color: #2c3e50; font-size: 22px; }
    .takeaways-box ul { margin-bottom: 0; padding-left: 20px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 500; }

    /* Tables */
    .table-wrapper { overflow-x: auto; margin: 35px 0; border-radius: 12px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; }
    th { background: #34495e; color: #fff; padding: 16px; text-align: left; }
    td { padding: 14px 16px; border-bottom: 1px solid #eee; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    tr:hover { background-color: #f1f1f1; }

    /* Blockquotes */
    blockquote {
        background: #fffaf0;
        border-left: 5px solid #ffb703;
        margin: 35px 0;
        padding: 20px 30px;
        font-style: italic;
        color: #555;
        font-size: 1.15em;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* Links */
    a { color: #d35400; text-decoration: none; font-weight: 600; transition: color 0.3s; }
    a:hover { color: #e67e22; text-decoration: underline; }
    
    /* Images */
    .separator img { border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.15); max-width: 100%; height: auto; }
    
    /* Sources Section */
    .sources-section { background: #fdfdfd; padding: 20px; border-radius: 8px; font-size: 0.9em; color: #7f8c8d; margin-top: 60px; border-top: 1px solid #eee; }
</style>
"""

# ==============================================================================
# 2. PROMPTS DEFINITIONS (FULL & UPDATED)
# ==============================================================================

# PROMPT A: تم تحديثه ليعمل مع RSS
PROMPT_A_TRENDING = """
A: You are a Lead Investigative Tech Reporter. I have fetched the LATEST REAL-TIME headlines from Google News RSS for "{section}".

INPUT RSS DATA (Real headlines from last 24h):
{rss_data}

SECTION FOCUS:
{section_focus}

**CRITICAL ANTI-DUPLICATION RULE:**
The following topics have already been covered. DO NOT write about them again. Find a NEW story:
{recent_titles}

TASK:
1. Analyze the RSS headlines.
2. Select ONE high-impact story. Ignore generic "What is AI?" articles. Look for Launches, Breakthroughs, or Legal news.
3. Extract the core event and main entity.

Output JSON only, EXACTLY in this format:
{{"headline": "One-line journalist-style headline","sources": [{{"title":"Original RSS Title","url":"Link provided in RSS","date":"{today_date}","type":"news","why":"Main Source","credibility":"High"}}],"riskNote":"..."}}
"""

PROMPT_A_EVERGREEN = """
A:You are an expert technical educator specialized in {section}. Your task is to outline a comprehensive, authoritative article about a core concept of {section}.
Instead of recent news, search for and cite: Foundational papers, Standard definitions, Official Documentation, and Key Textbooks.

TOPIC PROMPT: {evergreen_prompt}

**CRITICAL ANTI-DUPLICATION RULE:**
Check the following list of existing guides. Ensure your angle or specific topic is DISTINCT or an UPDATE:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. **HEADLINE STRATEGY (CRITICAL):** 
   - Do NOT start with "The Ultimate Guide" or "A Deep Dive". These are forbidden.
   - Create a specific, professional headline that reflects the exact angle of the content.
   - Use varied structures. Examples:
     * "Mastering [Concept]: Strategies for..."
     * "The Architecture of [Concept]: A Technical Breakdown"
     * "Why [Concept] Matters for Modern AI Pipelines"
     * "Building Scalable [Concept] Systems: Best Practices"
     * "[Concept] Explained: From Theory to Production"
2. Provide 2–3 authoritative sources (Seminal Papers, Documentation, University Lectures).
3. Output JSON ONLY (Same format as news to maintain pipeline compatibility):
{{"headline": "Your Unique Professional Headline", "sources": [{{"title":"...", "url":"...", "date":"YYYY-MM-DD (or N/A)", "type":"documentation|paper|book", "why":"Foundational reference", "credibility":"High"}}], "riskNote":"..."}}
"""

PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A (headline + sources). Write a polished HTML article (1500–2000 words) using the provided headline and sources. Follow these rules exactly.
INPUT: {json_input}

**STRICT FORBIDDEN PHRASES (DO NOT USE):**
{forbidden_phrases}

I. STRUCTURE & VOICE RULES (mandatory):

H1 = headline exactly as provided (unless you correct minor grammar, then keep original in an attribute).

Intro (do NOT start with "Imagine" or "In today’s world"): begin with a short, verifiable human hook:
If you have a named, sourced quote from the sources, start with it (quote + attribution).
If no named source quote exists, start with a clearly labeled "illustrative composite" sentence (e.g., "Illustrative composite: a researcher at a mid-size lab described…").

Use journalistic, conversational English — not academic tone:
Paragraphs: 2–4 sentences maximum.
Sentence length distribution: ~40% short (6–12 words), ~45% medium (13–22 words), ~15% long (23–35 words). Do not use sentences >35 words.
Use contractions where natural (e.g., "it's", "they're") to sound human.
Include exactly one first-person editorial sentence from the writer (e.g., "In my experience covering X, I've seen...") — keep it 1 sentence only.
Include one rhetorical question in the article (short).

Tone: authoritative but approachable. Use occasional colloquial connectors (e.g., "That said," "Crucially,") — sparingly.

II. EDITORIAL PRINCIPLES (applied inline):
So What? — after each major fact/claim, add a one-sentence human explanation of its impact (no template phrase).
Depth over breadth — choose 4–5 major points from the sources and analyze them deeply (quantitative where possible).
Dual verification — any load-bearing claim (numbers, performance, market sizes, legal claims) must be inline-cited to at least two independent sources. If only one exists, explicitly call it out as "single-source claim" and flag for follow-up.
Quotes — include at least one direct quote from a named expert present in the sources (copy verbatim and cite). If none exist, include a verified public statement (press release, blog) as a quote. Do not invent quotes.

III. CITATION & SOURCING RULES:
Inline citation format EXACTLY: (Source: ShortTitle — YYYY-MM-DD — URL)e.g., (Source: CoTracker3 arXiv — 2024-10-15 — https://arxiv.org/...)
At the end include a "Sources" <ul> listing full source entries (title + URL + date + short credibility note).
If you paraphrase any statistic, include the exact location in the source (e.g., "see Table 2, p.6").
For market/financial numbers, prefer SEC filings, company reports, or named market research with publisher and year.

IV. SECTION-SPECIFIC FOCUS (must be explicit in article):
Use the section focus from the input — ensure the article addresses at least TWO focus points (state them explicitly in the text as subheadings).

V. HUMANIZATION / ANTI-AI-PATTERNS (ethical, allowed steps to reduce AI-likeness):
Insert at least two small humanizing details:
a) One short anecdote or concrete example (with source or labeled "illustrative composite").
b) One sentence of personal observation (writer POV), as required in I.3.
Vary sentence rhythm and punctuation: include one parenthetical aside (short), and one comma-spliced sentence (only once) to mimic human style.
Insert at least one small, deliberate stylistic imperfection (not grammatical error): e.g., an interjection "Look," or "Here’s the rub:" — used once, intentionally human.

VI. FORMATTING & SEO:
Use H2 and H3 subheadings for each major point. Keep H2 count between 4–6.
Add one small comparison table (text-only) and 3 bullet "Why it matters" bullets near the top.
Add schema-ready attributes: author name placeholder, datePublished placeholder, and an image alt text line.
Word count: 1500–2000 words. If shorter, flag in 'notes'.

Output JSON ONLY, EXACTLY in this shape:
{{"draftTitle":"...","draftContent":"<html>...full HTML article...</html>","sources":[ {{ "title":"", "url":"", "date":"", "type":"", "credibility":"" }}, ... ],"notes":"List any remaining issues or empty string"}}
"""

PROMPT_C_TEMPLATE = """
C:You are Strategic Editor & SEO consultant for 'AI News Hub'. Input: {json_input} and {knowledge_graph}. Produce a final publishing package with the following exact tasks.

ARTICLE-LEVEL POLISH:
Improve clarity, tighten prose, and ensure "human first" voice remains. Do NOT convert to academic tone.
Add 2–4 textual rich elements: a short comparison table (if none present, create one), 3 bullets "Key takeaways", and 1 highlighted blockquote (choose an existing quote from sources).
Extract one conceptual icon (1–2 English words).
Create author byline and short author bio (40–60 words). Use placeholder if unknown.

**CRITICAL FORMATTING RULES (CSS COMPATIBILITY):**
1. **Key Takeaways:** MUST be wrapped in a div with class 'takeaways-box': `<div class="takeaways-box"><h3>🚀 Key Takeaways</h3><ul>...bullets...</ul></div>`.
2. **Tables:** MUST be wrapped in a div with class 'table-wrapper': `<div class="table-wrapper"><table>...</table></div>`.
3. **Quotes:** Ensure quotes are in `<blockquote>...</blockquote>`.

**IMAGE STRATEGY:**
1. `imageGenPrompt`: Create a specific English prompt for an AI image generator. Rules: Abstract, futuristic, technological style (3D render). NO HUMANS, NO FACES, NO ANIMALS, NO TEXT. Focus on concepts.
2. `imageOverlayText`: A very short, punchy text (2-4 words max) to be written ON the image (e.g., "AI vs Human", "New GPT-5").

NETWORK-LEVEL OPTIMIZATION:
Analyze knowledge_graph array and select 3–5 best internal articles to link.
**STRICT LINKING RULE:** Scan the draft for concepts matching the "title" in the provided database. IF and ONLY IF a match is found, insert a link using the EXACT "url" provided in the database. Format: `<a href="EXACT_URL_FROM_DB">Keyword</a>`. DO NOT invent links.

SEO & PUBLISHING PACKAGE:
Provide metaTitle (50–60 chars) and metaDescription (150–160 chars).
Provide 5–7 tags (exact keywords).
Generate Article schema JSON-LD (fully populated with placeholders for image URL and author URL).
Provide FAQ schema (3 Q&A) optimized for featured snippets (each answer ≤ 40 words).

ADSENSE READINESS & RISK ASSESSMENT:
Run Adsense readiness evaluation and return adsenseReadinessScore from 0–100. Include precise numeric breakdown.

OUTPUT:
Return single JSON ONLY with these fields:
{{"finalTitle":"...","finalContent":"<html>...final polished HTML with inline links and sources...</html>","excerpt":"...short excerpt...","imageGenPrompt":"...","imageOverlayText":"...","seo": {{ "metaTitle":"...","metaDescription":"...","imageAltText":"..." }},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[ "...","..." ],"internalLinks":[ "<a href='...'>...</a>", ... ],"schemaMarkup":"{{...JSON-LD...}}","adsenseReadinessScore":{{ "score":0-100, "breakdown": {{ "accuracy":n, "E-E-A-T":n, "YMYL":n, "adsPlacement":n }}, "notes":"..." }},"sources":[ ... ],"authorBio":{{ "name":"...", "bio":"...", "profileUrl":"..." }}}}
"""

PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Final Audit (UPDATED — includes mandatory A, B, C checks)
You are the Humanization & Final Audit specialist for 'AI News Hub'. Input: {json_input}. Your job: apply a comprehensive, human-level audit and humanization pass, with explicit mandatory checks.

STEP 2 — MANDATORY CHECK A: Sources & Fact Claims
A.1 Numeric claim verification: Verify that at least one source in sources[] contains that exact number.
A.2 Load-bearing claim verification: Ensure two independent credible sources.
A.3 Quote verification: Verify exact text exists in one of the sources.
A.4 Inline citation completeness: Every inline citation must appear in final sources[].

STEP 3 — MANDATORY CHECK B: Human Style
B.1 First-person writer sentence: Ensure presence of exactly one first-person editorial sentence.
B.2 Rhetorical question: Ensure there is one rhetorical question.
B.3 Forbidden phrases: Check that none of the forbidden exact phrases exist ("In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion").
B.4 Sentence length distribution: Short ~40%, Medium ~45%, Long ~15%.
B.6 "AI-pattern sniff" and rewrite: Identify top 8 sentences that most resemble AI-generated prose and rewrite them.

STEP 4 — MANDATORY CHECK C: E-E-A-T & YMYL
C.1 Author bio verification.
C.2 YMYL disclaimer: If riskNote exists, ensure explicit disclaimer in bold.
C.4 AI-detection threshold: If aiProbability > 50, re-run humanization.

STEP 6 — Safety, Legal & Final Editorial Confirmation
Include "humanEditorConfirmation" object.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","imageGenPrompt":"...preserve...","imageOverlayText":"...preserve...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"...","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}},"edits":[ {{"type":"...", "original":"...", "new":"...", "reason":"..."}}...],"auditMetadata": {{ "auditTimestamp":"...", "aiProbability":n, "numberOfHumanizationPasses":n }},"plagiarismFlag": false,"aiDetectionFlag": false,"citationCompleteness": true,"authorBioPresent": true,"humanEditorConfirmation": {{...}},"requiresAction": false, "requiredActions":[...],"notes":"..."}}
"""

PROMPT_E_TEMPLATE = """
E: ROLE PROMPT — "The Publisher"
You are the Publisher. Input: {json_input}.

Your single mission: take the provided draft/final article and transform it into a publication-quality piece.

STEP-BY-STEP WORKFLOW:
1. INPUTS: Read finalContent, sources.
2. SOURCE & FACT VERIFICATION: Final check on numeric claims and quotes.
3. HUMANIZATION & STYLE: Enforce first-person sentence, rhetorical question, remove forbidden phrases ("In today's digital age", etc).
4. SEO & PUBLISHING PACKAGE: Validate meta tags, schema, internal links.
5. FINAL OUTPUT: Return single JSON ONLY.

{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","imageGenPrompt":"...preserve...","imageOverlayText":"...preserve...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio": {{...}},"edits":[...],"auditMetadata": {{...}},"requiredActions":[...]}}
"""

PROMPT_FACEBOOK_HOOK = """
You are a Social Media Manager. Create an engaging Facebook post for this article.
Input:
Title: "{title}"
Category: "{category}"

Rules:
1. Write a short, punchy caption (max 50 words).
2. Use 2-3 emojis relevant to the tech topic.
3. Ask a question to encourage comments.
4. Include 3 relevant hashtags at the end.
5. DO NOT include the article link (system adds it automatically).
6. Output JSON ONLY in this format: {{"facebook": "YOUR_CAPTION_HERE"}}
"""

PROMPT_VIDEO_SCRIPT = """
You are a Screenwriter for a Viral Tech Short. Create a WhatsApp-style chat script between "Alex" and "Sam".
Input Title: "{title}"
Input Summary: "{text_summary}"

Rules:
1. **Goal:** Hook the viewer immediately.
2. **Style:** Casual, fast, like real texting (Use slang like "OMG", "Bro", "Crazy").
3. **Ending:** Must include Call-to-Action: "Link in description for the full story!".
4. **Length:** 20-30 bubbles.

Output JSON ONLY:
[
  {{"speaker": "Alex", "type": "send", "text": "Bro, did you see the news? 🤯"}},
  {{"speaker": "Sam", "type": "receive", "text": "No, what happened?"}},
  ...
]
"""

PROMPT_YOUTUBE_METADATA = """
You are a YouTube SEO Expert.
Input Headline: {draft_title}

Output JSON ONLY:
{{
  "title": "Clickbaity YouTube Title (Max 60 chars)",
  "description": "Engaging description hooks the viewer.",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}
"""

# ==============================================================================
# 3. KEY MANAGER & UTILITIES
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        for i in range(1, 7):
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
            log(f"🔄 Switching to API Key #{self.current_index + 1}...")
            return True
        else:
            log("❌ All API Keys exhausted for today!")
            return False

key_manager = KeyManager()

def clean_json(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: text = match.group(1)
    if text.lower().startswith("json"): text = text[4:].strip()
    return text

def try_parse_json(text, context=""):
    try: return json.loads(text)
    except:
        try:
            # Fix backslashes for escaped paths
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except: 
            log(f"      ❌ JSON Parse Failed in {context}.")
            return None

def get_real_news_rss(query_keywords, category):
    """
    جلب الأخبار الحقيقية باستخدام RSS مع تصفية 'when:1d' لضمان الحداثة
    """
    try:
        query = f"{query_keywords} when:1d"
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        log(f"   📡 Connecting to RSS Feed for: {query_keywords}...")
        feed = feedparser.parse(rss_url)
        
        items = []
        if feed.entries:
            for entry in feed.entries[:7]:
                pub_date = entry.published if 'published' in entry else "Today"
                items.append(f"- Headline: {entry.title}\n  Link: {entry.link}\n  Date: {pub_date}")
            return "\n".join(items)
        else:
            log("   ⚠️ No specific RSS found. Falling back to category search.")
            query = f"{category} technology when:1d"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:3]:
                 items.append(f"- Headline: {entry.title}\n  Link: {entry.link}")
            return "\n".join(items) if items else "No RSS data."
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return "RSS unavailable."

def get_blogger_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    try:
        r = requests.post('https://oauth2.googleapis.com/token', data=payload)
        r.raise_for_status()
        return r.json().get('access_token')
    except Exception as e:
        log(f"❌ Blogger Auth Error: {e}")
        return None

def publish_post(title, content, labels):
    token = get_blogger_token()
    if not token: return None
    
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    data = {"title": title, "content": content, "labels": labels, "status": "LIVE"}
    
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            post_data = r.json()
            real_url = post_data.get('url')
            log(f"✅ Published: {real_url}")
            return real_url
        else:
            log(f"❌ Publish Error: {r.text}")
            return None
    except Exception as e:
        log(f"❌ Publish Connection Error: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        log("⚠️ No IMGBB Key.")
        return None
    
    log(f"   🎨 Generating Image...")
    for attempt in range(3):
        try:
            safe_prompt = requests.utils.quote(f"{prompt_text}, abstract technology, 8k, --no text, humans")
            text_param = ""
            if overlay_text:
                safe_text = requests.utils.quote(overlay_text)
                text_param = f"&text={safe_text}&font=roboto&fontsize=50"

            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,9999)}{text_param}"
            
            img_res = requests.get(url, timeout=45)
            if img_res.status_code != 200:
                time.sleep(3)
                continue
            
            log("   ☁️ Uploading Image...")
            res = requests.post(
                "https://api.imgbb.com/1/upload", 
                data={"key":key, "expiration":0}, 
                files={"image":img_res.content},
                timeout=45
            )
            
            if res.status_code == 200:
                return res.json()['data']['url']
                
        except Exception as e:
            time.sleep(3)
    return None

def load_kg():
    try:
        with open('knowledge_graph.json', 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def get_recent_titles_string(limit=50):
    kg = load_kg()
    return ", ".join([item.get('title','UNKNOWN') for item in kg[-limit:]]) if kg else ""

def get_relevant_kg_for_linking(current_category, limit=60):
    full_kg = load_kg()
    if not full_kg: return "[]"
    rel = [{"title": i['title'], "url": i['url']} for i in full_kg if i.get('section')==current_category][:limit]
    return json.dumps(rel)

def update_kg(title, url, section):
    try:
        data = load_kg()
        for i in data: 
            if i.get('url')==url: return
        data.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
        with open('knowledge_graph.json','w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if not os.path.exists('knowledge_graph.json'): return
        with open('knowledge_graph.json','r') as f: d=json.load(f)
        if len(d) > 800:
            with open('knowledge_graph.json','w') as f: json.dump(d[-400:], f, indent=2)
    except: pass

def generate_step(model_name, prompt, step_name):
    log(f"   👉 Generating: {step_name}...")
    while True:
        current_key = key_manager.get_current_key()
        if not current_key: return None
        client = genai.Client(api_key=current_key)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return clean_json(response.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                if key_manager.switch_key(): continue
                else: return None
            log(f"      ❌ AI Error: {e}")
            return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (RSS + 5-STEP GENERATION)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name', 'models/gemini-2.5-flash')
    cat_config = config['categories'][category]
    
    log(f"\n🚀 STARTING PIPELINE: {category} ({mode})")
    recent_titles = get_recent_titles_string(limit=40)

    # --- STEP 1: RSS RESEARCH ---
    if mode == "trending":
        rss_keys = cat_config.get('trending_focus', category)
        rss_data_str = get_real_news_rss(rss_keys, category)
        
        # Stop if no valid news to avoid hallucinations
        if "No RSS" in rss_data_str:
            log("⚠️ Aborting: No fresh RSS data found today.")
            return

        prompt_a = PROMPT_A_TRENDING.format(
            rss_data=rss_data_str,
            section=category,
            section_focus=rss_keys,
            recent_titles=recent_titles,
            today_date=str(datetime.date.today())
        )
    else:
        prompt_a = PROMPT_A_EVERGREEN.format(
            section=category,
            evergreen_prompt=cat_config.get('evergreen_prompt', ''),
            recent_titles=recent_titles
        )

    json_a_text = generate_step(model, prompt_a, "Step A (Selection)")
    if not json_a_text: return
    time.sleep(5)

    # --- STEP 2: DRAFTING ---
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a_text, forbidden_phrases=", ".join(FORBIDDEN_PHRASES))
    json_b_text = generate_step(model, prompt_b, "Step B (Drafting)")
    if not json_b_text: return
    time.sleep(5)

    # --- STEP 3: SEO ---
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b_text, knowledge_graph=kg_links)
    json_c_text = generate_step(model, prompt_c, "Step C (SEO)")
    if not json_c_text: return
    time.sleep(5)

    # --- STEP 4: AUDIT (RESTORED!) ---
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c_text)
    json_d_text = generate_step(model, prompt_d, "Step D (Audit)")
    if not json_d_text: return
    time.sleep(5)

    # --- STEP 5: FINAL PACKAGE (RESTORED!) ---
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d_text)
    json_e_text = generate_step(model, prompt_e, "Step E (Publisher)")
    if not json_e_text: return

    final_data = try_parse_json(json_e_text, "Final")
    if not final_data: return

    final_title = final_data.get('finalTitle', f"{category} Update")

    # ==============================================================================
    # 🎥 MEDIA
    # ==============================================================================
    video_embed_html = ""
    vid_id_main = None
    vid_id_short = None
    path_video_short = None # for FB Reel

    try:
        content_stripped = re.sub('<[^<]+?>', '', final_data.get('finalContent', ''))[:2000]
        script_raw = generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=final_title, text_summary=content_stripped), "Script")
        
        script = try_parse_json(script_raw)
        if script:
            # Main Video (16:9)
            r1 = video_renderer.VideoRenderer(width=1920, height=1080)
            p1 = r1.render_video(script, final_title, f"main_{int(time.time())}.mp4")
            
            # Short Video (9:16)
            r2 = video_renderer.VideoRenderer(width=1080, height=1920)
            p2 = r2.render_video(script, final_title, f"short_{int(time.time())}.mp4")
            path_video_short = p2
            
            # Metadata
            meta_raw = generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=final_title), "YT Meta")
            meta = try_parse_json(meta_raw) or {"title": final_title, "tags": []}

            # Upload
            if p1:
                vid_id_main, _ = youtube_manager.upload_video_to_youtube(
                    p1, meta.get('title', final_title), "Generated by LatestAI\nLink below!", meta.get('tags', [])
                )
                if vid_id_main:
                    video_embed_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:35px 0;"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_id_main}" frameborder="0" allowfullscreen></iframe></div>'

            if p2:
                 vid_id_short, _ = youtube_manager.upload_video_to_youtube(
                    p2, f"{meta.get('title', final_title)[:90]} #Shorts", "Sub for daily news!", meta.get('tags', [])+['shorts']
                )

    except Exception as e:
        log(f"⚠️ Video Pipeline Error: {e}")

    # ==============================================================================
    # 📝 PUBLISHING
    # ==============================================================================
    content_html = ARTICLE_STYLE
    
    # Image
    img_url = generate_and_upload_image(final_data.get('imageGenPrompt', final_title), final_data.get('imageOverlayText', 'Tech News'))
    if img_url:
        alt = final_data.get('seo', {}).get('imageAltText', final_title)
        content_html += f'<div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;"><a href="{img_url}"><img src="{img_url}" alt="{alt}" /></a></div>'
    
    if video_embed_html: content_html += video_embed_html
    
    content_html += final_data.get('finalContent', '')
    
    # Safe Schema Injection
    if 'schemaMarkup' in final_data:
        try:
            s_dump = json.dumps(final_data['schemaMarkup'])
            content_html += f'\n<script type="application/ld+json">\n{s_dump}\n</script>'
        except: pass
        
    real_link = publish_post(final_title, content_html, [category])
    
    if real_link:
        update_kg(final_title, real_link, category)
        log("✅ Knowledge Graph Saved.")
        
        # Social Updates
        new_desc = f"🚀 READ STORY: {real_link}\n\nDon't forget to Sub!"
        if vid_id_main: youtube_manager.update_video_description(vid_id_main, new_desc)
        if vid_id_short: youtube_manager.update_video_description(vid_id_short, new_desc)
        
        try:
            if path_video_short:
                social_manager.post_reel_to_facebook(path_video_short, f"{final_title} 🔥\n\nFull: {real_link} #Tech")
            elif img_url:
                 fb_cap_raw = generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=final_title, category=category), "FB Caption")
                 fb_cap = try_parse_json(fb_cap_raw).get('facebook', final_title)
                 social_manager.distribute_content(fb_cap, real_link, img_url)
        except Exception as e: log(f"⚠️ Social Error: {e}")

# ==============================================================================
# 6. MAIN (ROULETTE & ANTI-BOT)
# ==============================================================================

def main():
    # 1. Anti-Bot Sleep (1 min to 30 mins)
    sleep_t = random.randint(60, 1800)
    log(f"🕵️‍♂️ Waiting {sleep_t} seconds...")
    time.sleep(sleep_t)

    # 2. Config
    with open('config_advanced.json','r') as f: config = json.load(f)

    # 3. Roulette Selection
    categories = list(config['categories'].keys())
    if not categories: return
    
    selected_cat = random.choice(categories)
    log(f"🎰 Selected Category: '{selected_cat}'")

    # 4. Run One Good Article (Trend Only)
    run_pipeline(selected_cat, config, mode="trending")

    perform_maintenance_cleanup()
    log("✅ Finished.")

if __name__ == "__main__":
    main()
