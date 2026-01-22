import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import feedparser  # Requires: pip install feedparser
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING
# ==============================================================================

# Words that trigger instant audit failure if detected
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
    """Timestamped logger for tracking progress."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING (SEO & UX Optimized)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* Global Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    
    /* SEO-Friendly Headings */
    h2 { color: #111; font-weight: 800; margin-top: 55px; margin-bottom: 25px; border-bottom: 4px solid #f1c40f; padding-bottom: 8px; display: inline-block; font-size: 28px; letter-spacing: -0.5px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 40px; font-size: 24px; }
    
    /* Table of Contents (TOC Box) */
    .toc-box {
        background: #ffffff;
        border: 1px solid #e1e4e8;
        padding: 30px;
        margin: 40px 0;
        border-radius: 12px;
        display: inline-block;
        min-width: 60%;
        box-shadow: 0 8px 16px rgba(0,0,0,0.05);
    }
    .toc-box h3 { margin-top: 0; font-size: 22px; border-bottom: 2px solid #3498db; padding-bottom: 8px; display: inline-block; margin-bottom: 15px; color: #222; }
    .toc-box ul { list-style: none; padding: 0; margin: 0; }
    .toc-box li { margin-bottom: 12px; border-bottom: 1px dashed #f0f0f0; padding-bottom: 8px; padding-left: 20px; position: relative; }
    .toc-box li:before { content: "►"; color: #3498db; position: absolute; left: 0; font-size: 14px; top: 4px; }
    .toc-box a { color: #444; font-weight: 600; font-size: 18px; text-decoration: none; transition: 0.2s; }
    .toc-box a:hover { color: #3498db; padding-left: 8px; }

    /* Comparison Tables */
    .table-wrapper { overflow-x: auto; margin: 45px 0; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.08); border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; font-size: 18px; }
    th { background: #2c3e50; color: #fff; padding: 18px; text-align: left; text-transform: uppercase; font-size: 16px; letter-spacing: 1px; }
    td { padding: 16px 18px; border-bottom: 1px solid #eee; color: #34495e; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    tr:hover { background-color: #e9ecef; transition: 0.3s; }

    /* Key Takeaways Box */
    .takeaways-box {
        background: linear-gradient(135deg, #fdfbf7 0%, #fff 100%);
        border-left: 6px solid #e67e22;
        padding: 30px;
        margin: 40px 0;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    .takeaways-box h3 { margin-top: 0; color: #d35400; font-size: 22px; margin-bottom: 20px; display: flex; align-items: center; }
    .takeaways-box ul { margin: 0; padding-left: 25px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 600; font-size: 18px; color: #222; }

    /* FAQ Schema Section (Visual) */
    .faq-section { margin-top: 70px; border-top: 3px solid #f1f1f1; padding-top: 50px; background: #fffcf5; padding: 40px; border-radius: 20px; }
    .faq-title { font-size: 30px; font-weight: 900; color: #222; margin-bottom: 35px; text-align: center; letter-spacing: -1px; }
    .faq-item { margin-bottom: 25px; border-bottom: 1px solid #f0e6cc; padding-bottom: 20px; }
    .faq-item:last-child { border-bottom: none; }
    .faq-q { font-weight: 700; font-size: 22px; color: #d35400; margin-bottom: 10px; display: block; }
    .faq-a { font-size: 19px; color: #555; line-height: 1.8; }

    /* Images & Quotes */
    .separator { margin: 40px auto; }
    .separator img { border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.12); max-width: 100%; height: auto; display: block; }
    blockquote { background: #ffffff; border-left: 5px solid #f1c40f; margin: 40px 0; padding: 25px 35px; font-style: italic; color: #555; font-size: 1.3em; line-height: 1.6; box-shadow: 0 3px 10px rgba(0,0,0,0.05); }
    
    /* Hyperlinks */
    a { color: #2980b9; text-decoration: none; font-weight: 600; border-bottom: 2px dotted #2980b9; transition: all 0.3s; }
    a:hover { color: #e67e22; border-bottom: 2px solid #e67e22; background-color: #fff8e1; }
</style>
"""

