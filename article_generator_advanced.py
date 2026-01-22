import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import feedparser  # تأكد من وجود هذه المكتبة في requirements.txt
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING & HUMANIZATION RULES
# ==============================================================================

# القائمة السوداء الصارمة (لضمان أسلوب بشري)
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
# 1. CSS STYLING (THE BEAST MODE SEO STYLE)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* Base Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    
    /* Headers (SEO Friendly) */
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
# 2. PROMPTS DEFINITIONS
# ==============================================================================

# 🛑🛑🛑 IMPORTANT: PASTE THE FULL PROMPTS (A, B, C, D, E, VIDEO, SOCIAL) HERE 🛑🛑🛑
# قم بلصق البرومبتات التفصيلية التي أعطيتك إياها سابقاً في هذا المكان بالضبط
# DO NOT leave them empty. Use the specific "Beast Mode" strings I provided.

PROMPT_A_TRENDING = """ """ # الصق هنا
PROMPT_A_EVERGREEN = """ """ # الصق هنا
PROMPT_B_TEMPLATE = """ """ # الصق هنا
PROMPT_C_TEMPLATE = """ """ # الصق هنا
PROMPT_D_TEMPLATE = """ """ # الصق هنا
PROMPT_E_TEMPLATE = """ """ # الصق هنا
PROMPT_VIDEO_SCRIPT = """ """ # الصق هنا
PROMPT_YOUTUBE_METADATA = """ """ # الصق هنا
PROMPT_FACEBOOK_HOOK = """ """ # الصق هنا

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
PROMPT_B_TEMPLATE = """
B: You are the Editor-in-Chief of 'LatestAI'. Your task is to write a polished, high-authority news article (approx. 1800-2000 words) based on the research provided.

INPUT DATA: {json_input}
STRICT FORBIDDEN PHRASES (Instant Failure if any of these are found in your output): 
{forbidden_phrases}

I. ARCHITECTURE FOR SEO DOMINANCE (You MUST follow this structure step-by-step):
1. **Headline (H1):** Use the provided headline (or improve it slightly for Click-Through Rate, but keep it factual).
2. **Introduction:** Hook the reader immediately (in media res). State the "News Event" clearly in the first paragraph.
3. **The "Direct Answer" Paragraph (FEATURED SNIPPET TRAP):** Immediately after the Introduction, create an H2 titled "The Bottom Line". Under it, write a concise, bolded, 50-word summary of WHAT happened and WHY it matters. This specifically helps us rank for Google's featured snippets (Zero Position).
4. **Table of Contents Placeholder:** Insert EXACTLY this string here: `[[TOC_PLACEHOLDER]]`. Do not generate the TOC yourself; just place this marker. We will inject the code programmatically later.
5. **Deep Dive Sections (The Meat):** Write 4 to 6 H2 sections covering Technical Details, Market Impact, and Performance Benchmarks. You MUST use H3 subsections liberally to break up long text blocks.
6. **The Skeptical Take (Critical Authority - Mandatory):** Create an H2 titled "The Challenges" or "Critical Analysis". You MUST criticize the news slightly or highlight potential risks (e.g., high costs, data privacy concerns, technical limitations, or hype vs. reality). This builds trust with the reader (E-E-A-T factors).
7. **Comparison Data:** Include a textual data representation or Markdown table comparing this new development to its predecessor or main competitor (e.g. Model A vs Model B).

II. STYLE & TONE GUIDELINES:
- **Tone:** Professional yet accessible (Grade 10 reading level). Be objective but slightly cynical (avoid over-hyping everything like a press release).
- **Perspective:** Use collective pronouns like "We believe", "Our analysis suggests", or "In our view" to simulate an expert editorial team.
- **Formatting:** Use **Bold** for key stats, numbers, prices, and entity names. Use bullet points or numbered lists in almost every section to ensure readability (Skimmability).

III. CITATION & SOURCING:
- Quote a source provided in the context or a simulated public statement from the company spokesperson to add weight.
- Refer to "Recent reports" or "Official documentation".

Output JSON ONLY in this exact format (ensure JSON string encoding is valid):
{{
  "draftTitle": "The Final Headline",
  "draftContent": "<html>... Full HTML Article Content (with H2, H3, p, ul, strong, table tags) ...</html>",
  "excerpt": "A powerful 2-sentence meta summary (approx 150 chars).",
  "sources_used": ["List of entities or companies mentioned"]
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
PROMPT_D_TEMPLATE = """
PROMPT D — Final Humanization & Safety Audit
Input: {json_input}

YOUR MISSION is to act as the Quality Control Officer. Do not change the meaning of the content, but you MUST fix the style.

MANDATORY CHECKLIST:
1. **Robotic Word Purge (Strict):** Scan the `finalContent` HTML. If you find any of these specific words (which AI overuse), replace them with simpler, grittier English synonyms: 
   - Replace "Delve" with "Explore" or "Look into".
   - Replace "Realm" with "Field" or "Area".
   - Replace "Tapestry" with "System" or "Complex mix".
   - Replace "Game-changer" with "Significant update" or "Big deal".
   - Replace "Poised to" with "Set to" or "Ready to".
   - Remove "In conclusion" or "To sum up" entirely.

