import os
import json
import time
import requests
import re
import random
import sys
import datetime
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. LOGGING HELPER
# ==============================================================================
def log(msg):
    print(msg, flush=True)

# ==============================================================================
# 1. CSS STYLING (MODERN TECH LOOK)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* General Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #2c3e50; font-size: 18px; }
    h2 { color: #1a252f; font-weight: 700; margin-top: 40px; margin-bottom: 20px; border-bottom: 2px solid #3498db; padding-bottom: 10px; display: inline-block; }
    h3 { color: #2980b9; font-weight: 600; margin-top: 30px; }
    
    /* Key Takeaways Box */
    .takeaways-box {
        background: #f0f8ff;
        border-left: 5px solid #3498db;
        padding: 20px;
        margin: 30px 0;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .takeaways-box h3 { margin-top: 0; color: #2c3e50; }
    .takeaways-box ul { margin-bottom: 0; padding-left: 20px; }
    .takeaways-box li { margin-bottom: 10px; }

    /* Tables */
    .table-wrapper { overflow-x: auto; margin: 30px 0; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
    table { width: 100%; border-collapse: collapse; background: #fff; }
    th { background: #34495e; color: #fff; padding: 15px; text-align: left; }
    td { padding: 12px 15px; border-bottom: 1px solid #eee; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    tr:hover { background-color: #f1f1f1; }

    /* Blockquotes */
    blockquote {
        background: #fff;
        border-left: 5px solid #e74c3c;
        margin: 30px 0;
        padding: 20px 30px;
        font-style: italic;
        color: #555;
        font-size: 1.1em;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* Links */
    a { color: #3498db; text-decoration: none; font-weight: 500; transition: color 0.3s; }
    a:hover { color: #2980b9; text-decoration: underline; }
    
    /* Images */
    .separator img { border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.15); max-width: 100%; height: auto; }
    
    /* Sources Section */
    .sources-section { background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 0.9em; color: #666; margin-top: 50px; }
</style>
"""

# ==============================================================================
# 2. PROMPTS DEFINITIONS (FULL VERSIONS)
# ==============================================================================

PROMPT_A_TRENDING = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index (Google Search, Google Scholar, arXiv, official blogs, SEC/10-Q when financial figures are used) for one specific, high-impact case, study, deployment, or company announcement that occurred within {date_range} (for example "last 60 days").

SECTION FOCUS (choose the relevant focus for {section}; these must guide your search terms):
{section_focus}

**CRITICAL ANTI-DUPLICATION RULE:**
The following topics have already been covered recently. DO NOT write about them again. Find a DIFFERENT story:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES (follow EXACTLY):

Return exactly one headline (plain English, single line) — a journalist-style headline that connects technical advance to human/commercial impact.

Provide 2–3 primary sources that verify the story. At least:
One PRIMARY TECH SOURCE: (peer-reviewed DOI or arXiv paper with version/date OR official GitHub repo with commit/PR date OR official company technical blog post).
One SECONDARY CORROBORATING SOURCE: (reputable news outlet, conference proceeding, or company press release).

For each source, include:
title, exact URL, publication date (YYYY-MM-DD), type (paper/blog/repo/press/SEC), and a one-line note: "why it verifies".

For any numeric claim you will later assert (e.g., "88% of queries"), ensure the source actually contains that number. If the source gives a figure differently, report the exact figure and location of the figure in the source (e.g., "see Figure 2, page 6" or "arXiv v2, paragraph 3").

If the story touches YMYL topics (health/finance/legal), include an immediate risk note listing which regulations may apply (e.g., HIPAA, FDA, CE, GDPR, SEC) and what kind of verification is required.

Check basic credibility signals for each source and report them: (a) publisher credibility (Nature/IEEE/ACM/official corp blog), (b) if arXiv — indicate whether paper has code/benchmarks, (c) if GitHub — include last commit date and license, (d) if press release — confirm corporate domain and date/time.

Output JSON only, EXACTLY in this format:
{{"headline": "One-line headline","sources": [{{"title":"Exact source title","url":"https://...","date":"YYYY-MM-DD","type":"paper|arXiv|repo|blog|press|SEC","why":"One-line why this verifies (include exact page/figure if relevant)","credibility":"short note: Nature/IEEE/company blog/press/etc","notes":"any caveats about the source"}}],"riskNote":"If YMYL risk exists list regulators and verification steps; otherwise empty string"}}
"""

PROMPT_A_EVERGREEN = """
A:You are an expert technical educator specialized in {section}. Your task is to outline a comprehensive "Ultimate Guide" or "Deep Dive" into a core concept of {section}.
Instead of recent news, search for and cite: Foundational papers, Standard definitions, Official Documentation, and Key Textbooks.

TOPIC PROMPT: {evergreen_prompt}

**CRITICAL ANTI-DUPLICATION RULE:**
Check the following list of existing guides. Ensure your angle or specific topic is DISTINCT or an UPDATE:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return a headline like "The Ultimate Guide to [Topic]" or "Understanding [Concept]: A Deep Dive".
2. Provide 2–3 authoritative sources (Seminal Papers, Documentation, University Lectures).
3. Output JSON ONLY (Same format as news to maintain pipeline compatibility):
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"YYYY-MM-DD (or N/A)", "type":"documentation|paper|book", "why":"Foundational reference", "credibility":"High"}}], "riskNote":"..."}}
"""

PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A (headline + sources). Write a polished HTML article (1500–2000 words) using the provided headline and sources. Follow these rules exactly.
INPUT: {json_input}

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

Avoid AI-template phrasing: forbid the following exact phrases (do not use them anywhere):
"In today's digital age"
"The world of AI is ever-evolving"
"This matters because" — instead use 1–2 human sentences that explain significance.
"In conclusion" (use a forward-looking takeaway instead).

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

# --- UPDATED VIDEO PROMPT (COMPREHENSIVE & SHORT BURSTS) ---
PROMPT_VIDEO_SCRIPT = """
You are a Screenwriter. Create a WhatsApp-style chat script between two friends (Alex & Sam) discussing this news.

INPUT HEADLINE: "{title}"
INPUT SUMMARY: "{text_summary}"

Rules:
1. **GOAL:** The chat must cover the ENTIRE article content (Intro, Key Details, Why it matters, Conclusion). It should replace reading the article.
2. **STYLE:** Casual, fast, like real texting. Use slang like "OMG", "No way", "Seriously?".
3. **FORMAT:** Short bubbles. Max 6-8 words per bubble.
4. **SPLITTING:** Split long explanations into 3-4 consecutive bubbles from the same speaker. NEVER write a long paragraph.
5. **LENGTH:** 30-50 bubbles total (Comprehensive coverage).
6. **LANGUAGE:** English Only.
7. Output JSON ONLY:
[
  {{"speaker": "Alex", "type": "send", "text": "Bro did u see the news?"}},
  {{"speaker": "Alex", "type": "send", "text": "NVIDIA just dropped a bomb 🤯"}},
  {{"speaker": "Sam", "type": "receive", "text": "No what happened??"}},
  {{"speaker": "Sam", "type": "receive", "text": "Tell me everything!"}},
  {{"speaker": "Alex", "type": "send", "text": "Okay so basically..."}},
  {{"speaker": "Alex", "type": "send", "text": "They released a new chip."}}
]
"""

PROMPT_YOUTUBE_METADATA = """
You are a YouTube SEO Expert. Based on this specific headline, generate metadata.
Input Headline: {draft_title}

Output JSON ONLY:
{{
  "title": "Catchy YouTube Title (Max 60 chars) - Must relate to {draft_title}",
  "description": "Engaging description (first 2 lines hook), includes keywords.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}
"""

# ==============================================================================
# 3. KEY MANAGER
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

# ==============================================================================
# 4. HELPER FUNCTIONS
# ==============================================================================

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
    """Publishes to Blogger and returns the ACTUAL URL."""
    token = get_blogger_token()
    if not token: return None
    
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"title": title, "content": content, "labels": labels}
    
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            post_data = r.json()
            real_url = post_data.get('url')
            log(f"✅ Published: {title} -> {real_url}")
            return real_url
        else:
            log(f"❌ Publish Error: {r.text}")
            return None
    except Exception as e:
        log(f"❌ Connection Error: {e}")
        return None

def clean_json(text):
    """Cleans JSON string from Markdown and common errors."""
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: 
        text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: 
            text = match.group(1)
    
    if text.lower().startswith("json"):
        text = text[4:].strip()

    return text

def try_parse_json(text, context=""):
    """Robust JSON parsing with multiple fallback strategies."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            try:
                return json.loads(text[:e.pos])
            except: pass
        pass

    try:
        fixed_text = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass

    try:
        fixed_text = text.replace('\\', '\\\\')
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass

    try:
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match: return json.loads(match.group(1))
    except: pass

    try:
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return json.loads(match.group(1))
    except: pass

    log(f"      ❌ JSON Parse Failed in {context}.")
    return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        log("⚠️ No IMGBB_API_KEY found.")
        return None
    
    log(f"   🎨 Generating Image: '{prompt_text}'...")
    
    for attempt in range(3):
        try:
            safe_prompt = requests.utils.quote(f"{prompt_text}, abstract, futuristic, 3d render, high quality, --no people, humans, animals, faces")
            text_param = ""
            if overlay_text:
                safe_text = requests.utils.quote(overlay_text)
                text_param = f"&text={safe_text}&font=roboto&fontsize=50"

            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologo=true&seed={random.randint(1,99999)}&model=flux{text_param}"
            
            img_response = requests.get(url, timeout=45)
            if img_response.status_code != 200:
                time.sleep(5)
                continue
            
            log("   ☁️ Uploading to ImgBB...")
            res = requests.post(
                "https://api.imgbb.com/1/upload", 
                data={"key":key, "expiration":0}, 
                files={"image":img_response.content},
                timeout=45
            )
            
            if res.status_code == 200:
                direct_link = res.json()['data']['url']
                log(f"   ✅ Image Ready: {direct_link}")
                return direct_link
                
        except Exception as e:
            time.sleep(5)
            
    log("❌ Failed to generate/upload image after 3 attempts.")
    return None

def load_kg():
    try:
        with open('knowledge_graph.json', 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def get_recent_titles_string(limit=50):
    kg = load_kg()
    titles = [item['title'] for item in kg[-limit:]] if kg else []
    return ", ".join(titles)

def get_relevant_kg_for_linking(current_category, limit=60):
    full_kg = load_kg()
    if not full_kg: return "[]"
    
    relevant = [item for item in full_kg if item.get('section') == current_category]
    guides = [item for item in full_kg if "Guide" in item.get('title', '') and item.get('section') != current_category]
    
    combined = relevant + guides[:10]
    if len(combined) > limit: combined = combined[-limit:]
    
    simplified = [{"title": item['title'], "url": item['url']} for item in combined if 'url' in item]
    return json.dumps(simplified)

def update_kg(title, url, section):
    try:
        data = load_kg()
        for item in data:
            if item.get('url') == url: return
        
        data.append({"title": title, "url": url, "section": section, "date": str(datetime.date.today())})
        
        with open('knowledge_graph.json', 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=2)
        log(f"   💾 Saved to Knowledge Graph: {title}")
    except Exception as e:
        log(f"   ⚠️ KG Update Error: {e}")

def perform_maintenance_cleanup():
    try:
        kg_path = 'knowledge_graph.json'
        archive_dir = 'archive'
        
        if not os.path.exists(kg_path): return
        with open(kg_path, 'r', encoding='utf-8') as f: data = json.load(f)
            
        if len(data) < 800: return

        log("   🧹 Performing Database Maintenance...")
        guides = [item for item in data if "Guide" in item.get('title', '')]
        others = [item for item in data if item not in guides]
        
        keep_count = 400
        if len(others) <= keep_count: return

        kept_others = others[-keep_count:] 
        to_archive = others[:-keep_count]
        
        new_main_data = guides + kept_others
        with open(kg_path, 'w', encoding='utf-8') as f: json.dump(new_main_data, f, indent=2)
            
        if not os.path.exists(archive_dir): os.makedirs(archive_dir)
        
        current_year = datetime.datetime.now().year
        archive_path = os.path.join(archive_dir, f'history_{current_year}.json')
        
        archive_data = []
        if os.path.exists(archive_path):
            with open(archive_path, 'r', encoding='utf-8') as f: archive_data = json.load(f)
        
        archive_data.extend(to_archive)
        with open(archive_path, 'w', encoding='utf-8') as f: json.dump(archive_data, f, indent=2)
            
        log(f"   ✅ Archived {len(to_archive)} articles.")
    except Exception as e:
        log(f"   ⚠️ Maintenance Warning: {e}")

def estimate_blogger_url(title):
    """Estimates the Blogger URL to put in YouTube description before publishing."""
    # Clean title to slug
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower()
    slug = re.sub(r'[\s-]+', '-', slug)
    
    today = datetime.date.today()
    year = today.year
    month = f"{today.month:02d}"
    
    # Placeholder URL structure
    return f"https://www.latestai.me/{year}/{month}/{slug}.html"

# ==============================================================================
# 5. CORE GENERATION LOGIC
# ==============================================================================

def generate_step(model_name, prompt, step_name):
    log(f"   👉 Executing {step_name}...")
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
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                log(f"      ⚠️ Quota hit on Key #{key_manager.current_index + 1}.")
                if key_manager.switch_key():
                    log("      🔄 Retrying with new key...")
                    continue
                else: return None
            elif "503" in error_msg:
                time.sleep(30)
                continue
            else:
                log(f"      ❌ Error: {e}")
                return None

# ==============================================================================
# 6. UNIFIED PIPELINE
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name', 'models/gemini-2.5-flash')
    cat_config = config['categories'][category]
    
    log(f"\n🚀 STARTING {mode.upper()} CHAIN FOR: {category}")

    recent_titles = get_recent_titles_string(limit=40)

    # --- STEP A ---
    if mode == "trending":
        prompt_a = PROMPT_A_TRENDING.format(
            section=category,
            date_range=config['settings'].get('date_range_query', 'last 60 days'),
            section_focus=cat_config.get('trending_focus', ''),
            recent_titles=recent_titles
        )
    else:
        prompt_a = PROMPT_A_EVERGREEN.format(
            section=category,
            evergreen_prompt=cat_config.get('evergreen_prompt', ''),
            recent_titles=recent_titles
        )

    json_a = generate_step(model, prompt_a, "Step A (Research)")
    if not json_a: return
    time.sleep(10)

    # --- STEP B ---
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a)
    json_b = generate_step(model, prompt_b, "Step B (Drafting)")
    if not json_b: return
    time.sleep(10)

    # --- STEP C ---
    relevant_kg_str = get_relevant_kg_for_linking(category, limit=50)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b, knowledge_graph=relevant_kg_str)
    json_c = generate_step(model, prompt_c, "Step C (SEO & Images)")
    if not json_c: return
    time.sleep(10)

    # --- STEP D ---
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c)
    json_d = generate_step(model, prompt_d, "Step D (Audit)")
    if not json_d: return
    time.sleep(10)

    # --- STEP E (FINAL POLISH) ---
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d)
    json_e = generate_step(model, prompt_e, "Step E (Final)")
    if not json_e: return

    # -------------------------------------------------------------
    # 🎥 STEP F: DUAL VIDEO PRODUCTION (LANDSCAPE + SHORTS)
    # -------------------------------------------------------------
    video_embed_html = ""
    uploaded_video_id_main = None 
    uploaded_video_id_short = None
    youtube_description_cache = "" 

    try:
        # We use json_d (Audit) for script generation as it has the full draft
        final_d = try_parse_json(json_d, "Step D Parsing")
        data_a = try_parse_json(json_a, "Step A Parsing") if 'json_a' in locals() and json_a else {}
        
        specific_title = data_a.get('headline') if data_a else final_d.get('draftTitle', 'Tech News')
        
        if final_d:
            content_text = re.sub('<[^<]+?>', '', final_d.get('draftContent', ''))[:2000] # More context for long script
            
            log(f"   🎬 Step F: Generating Video Script for '{specific_title}'...")
            
            script_prompt = PROMPT_VIDEO_SCRIPT.format(title=specific_title, text_summary=content_text)
            
            # RETRY LOOP FOR SCRIPT GENERATION
            script_json_text = None
            for attempt in range(3):
                script_json_text = generate_step(model, script_prompt, f"Video Scripting (Attempt {attempt+1})")
                if try_parse_json(script_json_text):
                    break
                log("      ⚠️ Script JSON invalid, retrying...")
            
            if script_json_text:
                chat_script = try_parse_json(script_json_text, "Video Script Parsing")
                
                if chat_script:
                    # --- 1. RENDER LANDSCAPE (1920x1080) ---
                    renderer_main = video_renderer.VideoRenderer(width=1920, height=1080)
                    vid_main_file = f"vid_main_{int(time.time())}.mp4"
                    path_main = renderer_main.render_video(chat_script, specific_title, filename=vid_main_file)
                    
                    # --- 2. RENDER PORTRAIT (1080x1920) FOR SHORTS ---
                    renderer_short = video_renderer.VideoRenderer(width=1080, height=1920)
                    vid_short_file = f"vid_short_{int(time.time())}.mp4"
                    path_short = renderer_short.render_video(chat_script, specific_title, filename=vid_short_file)

                    # --- 3. YOUTUBE METADATA ---
                    yt_prompt = PROMPT_YOUTUBE_METADATA.format(draft_title=specific_title)
                    yt_meta_json = generate_step(model, yt_prompt, "YouTube SEO")
                    
                    if yt_meta_json:
                        yt_meta = try_parse_json(yt_meta_json, "YouTube Meta")
                        youtube_description_cache = yt_meta.get('description', '')
                        initial_desc = youtube_description_cache + "\n\n📄 Read full article: [Link coming soon]\n👉 Subscribe for more AI News!"
                        
                        # --- 4. UPLOAD MAIN VIDEO ---
                        if path_main and os.path.exists(path_main):
                            vid_id, embed_link = youtube_manager.upload_video_to_youtube(
                                path_main, 
                                yt_meta.get('title', specific_title),
                                initial_desc,
                                yt_meta.get('tags', [])
                            )
                            if vid_id:
                                uploaded_video_id_main = vid_id
                                # Create Embed HTML for Blog
                                video_embed_html = f"""
                                <div class="video-container" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; margin: 30px 0;">
                                    <iframe style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border-radius: 10px;" 
                                    src="https://www.youtube.com/embed/{vid_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
                                </div>
                                """
                                log("   ✅ Main Video Uploaded & Ready for Injection.")

                        # --- 5. UPLOAD SHORTS VIDEO ---
                        if path_short and os.path.exists(path_short):
                            # Add #Shorts to title
                            short_title = yt_meta.get('title', specific_title)[:90] + " #Shorts"
                            vid_id_short, _ = youtube_manager.upload_video_to_youtube(
                                path_short, 
                                short_title,
                                initial_desc, # Same description
                                yt_meta.get('tags', []) + ["shorts", "reels"]
                            )
                            if vid_id_short:
                                uploaded_video_id_short = vid_id_short
                                log("   ✅ Shorts Video Uploaded Successfully.")
            
    except Exception as e:
        log(f"⚠️ Video Generation Failed: {e}")

    # --- FINAL PROCESSING & PUBLISHING ---
    try:
        final = try_parse_json(json_e, "Step E Parsing")
        if not final:
            log("❌ Final processing failed: Could not parse JSON after multiple attempts.")
            return

        title = final.get('finalTitle', f"{category} Article")
        content = ARTICLE_STYLE 
        
        # Image Gen
        img_prompt = final.get('imageGenPrompt', f"Abstract {category} technology")
        overlay_text = final.get('imageOverlayText', title[:20])
        img_url = generate_and_upload_image(img_prompt, overlay_text)
        
        if img_url:
            alt_text = final.get('seo', {}).get('imageAltText', title)
            img_html = f'<div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;"><a href="{img_url}"><img border="0" src="{img_url}" alt="{alt_text}" /></a></div>'
            content += img_html
        
        # INJECT VIDEO HERE (AFTER STEP E)
        final_body = final.get('finalContent', '')
        if video_embed_html:
            # Inject after the first paragraph or H2
            if "</h2>" in final_body:
                final_body = final_body.replace("</h2>", "</h2>" + video_embed_html, 1)
            else:
                final_body = video_embed_html + final_body
        
        content += final_body
        
        # Publish to Blogger
        labels = [category]
        real_url = publish_post(title, content, labels)
        
        if real_url:
            update_kg(title, real_url, category)
            
            # UPDATE YOUTUBE DESCRIPTIONS (BOTH VIDEOS)
            new_desc = youtube_description_cache + f"\n\n📄 Read full article: {real_url}\n👉 Subscribe for more AI News!"
            
            if uploaded_video_id_main:
                youtube_manager.update_video_description(uploaded_video_id_main, new_desc)
            
            if uploaded_video_id_short:
                youtube_manager.update_video_description(uploaded_video_id_short, new_desc)

            # Facebook
            if img_url: 
                try:
                    fb_prompt = PROMPT_FACEBOOK_HOOK.format(title=title, category=category)
                    fb_json_text = generate_step(model, fb_prompt, "Facebook Hook Generation")
                    if fb_json_text:
                        fb_data = try_parse_json(fb_json_text, "Facebook Parsing")
                        if fb_data:
                            social_manager.distribute_content(fb_data.get('facebook', ''), real_url, img_url)
                except Exception as e:
                    log(f"⚠️ Facebook Automation Skipped: {e}")
            
    except Exception as e:
        log(f"❌ Final processing failed: {e}")

# ==============================================================================
# 7. MAIN
# ==============================================================================

def main():
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    for category in config['categories']:
        run_pipeline(category, config, mode="trending")
        log("💤 Cooling down (30s)...")
        time.sleep(30)
        
        run_pipeline(category, config, mode="evergreen")
        log("💤 Cooling down (30s)...")
        time.sleep(30)
    
    perform_maintenance_cleanup()

if __name__ == "__main__":
    main()