# ==============================================================================
# 2. PROMPTS DEFINITIONS (PASTE AREA)
# ==============================================================================

# 🛑🛑🛑 IMPORTANT 🛑🛑🛑
# Paste the Full, Detailed "Beast Mode" Prompts in the specific variables below.
# Do NOT skip this step.

# ==============================================================================
# 2. PROMPTS DEFINITIONS (FULL, UNABRIDGED, PRODUCTION-GRADE)
# ==============================================================================

# ------------------------------------------------------------------
# PROMPT A: RESEARCH PHASE (Selecting REAL News from RSS)
# ------------------------------------------------------------------
PROMPT_A_TRENDING = """
A: You are a Lead Investigative Tech Reporter for a top-tier technology publication (similar to The Verge, TechCrunch). 
I have fetched the LATEST REAL-TIME headlines from the Google News RSS Feed for the category: "{section}".

INPUT RSS DATA (These are real headlines collected from the last 24 hours):
{rss_data}

SECTION FOCUS KEYWORDS (Use these to strictly filter for relevance):
{section_focus}

**CRITICAL ANTI-DUPLICATION RULE:**
The following topics have ALREADY been covered recently on our blog. DO NOT select them again. You MUST find a completely DIFFERENT, FRESH story from the provided RSS data:
{recent_titles}

YOUR MISSION (Follow Exactly):
1. **Analyze:** Read through the RSS headlines provided in the input.
2. **Select:** Pick EXACTLY ONE high-impact story.
   - **Priority 1:** Official Product Launches / Version Updates / Hardware Releases.
   - **Priority 2:** Significant Funding Rounds (>$20M) or Acquisitions.
   - **Priority 3:** Legal/Ethical Rulings, Lawsuits, or Government Regulations.
   - **Priority 4:** Breakthrough Engineering Papers (SOTA Benchmarks).
   - **IGNORE:** Generic listicles (e.g., "Top 10 AI tools"), weak opinion pieces, speculation, or "What is AI?" introductory articles. Only HARD NEWS.
3. **Synthesize:** Extract the core event, the main entity involved (Company/Researcher), and the date context.

Output JSON only, EXACTLY in this format:
{{
  "headline": "A professional, click-worthy, journalist-style headline based on the chosen RSS item (Do not use colon ':')",
  "original_rss_link": "The specific URL link found in the chosen RSS item for verification",
  "original_rss_title": "The exact title from RSS data",
  "topic_focus": "The specific subject (e.g. Google Gemini 1.5 Pro Release)",
  "why_selected": "Brief reason why this is the most important story in the feed today",
  "date_context": "{today_date}"
}}
"""

# Backup Prompt (Used mainly if RSS fails or manual switch)
PROMPT_A_EVERGREEN = """
A: Expert Technical Educator. 
Task: Outline a comprehensive, authoritative guide about {section}.
Anti-Duplication: Avoid {recent_titles}.

Output JSON ONLY:
{{
  "headline": "Definitive Guide: [Topic] in 2026",
  "original_rss_link": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "topic_focus": "Educational Guide",
  "date_context": "Evergreen"
}}
"""