2. **Formatting Logic Check:** 
   - Verify that H2 tags have `id` attributes assigned. 
   - Verify that the `toc-box` div exists.
   - Verify that the `faq-section` div exists at the bottom.

3. **Schema Integrity:** Verify that `schemaMarkup` is valid JSON structure and matches the article content.

4. **Author Bio Check:** If the content is missing an author sign-off, append a small paragraph `<p><em>Reporting by LatestAI Staff.</em></p>` at the very end of the HTML.

Output JSON ONLY (Structure must match Input C EXACTLY, preserving all fields like seo, tags, prompts, etc. Do not lose any data):
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
# 3. HELPER FUNCTIONS & CLASSES
# ==============================================================================

class KeyManager:
    """Manages rotation of Gemini API Keys."""
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
            log(f"🔄 Quota Hit. Switching to API Key #{self.current_index + 1}...")
            return True
        else:
            log("❌ FATAL: All API Keys exhausted for today!")
            return False

key_manager = KeyManager()

def clean_json(text):
    """
    NUCLEAR LEVEL CLEANER: Removes everything not strictly inside the outer brackets.
    Solves the 'JSON Parse Failed' error decisively.
    """
    text = text.strip()
    
    # 1. Try finding Markdown Code blocks first
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: 
        text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: 
            text = match.group(1)
    
    # 2. Last Resort: Find first '{' or '[' and last '}' or ']'
    # Detect if array or object
    if text.startswith("[") or (text.find("[") != -1 and text.find("[") < text.find("{")):
        start = text.find('[')
        end = text.rfind(']')
    else:
        start = text.find('{')
        end = text.rfind('}')
    
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    return text.strip()

def try_parse_json(text, context=""):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Fix backslashes and Common Errors
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except:
            log(f"      ❌ JSON Parse Failed in {context}. (Cleaner could not salvage)")
            # Log the problematic text snippet for debugging (first 100 chars)
            log(f"      --> Snippet: {text[:100]}...")
            return None

def get_real_news_rss(query_keywords, category):
    """
    Fetches news via RSS with 24-hour filter. 
    Improved logic for 'No specific RSS found' warning.
    """
    try:
        # Use full keyword list, force "when:1d"
        encoded = urllib.parse.quote(f"{query_keywords} when:1d")
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        log(f"   📡 Searching RSS: {query_keywords[:50]}...")
        feed = feedparser.parse(url)
        
        items = []
        if feed.entries:
            for entry in feed.entries[:7]:
                pub = entry.published if 'published' in entry else "Today"
                # Strip source title usually at end e.g. "... - TechCrunch"
                clean_title = entry.title.split(' - ')[0]
                items.append(f"- Headline: {clean_title}\n  Link: {entry.link}\n  Date: {pub}")
            return "\n".join(items)
        else:
            log("   ⚠️ RSS Empty. Switching to Fallback: 'Technology' Category search.")
            # Fallback: Less strict search
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
    
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels, "status": "LIVE"}
    
    try:
        r = requests.post(url, headers=headers, json=body)
        if r.status_code == 200:
            link = r.json().get('url')
            log(f"✅ Published: {link}")
            return link
        log(f"❌ Publish Error: {r.text}")
        return None
    except Exception as e:
        log(f"❌ Publish Exception: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        log("⚠️ No IMGBB Key.")
        return None
    
    log(f"   🎨 Generating Image (Flux)...")
    for attempt in range(3):
        try:
            # Enhanced Safe Prompt
            safe_p = urllib.parse.quote(f"{prompt_text}, abstract, technology, 8k, --no text, no watermark")
            text_param = ""
            if overlay_text:
                text_param = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white"
            
            url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,99999)}{text_param}"
            
            r = requests.get(url, timeout=50)
            if r.status_code == 200:
                up_res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if up_res.status_code == 200:
                    link = up_res.json()['data']['url']
                    log(f"   ✅ Image: {link}")
                    return link
        except: time.sleep(2)
    return None

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r', encoding='utf-8') as f: return json.load(f)
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
            if i['url'] == url: return
        data.append({"title":title, "url":url, "section":section, "date":str(datetime.date.today())})
        with open('knowledge_graph.json','w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: d=json.load(f)
            if len(d)>800: 
                with open('knowledge_graph.json','w') as f: json.dump(d[-400:], f, indent=2)
    except: pass

def generate_step(model, prompt, step):
    log(f"   👉 Generating: {step}")
    while True:
        key = key_manager.get_current_key()
        if not key: 
            log("❌ FATAL: No keys.")
            return None
        client = genai.Client(api_key=key)
        try:
            r = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            # The critical Fix: Clean the response text before parsing
            cleaned_text = clean_json(r.text)
            return cleaned_text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                log(f"      ⚠️ Key switch...")
                if not key_manager.switch_key(): return None
            else:
                log(f"      ❌ AI Error: {e}")
                return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (THE MASTER FUNCTION)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} ({mode})")
    recent = get_recent_titles_string()

    # 1. RSS
    rss_str = get_real_news_rss(cat_conf.get('trending_focus',''), category)
    if "No RSS" in rss_str:
        log("❌ NO NEWS FOUND. Stopping to preserve quality.")
        return

    # 2. Step A (Research)
    prompt_a = PROMPT_A_TRENDING.format(rss_data=rss_str, section=category, section_focus=cat_conf['trending_focus'], recent_titles=recent, today_date=str(datetime.date.today()))
    json_a_txt = generate_step(model, prompt_a, "Step A (Research)")
    if not json_a_txt: return
    json_a = try_parse_json(json_a_txt, "A")
    if not json_a: return
    log(f"   🗞️ Topic: {json_a.get('headline')}")
    time.sleep(5)

    # 3. Step B (Draft)
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a_txt, forbidden_phrases=str(FORBIDDEN_PHRASES))
    json_b_txt = generate_step(model, prompt_b, "Step B (Writer)")
    if not json_b_txt: return
    time.sleep(5)

    # 4. Step C (Format)
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b_txt, knowledge_graph=kg_links)
    json_c_txt = generate_step(model, prompt_c, "Step C (SEO)")
    if not json_c_txt: return
    time.sleep(5)

    # 5. Step D (Audit)
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c_txt)
    json_d_txt = generate_step(model, prompt_d, "Step D (Audit)")
    if not json_d_txt: return
    time.sleep(5)

    # 6. Step E (Publish Prep) - Safety Critical Step
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d_txt)
    json_e_txt = generate_step(model, prompt_e, "Step E (Publisher)")
    if not json_e_txt: 
        log("❌ Step E Failed (Empty Response)")
        return
        
    final_data = try_parse_json(json_e_txt, "E")
    if not final_data: 
        log("❌ Step E Parsing Failed (Invalid JSON)")
        return

    title = final_data.get('finalTitle', f"{category} Update")

    # ==========================
    # 🎥 MEDIA
    # ==========================
    video_html = ""
    vid_id_main = None
    vid_id_short = None
    vid_path_fb = None
    
    try:
        summ = re.sub('<[^<]+?>', '', final_data.get('finalContent', ''))[:2000]
        script_raw = generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
        script = try_parse_json(script_raw)
        
        if script:
            rr = video_renderer.VideoRenderer(width=1920, height=1080) # Main Init
            
            # Landscape
            pm = rr.render_video(script, title, f"main_{int(time.time())}.mp4")
            if pm:
                vid_id_main, _ = youtube_manager.upload_video_to_youtube(pm, title, "Full Article Linked 👇", ["ai"])
                if vid_id_main:
                    video_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_id_main}" frameborder="0" allowfullscreen></iframe></div>'
            
            # Short
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            ps = rs.render_video(script, title, f"short_{int(time.time())}.mp4")
            vid_path_fb = ps
            if ps: vid_id_short, _ = youtube_manager.upload_video_to_youtube(ps, title+" #Shorts", "Subscribe!", ["shorts"])
            
    except Exception as e:
        log(f"⚠️ Video Error: {e}")

    # ==========================
    # 📝 PUBLISH
    # ==========================
    html_body = ARTICLE_STYLE
    img = generate_and_upload_image(final_data.get('imageGenPrompt', title), final_data.get('imageOverlayText', 'News'))
    
    if img: 
        alt = final_data['seo']['imageAltText']
        html_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{alt}" /></a></div>'
    
    if video_html: html_body += video_html
    html_body += final_data.get('finalContent', '')
    
    # Schema Injection
    if 'schemaMarkup' in final_data:
        try: html_body += f'\n<script type="application/ld+json">\n{json.dumps(final_data["schemaMarkup"])}\n</script>'
        except: pass
        
    url = publish_post(title, html_body, [category])
    
    if url:
        update_kg(title, url, category)
        
        # Updates
        desc = f"🚀 READ HERE: {url}\n\nDon't forget to Subscribe!"
        if vid_id_main: youtube_manager.update_video_description(vid_id_main, desc)
        if vid_id_short: youtube_manager.update_video_description(vid_id_short, f"Read: {url}")
        
        # Social
        try:
            if vid_path_fb: social_manager.post_reel_to_facebook(vid_path_fb, f"{title} 🔥\n{url}")
            elif img:
                fb_raw = generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title), "FB")
                fb = try_parse_json(fb_raw).get('facebook', title)
                social_manager.distribute_content(fb, url, img)
        except: pass

# ==============================================================================
# 6. MAIN
# ==============================================================================

def main():
    wait = random.randint(01, 10) # Anti-bot 1-30 min
    log(f"⏰ Anti-Bot: Waiting {wait} seconds...")
    time.sleep(wait)
    
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ Config file missing.")
        return
        
    cat = random.choice(list(cfg['categories'].keys()))
    run_pipeline(cat, cfg, mode="trending")
    perform_maintenance_cleanup()
    log("✅ End.")

if __name__ == "__main__":
    main()