# ------------------------------------------------------------------
# PROMPT B: WRITER PHASE (Architectural & SEO Drafting)
# ------------------------------------------------------------------
# PROMPT B: Writer Phase (FACTUAL & STRICT)
PROMPT_B_TEMPLATE = """
B: You are the Editor-in-Chief of 'LatestAI'. Write a high-authority news article (approx. 1800 words) based STRICTLY on the facts provided in the Input Data.

INPUT DATA: {json_input}
STRICT FORBIDDEN PHRASES: {forbidden_phrases}

I. ANTI-HALLUCINATION RULES (CRITICAL):
1. **NO FAKE PERSONAS:** Do NOT invent names, doctors, or researchers (e.g. Do not invent 'Dr. Lena Petrova').
2. **Attribution:** If the RSS data does not have a specific quote, attribute statements to "The Company", "Official Documentation", or "Industry Analysts". DO NOT make up quotes.
3. **Product Accuracy:** Use ONLY the product names found in the Input Data. Do not guess version numbers (e.g. don't write 'Spot Cam 3D' unless it is explicitly in the input). Use general terms like "Updated Camera" or "New Sensor" if unsure.

II. ARCHITECTURE FOR SEO DOMINANCE:
1. **Headline (H1):** Use the provided headline.
2. **Introduction:** Hook the reader immediately. State the facts clearly.
3. **The "Direct Answer" (Featured Snippet):** Immediately after the Intro, create an H2 titled "The Bottom Line". Write a 50-word bolded summary of the facts.
4. **Table of Contents:** Insert `[[TOC_PLACEHOLDER]]`.
5. **Deep Dive Sections:** 4-6 H2 sections covering the updates. Use H3 subsections.
6. **Critical Analysis (The Skeptical Take):** Create an H2 titled "Critical Analysis". Discuss potential downsides (price, compatibility, complexity) objectively.
7. **Comparison:** Include a textual data representation comparing this update to the previous version.

III. TONE:
- Professional, Objective, Factual.
- Avoid over-hyping ("Revolutionary", "Miracle"). Use "Significant update", "Major release".

Output JSON ONLY in this exact format:
{{
  "draftTitle": "The Final Headline",
  "draftContent": "<html>... Full HTML Article Content ...</html>",
  "excerpt": "A powerful 2-sentence meta summary.",
  "sources_used": ["List actual companies mentioned"]
}}
"""


# ------------------------------------------------------------------
# PROMPT C: SEO SPECIALIST (Formatting, Schema, Visuals)
# ------------------------------------------------------------------
PROMPT_C_TEMPLATE = """
C: You are the Strategic Editor & SEO Consultant.
INPUT DRAFT: {json_input}
KNOWLEDGE GRAPH LINKS (Internal Links Candidates): {knowledge_graph}

YOUR TASKS (EXECUTE ALL 5 STEPS WITH PRECISION):

1. **TOC Injection & Linking (The Navigator):** 
   - Replace the `[[TOC_PLACEHOLDER]]` marker with a styled HTML div (class="toc-box") containing a title "Quick Navigation" and an unordered list `<ul>` of anchor links to all H2 headings in the article. 
   - **CRITICAL STEP:** You MUST add unique `id` attributes to all the corresponding H2 tags within the `finalContent` so that the TOC links actually work (e.g., convert `<h2>Title</h2>` to `<h2 id="title-id">Title</h2>`).

2. **FAQ Rich Snippets (Visual & Code):** 
   - Extract 3 relevant "User Intent" questions about this news topic. 
   - Create a VISUAL HTML section at the very bottom of the article body (class="faq-section"), formatted nicely with `faq-title`, `faq-q`, and `faq-a` classes.

3. **Styling & Wrappers (The CSS Hooks):** 
   - Wrap the "Key Takeaways" bullet points list in a div with `class="takeaways-box"`. 
   - Wrap any markdown tables converted to HTML in a div with `class="table-wrapper"`.
   - Ensure all Quotes are wrapped in `blockquote` tags.

4. **Internal Linking Strategy:** 
   - Scan the article text for keywords that match the `title` or `topic` in the provided `KNOWLEDGE GRAPH LINKS`. 
   - If a high-confidence match is found, turn that keyword into a hyperlink (`<a href='url'>keyword</a>`). 
   - Strict Limit: Maximum 3 internal links per article to avoid over-optimization (Penalty prevention).

5. **Advanced Schema Generation (The "Graph" Method):** 
   Generate a sophisticated, VALID JSON-LD object containing a graph with TWO distinct nodes:
   - Node 1: `NewsArticle` (including headline, datePublished, author="LatestAI Staff", headline, and image list placeholder).
   - Node 2: `FAQPage` (containing the 3 extracted Questions and Answers from Step 2, using standard Schema.org vocabulary: `mainEntity` -> `Question` -> `acceptedAnswer` -> `Answer`).
   - Ensure the JSON is syntactically perfect and escaped correctly.

Output JSON ONLY:
{{
  "finalTitle": "The refined headline",
  "finalContent": "<html>...The Modified HTML with IDs, Classes, Links, and the Visual FAQ Section appended at the end...</html>",
  "imageGenPrompt": "A highly detailed English prompt for Flux AI image generation (keywords: abstract, tech, 3d render, cinematic lighting, 8k, volumetric, no text)",
  "imageOverlayText": "A very short (2-3 words) catchy text overlay for the thumbnail (e.g. 'GEMINI UPDATED')",
  "seo": {{
      "metaTitle": "SEO Title (Max 60 chars) - Focus on CTR",
      "metaDescription": "SEO Description (Max 155 chars) - Include focus keyword",
      "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
      "imageAltText": "SEO friendly image alt text description"
  }},
  "schemaMarkup": {{ 
      "@context": "https://schema.org", 
      "@graph": [
          {{ "@type": "NewsArticle", "headline": "...", "datePublished": "...", "author": {{ "@type": "Organization", "name": "LatestAI" }} }},
          {{ "@type": "FAQPage", "mainEntity": [ {{ "@type": "Question", "name": "...", "acceptedAnswer": {{ "@type": "Answer", "text": "..." }} }}, ... ] }} 
      ]
  }}
}}
"""

# ------------------------------------------------------------------
# PROMPT D: AUDIT (Quality Assurance & Safety)
# ------------------------------------------------------------------

# PROMPT D: AUDIT (Safety & Fact Check)
PROMPT_D_TEMPLATE = """
PROMPT D — Fact Checker & Auditor
Input: {json_input}

YOUR MISSION: Purge robotic language and hallucinations.

MANDATORY CHECKLIST:
1. **Hallucination Scan:** Check the content for names of people. If a name sounds generic or invented (like 'Dr. Smith', 'Lena Petrova') and is NOT a famous CEO (like Sam Altman, Musk, Sundar Pichai), **REMOVE THE NAME**. Replace with "A spokesperson" or "The developers".
2. **Robotic Word Purge:** Replace words: "Delve", "Tapestry", "Beacon", "Paramount". Use simpler English.
3. **Product Name Safety:** If a specific model number (v3, 5.1) is used, ensure it was present in the context of the article title. If unsure, generalize it.
4. **Formatting Check:** Ensure `id` attributes are in H2 tags for the TOC.

Output JSON ONLY (Structure must match Input C EXACTLY):
{{"finalTitle":"...", "finalContent":"...", "imageGenPrompt":"...", "imageOverlayText":"...", "seo": {{...}}, "schemaMarkup":{{...}}, "sources":[...], "excerpt":"..."}}
"""



# ------------------------------------------------------------------
# PROMPT E: PUBLISHER (Safety Wrapper)
# ------------------------------------------------------------------
PROMPT_E_TEMPLATE = """
E: The Publisher Role.
Your job is to prepare the final JSON payload for the Python publishing script.

CRITICAL INSTRUCTION:
Return VALID JSON only. 
- Do NOT add markdown code blocks (like ```json ... ```). 
- Do NOT add introductory text (like "Here is the JSON"). 
- Do NOT add explanations or footnotes.
Just return the raw JSON object string to prevent pipeline crashes.

Input data to finalize: {json_input}

Output JSON Structure (Strict):
{{"finalTitle":"...", "finalContent":"...", "imageGenPrompt":"...", "imageOverlayText":"...", "seo": {{...}}, "schemaMarkup":{{...}}, "sources":[...], "authorBio": {{...}}}}
"""

# ------------------------------------------------------------------
# VIDEO PROMPTS (Viral & Short Form Scripting)
# ------------------------------------------------------------------
PROMPT_VIDEO_SCRIPT = """
You are a Screenwriter for a viral Tech Channel (TikTok/Reels/Shorts).
Input Title: "{title}"
Input Summary: "{text_summary}"

TASK: Create a dialogue script for a "WhatsApp" style video between 2 characters:
- "Alex" (The Insider/Tech Geek - Uses emoji 🚨).
- "Sam" (The Curious Friend/Skeptic - Uses emoji 🤔).

SCRIPTING RULES:
1. **The Hook (0-3 seconds):** Alex must start with high energy urgency (e.g., "YOO!", "STOP SCROLLING", "DID YOU SEE THIS?").
2. **The Reveal:** Alex explains the main news in simple terms (Explain Like I'm 15).
3. **The Impact:** Sam asks "So what?" or "Is that good?". Alex explains one major benefit or danger.
4. **The CTA (Call to Action):** Alex must end the conversation by saying specifically: "I linked the full breakdown in the description!" or "Link in bio for the full story!".
5. **Length Constraints:** Total of 25 to 35 message bubbles. Keep each bubble short (3-8 words maximum) for fast reading speed on mobile.

Output JSON ONLY in this array format:
[
  {{"speaker": "Alex", "type": "send", "text": "YOO! Did you see the new update? 🚨"}},
  {{"speaker": "Sam", "type": "receive", "text": "No, what happened now? 🤔"}},
  ...
]
"""

# ------------------------------------------------------------------
# SOCIAL PROMPTS (Metadata Optimization)
# ------------------------------------------------------------------
PROMPT_YOUTUBE_METADATA = """
You are a YouTube SEO Expert specialized in Click-Through Rate (CTR).
Input Article Headline: {draft_title}

TASK: Generate High-Performance metadata for a YouTube Video covering this topic.

OUTPUT GUIDELINES:
1. **Title:** Must be clickbaity but truthful. Use ALL CAPS for key words. Include emojis. Max 60 chars. (Example: "GOOGLE Just KILLED ChatGPT? 🤯")
2. **Description:** Start with a 2-sentence strong hook describing the conflict or news. Include 3-4 distinct hashtags related to the tech news.

Output JSON ONLY:
{{
  "title": "Viral YouTube Title Here",
  "description": "Strong hook text. \\n\\n#Tag1 #Tag2 #Tag3",
  "tags": ["tag1", "tag2", "tag3", "tech news", "ai update"]
}}
"""

PROMPT_FACEBOOK_HOOK = """
You are a Social Media Manager. Create a Facebook Post caption for this news.
Input Title: "{title}"

Rules:
1. **Hook:** Start with a polarizing question or a shocking stat related to the news.
2. **Body:** 2 short sentences explaining the core update.
3. **Engagement:** Use 3 relevant emojis to break up text.
4. **Tags:** 3 Hashtags at the end.
5. Do NOT include the link (the system adds it automatically).

Output JSON ONLY:
{{"facebook": "Your caption text here..."}}
"""

# ==============================================================================
# 3. HELPER UTILITIES & CLASSES
# ==============================================================================

class KeyManager:
    """Manages round-robin rotation of multiple Gemini API Keys."""
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
            log(f"🔄 API Quota reached. Switching to Key #{self.current_index + 1}...")
            return True
        else:
            log("❌ FATAL: All API Keys exhausted for today!")
            return False

key_manager = KeyManager()

def clean_json(text):
    """
    NUCLEAR LEVEL JSON CLEANER: 
    Finds the first valid '{' or '[' and the last valid '}' or ']'.
    This prevents 'JSON Parse Failed' crashes caused by AI conversational filler text.
    """
    text = text.strip()
    
    # 1. Try finding Markdown Code blocks first (Most common AI output)
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: 
        text = match.group(1)
    else:
        # Generic code block check
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: text = match.group(1)
    
    # 2. Heuristic extraction of the main JSON object
    # If it looks like an array start
    if text.startswith("[") or (text.find("[") != -1 and text.find("[") < text.find("{")):
        start = text.find('[')
        end = text.rfind(']')
    else:
        # Assuming Object
        start = text.find('{')
        end = text.rfind('}')
    
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    return text.strip()

def try_parse_json(text, context=""):
    """
    Robust Parsing wrapper.
    Attempts strict load, then escape fixing, then logs failure.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Common fix: Escape backslashes that AI often messes up in paths/latex
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except:
            log(f"      ❌ JSON Parse Failed in {context}. The Cleaner could not salvage it.")
            # Log snippet for debug
            log(f"      --> Snippet: {text[:200]}...")
            return None

def get_real_news_rss(query_keywords, category):
    """
    Smart RSS Fetching with Split Strategy.
    Prevents "Empty RSS" results by breaking down comma-separated lists into single targeted queries.
    """
    try:
        # 1. SPLIT STRATEGY: Don't search for "A, B, C" at once. Pick ONE.
        if "," in query_keywords:
            topics_list = [t.strip() for t in query_keywords.split(',') if t.strip()]
            focused_topic = random.choice(topics_list)
            log(f"   🎯 Niche Strategy: Selected sub-topic '{focused_topic}' from category list.")
            
            # Construct strict query
            full_query = f"{focused_topic} when:1d"
        else:
            full_query = f"{query_keywords} when:1d"

        # Encode and fetch
        encoded = urllib.parse.quote(full_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        log(f"   📡 Searching RSS: {full_query}")
        feed = feedparser.parse(url)
        
        items = []
        if feed.entries:
            for entry in feed.entries[:7]:
                pub = entry.published if 'published' in entry else "Today"
                # Clean title source usually at the end
                clean_title = entry.title.split(' - ')[0]
                items.append(f"- Headline: {clean_title}\n  Link: {entry.link}\n  Date: {pub}")
            return "\n".join(items)
        else:
            # 2. FALLBACK STRATEGY: Broad search if niche failed
            log(f"   ⚠️ RSS Empty for '{full_query}'. Switching to Fallback: '{category} news'.")
            fallback_query = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fallback_query)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                items.append(f"- Headline: {entry.title}\n  Link: {entry.link}")
            
            return "\n".join(items) if items else "No RSS data available today."
            
    except Exception as e:
        log(f"❌ RSS System Error: {e}")
        return "RSS Error."

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
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels, "status": "LIVE"}
    
    try:
        r = requests.post(url, headers=headers, json=body)
        if r.status_code == 200:
            link = r.json().get('url')
            log(f"✅ Blog Published: {link}")
            return link
        log(f"❌ Blogger Error: {r.text}")
        return None
    except Exception as e:
        log(f"❌ Blogger Connect Fail: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        log("⚠️ No IMGBB Key.")
        return None
    
    log(f"   🎨 Generating Image (Flux)...")
    for attempt in range(3):
        try:
            # Pollinations.ai Safe Params
            safe_p = urllib.parse.quote(f"{prompt_text}, abstract, technology, 8k, --no text")
            txt_p = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white" if overlay_text else ""
            url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,9999)}{txt_p}"
            
            # Request Image
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                # Upload to ImgBB
                res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if res.status_code == 200:
                    link = res.json()['data']['url']
                    log(f"   ✅ Image URL: {link}")
                    return link
        except Exception as e:
            time.sleep(5)
    return None

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: return json.load(f)
    except: pass
    return []

def get_recent_titles_string(limit=50):
    kg = load_kg()
    if not kg: return "None"
    return ", ".join([i.get('title','') for i in kg[-limit:]])

def get_relevant_kg_for_linking(current_category, limit=60):
    kg = load_kg()
    # Simple semantic match: articles in same category
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==current_category][:limit]
    return json.dumps(links)

def update_kg(title, url, section):
    try:
        data = load_kg()
        for i in data:
            if i['url'] == url: return
        data.append({"title":title, "url":url, "section":section, "date":str(datetime.date.today())})
        with open('knowledge_graph.json','w') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: d=json.load(f)
            # Prune to keep only last 400 entries to prevent prompt token bloat
            if len(d)>800: 
                with open('knowledge_graph.json','w') as f: json.dump(d[-400:], f, indent=2)
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
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            # Send to clean_json to fix potential AI format errors
            return clean_json(r.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                log(f"      ⚠️ Key Quota. Switching...")
                if not key_manager.switch_key(): return None
            else:
                log(f"      ❌ AI Gen Error: {e}")
                return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (FLOW CONTROLLER)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} ({mode})")
    recent = get_recent_titles_string()

    # 1. RSS
    rss_str = get_real_news_rss(cat_conf.get('trending_focus',''), category)
    if "No RSS" in rss_str:
        log("❌ Pipeline Stop: No relevant news found in RSS.")
        return

    # 2. Step A: Research
    prompt_a = PROMPT_A_TRENDING.format(rss_data=rss_str, section=category, section_focus=cat_conf['trending_focus'], recent_titles=recent, today_date=str(datetime.date.today()))
    json_a_raw = generate_step(model, prompt_a, "Step A (Research)")
    if not json_a_raw: return
    json_a = try_parse_json(json_a_raw, "A")
    if not json_a: return
    log(f"   🗞️ Topic: {json_a.get('headline')}")
    time.sleep(5)

    # 3. Step B: Writer
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a_raw, forbidden_phrases=str(FORBIDDEN_PHRASES))
    json_b_raw = generate_step(model, prompt_b, "Step B (Drafting)")
    if not json_b_raw: return
    time.sleep(5)

    # 4. Step C: Format & SEO
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b_raw, knowledge_graph=kg_links)
    json_c_raw = generate_step(model, prompt_c, "Step C (Formatting)")
    if not json_c_raw: return
    time.sleep(5)

    # 5. Step D: Audit
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c_raw)
    json_d_raw = generate_step(model, prompt_d, "Step D (Audit)")
    if not json_d_raw: return
    time.sleep(5)

    # 6. Step E: Publish Prep
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d_raw)
    json_e_raw = generate_step(model, prompt_e, "Step E (Final)")
    final_data = try_parse_json(json_e_raw, "E")
    
    # SAFETY: Check if final_data exists, if E fails, try falling back to D
    if not final_data:
        log("⚠️ Step E Failed parsing. Falling back to Step D result.")
        final_data = try_parse_json(json_d_raw, "Fallback D")
        if not final_data: return

    title = final_data.get('finalTitle', f"{category} Update")

    # =======================================================
    # 🎥 SOCIAL MEDIA & METADATA PREP (FIXED: HOOKS FIRST)
    # =======================================================
    log("   🧠 Generating Social Hooks & Descriptions...")
    
    # A. YouTube Metadata (Before video creation, to have proper Desc)
    yt_meta_raw = generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Metadata")
    yt_meta = try_parse_json(yt_meta_raw) or {"title": title, "description": f"{title} news update.", "tags": []}
    
    # B. Facebook Hook (Independent Generation)
    fb_hook_raw = generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Caption")
    fb_data = try_parse_json(fb_hook_raw)
    # This captures the engaging caption
    fb_caption = fb_data.get('facebook', title) if fb_data else title

    # ==========================
    # 🎬 VIDEO GENERATION
    # ==========================
    video_html_embed = ""
    vid_id_main = None
    vid_id_short = None
    vid_path_fb = None # Path for FB Reel
    
    try:
        # Script
        summ = re.sub('<[^<]+?>', '', final_data.get('finalContent', ''))[:1500]
        script_raw = generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
        script = try_parse_json(script_raw)
        
        if script:
            rr = video_renderer.VideoRenderer()
            
            # --- 1. LANDSCAPE VIDEO (Main) ---
            path_main = rr.render_video(script, title, f"main_{int(time.time())}.mp4")
            if path_main:
                # Use AI-Generated Description IMMEDIATELY
                # Add placeholder link text
                full_yt_desc = f"{yt_meta['description']}\n\n👉 Full Story Link in Comments/Desc soon!\n\n#LatestAI #TechNews"
                
                vid_id_main, _ = youtube_manager.upload_video_to_youtube(
                    path_main, 
                    yt_meta.get('title', title)[:100], 
                    full_yt_desc, 
                    yt_meta.get('tags', [])
                )
                if vid_id_main:
                    # Blog Embed Code
                    video_html_embed = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_id_main}" frameborder="0" allowfullscreen></iframe></div>'
            
            # --- 2. PORTRAIT VIDEO (Shorts) ---
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            path_short = rs.render_video(script, title, f"short_{int(time.time())}.mp4")
            vid_path_fb = path_short # Save for FB Reel later
            
            if path_short:
                short_title = f"{yt_meta.get('title', title)[:90]} #Shorts"
                vid_id_short, _ = youtube_manager.upload_video_to_youtube(
                    path_short, 
                    short_title, 
                    full_yt_desc, # Same rich description
                    yt_meta.get('tags', []) + ["shorts"]
                )
            
    except Exception as e:
        log(f"⚠️ Video Generation Error: {e}")

    # ==========================
    # 📝 BLOG PUBLISHING
    # ==========================
    html_body = ARTICLE_STYLE
    
    # Header Image
    img = generate_and_upload_image(final_data.get('imageGenPrompt', title), final_data.get('imageOverlayText', 'News'))
    if img: 
        alt = final_data.get('seo', {}).get('imageAltText', title)
        html_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{alt}" /></a></div>'
    
    # Video
    if video_html_embed: 
        html_body += video_html_embed
        
    # Text Content
    html_body += final_data.get('finalContent', '')
    
    # Schema
    if 'schemaMarkup' in final_data:
        try: html_body += f'\n<script type="application/ld+json">\n{json.dumps(final_data["schemaMarkup"])}\n</script>'
        except: pass
        
    # Publish!
    url = publish_post(title, html_body, [category])
    
    if url:
        update_kg(title, url, category)
        
        # ===============================================
        # 🔄 POST-DISTRIBUTION (UPDATE & DOUBLE POST)
        # ===============================================
        
        # 1. Update YouTube Descriptions (Append Real Link)
        update_text = f"\n\n🔥 READ FULL STORY: {url}"
        if vid_id_main: 
            # Note: We append to the existing rich desc logic handled in manager
            youtube_manager.update_video_description(vid_id_main, update_text) 
        if vid_id_short: 
            youtube_manager.update_video_description(vid_id_short, update_text)
        
        # 2. FACEBOOK STRATEGY (DUAL POSTING)
        try:
            # A. Reel Upload (If video exists)
            if vid_path_fb:
                log("   🚀 Uploading FB Reel...")
                # Reel Description = Caption + Link + Tags
                reel_desc = f"{fb_caption}\n\n📲 Link: {url}\n\n#Reels #Tech #AI"
                social_manager.post_reel_to_facebook(vid_path_fb, reel_desc)
                time.sleep(15) # Safety buffer between posts
            
            # B. Standard Photo Post (Always)
            if img:
                log("   🚀 Posting FB Photo Link...")
                # Post Description = Caption + Link + Clean breakdown
                post_desc = f"{fb_caption}\n\n👇 FULL BREAKDOWN:\n{url}"
                social_manager.distribute_content(post_desc, url, img)
                
        except Exception as e: 
            log(f"⚠️ Social Dist Error: {e}")

# ==============================================================================
# 7. MAIN
# ==============================================================================

def main():
    # Removed Wait time (Relies on Workflow Scheduler)
    
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ Config file missing.")
        return
        
    # Random Category Selection (Roulette)
    cat = random.choice(list(cfg['categories'].keys()))
    run_pipeline(cat, cfg, mode="trending")
    perform_maintenance_cleanup()
    log("✅ End.")

if __name__ == "__main__":
    main()
