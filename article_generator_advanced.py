import os
import json
import time
import requests
import re
import random
from google import genai
from google.genai import types

# ==============================================================================
# 1. PROMPTS DEFINITIONS (EXACT & DETAILED)
# ==============================================================================

# --- TRENDING RESEARCH (NEWS) ---
PROMPT_A_TRENDING = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index (Google Search, Google Scholar, arXiv, official blogs, SEC/10-Q when financial figures are used) for one specific, high-impact case, study, deployment, or company announcement that occurred within {date_range} (for example "last 60 days").

SECTION FOCUS (choose the relevant focus for {section}; these must guide your search terms):
{section_focus}

MANDATORY SOURCE & VERIFICATION RULES (follow EXACTLY):
1. Return exactly one headline (plain English, single line) — a journalist-style headline that connects technical advance to human/commercial impact.
2. Provide 2–3 primary sources that verify the story. At least:
   - One PRIMARY TECH SOURCE: (peer-reviewed DOI or arXiv paper with version/date OR official GitHub repo with commit/PR date OR official company technical blog post).
   - One SECONDARY CORROBORATING SOURCE: (reputable news outlet, conference proceeding, or company press release).
3. For each source, include:
   - title, exact URL, publication date (YYYY-MM-DD), type (paper/blog/repo/press/SEC), and a one-line note: "why it verifies".
4. For any numeric claim you will later assert (e.g., "88% of queries"), ensure the source actually contains that number. If the source gives a figure differently, report the exact figure and location of the figure in the source (e.g., "see Figure 2, page 6" or "arXiv v2, paragraph 3").
5. If the story touches YMYL topics (health/finance/legal), include an immediate risk note listing which regulations may apply (e.g., HIPAA, FDA, CE, GDPR, SEC) and what kind of verification is required.
6. Check basic credibility signals for each source and report them: (a) publisher credibility (Nature/IEEE/ACM/official corp blog), (b) if arXiv — indicate whether paper has code/benchmarks, (c) if GitHub — include last commit date and license, (d) if press release — confirm corporate domain and date/time.

Output JSON only, EXACTLY in this format:
{{"headline": "One-line headline","sources": [{{"title":"Exact source title","url":"https://...","date":"YYYY-MM-DD","type":"paper|arXiv|repo|blog|press|SEC","why":"One-line why this verifies (include exact page/figure if relevant)","credibility":"short note: Nature/IEEE/company blog/press/etc","notes":"any caveats about the source"}}],"riskNote":"If YMYL risk exists list regulators and verification steps; otherwise empty string"}}
"""

# --- EVERGREEN RESEARCH (CONCEPTS) ---
PROMPT_A_EVERGREEN = """
A:You are an expert technical educator specialized in {section}. Your task is to outline a comprehensive "Ultimate Guide" or "Deep Dive" into a core concept of {section}.
Instead of recent news, search for and cite: Foundational papers, Standard definitions, Official Documentation, and Key Textbooks.

TOPIC PROMPT: {evergreen_prompt}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return a headline like "The Ultimate Guide to [Topic]" or "Understanding [Concept]: A Deep Dive".
2. Provide 2–3 authoritative sources (Seminal Papers, Documentation, University Lectures).
3. Output JSON ONLY (Same format as news to maintain pipeline compatibility):
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"YYYY-MM-DD (or N/A)", "type":"documentation|paper|book", "why":"Foundational reference", "credibility":"High"}}], "riskNote":"..."}}
"""

# --- COMMON STEPS (B, C, D, E) ---
PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A (headline + sources). Write a polished HTML article (1500–2000 words) using the provided headline and sources. Follow these rules exactly.
INPUT: {json_input}

I. STRUCTURE & VOICE RULES (mandatory):
H1 = headline exactly as provided.
Intro: begin with a short, verifiable human hook.
Use journalistic, conversational English — not academic tone.
Paragraphs: 2–4 sentences maximum.
Sentence length distribution: ~40% short (6–12 words), ~45% medium (13–22 words), ~15% long (23–35 words).
Include exactly one first-person editorial sentence from the writer.
Include one rhetorical question in the article.
Avoid AI-template phrasing: forbid "In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion".

II. EDITORIAL PRINCIPLES:
So What? — after each major fact/claim, add a one-sentence human explanation.
Depth over breadth.
Dual verification for load-bearing claims.
Quotes — include at least one direct quote from a named expert.

III. CITATION & SOURCING RULES:
Inline citation format EXACTLY: (Source: ShortTitle — YYYY-MM-DD — URL).
At the end include a "Sources" <ul>.

IV. SECTION-SPECIFIC FOCUS:
Ensure the article addresses at least TWO focus points.

V. HUMANIZATION:
Insert at least two small humanizing details (anecdote, personal observation).
Vary sentence rhythm.

VI. FORMATTING & SEO:
Use H2 and H3 subheadings.
Add one small comparison table (text-only) and 3 bullet "Why it matters" bullets near the top.

Output JSON ONLY:
{{"draftTitle":"...","draftContent":"<html>...full HTML article...</html>","sources":[ {{ "title":"", "url":"", "date":"", "type":"", "credibility":"" }}, ... ],"notes":"List any remaining issues or empty string"}}
"""

PROMPT_C_TEMPLATE = """
C:You are Strategic Editor & SEO consultant for 'AI News Hub'.
Input Draft JSON: {json_input}
Knowledge Graph: {knowledge_graph}

Produce a final publishing package with the following exact tasks.

ARTICLE-LEVEL POLISH:
Improve clarity, tighten prose, and ensure "human first" voice remains.
Add 2–4 textual rich elements: a short comparison table, 3 bullets "Key takeaways", and 1 highlighted blockquote.
Extract one conceptual icon (1–2 English words).
Create author byline and short author bio.

**IMAGE PROMPT GENERATION (MANDATORY):**
Create a specific English prompt for an AI image generator to create a header image for this article.
RULES:
1. Abstract, futuristic, technological style (3D render, isometric, or digital art).
2. NO HUMANS, NO FACES, NO ANIMALS, NO TEXT.
3. Focus on concepts: data streams, neural nodes, silicon chips, glowing networks, abstract robotics.
4. Field name in JSON: "imageGenPrompt".

NETWORK-LEVEL OPTIMIZATION:
Analyze knowledge_graph array and select 3–5 best internal articles to link.
Propose 2 future article titles.

SEO & PUBLISHING PACKAGE:
Provide metaTitle (50–60 chars) and metaDescription (150–160 chars).
Provide 5–7 tags.
Generate Article schema JSON-LD.
Provide FAQ schema (3 Q&A).

ADSENSE READINESS:
Run Adsense readiness evaluation and return adsenseReadinessScore from 0–100.

OUTPUT JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...final polished HTML...</html>","excerpt":"...","imageGenPrompt":"...","seo": {{ "metaTitle":"...","metaDescription":"...","imageAltText":"..." }},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[ "<a href='...'>...</a>", ... ],"schemaMarkup":"{{...JSON-LD...}}","adsenseReadinessScore":{{ "score":0-100, "breakdown": {{...}}, "notes":"..." }},"sources":[ ... ],"authorBio":{{ "name":"...", "bio":"...", "profileUrl":"..." }}}}
"""

PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Final Audit
Input: {json_input}

MANDATORY CHECKS:
STEP 2 — MANDATORY CHECK A: Sources & Fact Claims (Numeric, Load-bearing, Quotes, Citations).
STEP 3 — MANDATORY CHECK B: Human Style (First-person sentence, Rhetorical question, Forbidden phrases, Sentence length, AI-pattern sniff).
STEP 4 — MANDATORY CHECK C: E-E-A-T & YMYL (Author bio, YMYL disclaimer, AI-detection threshold).
STEP 6 — Safety, Legal & Final Editorial Confirmation.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","imageGenPrompt":"...preserve...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"...","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}},"edits":[...],"auditMetadata": {{ "auditTimestamp":"...", "aiProbability":n, "numberOfHumanizationPasses":n }},"humanEditorConfirmation": {{...}},"requiresAction": false, "requiredActions":[...],"notes":"..."}}
"""

PROMPT_E_TEMPLATE = """
E: ROLE PROMPT — "The Publisher"
Input: {json_input}

Your single mission: take the provided draft/final article and transform it into a publication-quality piece.
1. INPUTS: Read finalContent, sources.
2. SOURCE & FACT VERIFICATION: Final check.
3. HUMANIZATION & STYLE: Enforce first-person sentence, rhetorical question, remove forbidden phrases.
4. SEO & PUBLISHING PACKAGE: Validate meta tags, schema, internal links.
5. FINAL OUTPUT: Return single JSON ONLY.

{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","imageGenPrompt":"...preserve...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio": {{...}},"edits":[...],"auditMetadata": {{...}},"requiredActions":[...]}}
"""

# ==============================================================================
# 2. KEY MANAGER (ROTATION LOGIC - 6 KEYS)
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        # Load keys 1 through 6
        for i in range(1, 7):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        
        if not self.keys:
            # Fallback to single key if numbered ones aren't set
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
            
        self.current_index = 0
        print(f"🔑 Loaded {len(self.keys)} API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            print(f"🔄 Switching to API Key #{self.current_index + 1}...")
            return True
        else:
            print("❌ All API Keys exhausted for today!")
            return False

key_manager = KeyManager()

# ==============================================================================
# 3. HELPER FUNCTIONS
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
        print(f"❌ Blogger Auth Error: {e}")
        return None

def publish_post(title, content, labels):
    token = get_blogger_token()
    if not token: return False
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"title": title, "content": content, "labels": labels}
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            print(f"✅ Published: {title}")
            return True
        else:
            print(f"❌ Publish Error: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

def clean_json(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    return text

def generate_and_upload_image(prompt_text):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        print("⚠️ No IMGBB_API_KEY found.")
        return None
    
    print(f"   🎨 Generating Image...")
    try:
        # Pollinations Generation (Free)
        safe_prompt = requests.utils.quote(f"{prompt_text}, abstract, futuristic, 3d render, high quality, --no people, humans, animals, faces, text")
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologo=true&seed={random.randint(1,99999)}&model=flux"
        
        img_response = requests.get(url, timeout=30)
        if img_response.status_code != 200: return None
        
        # ImgBB Upload (Free Direct Link)
        print("   ☁️ Uploading to ImgBB...")
        res = requests.post(
            "https://api.imgbb.com/1/upload", 
            data={"key":key, "expiration":0}, 
            files={"image":img_response.content}
        )
        if res.status_code == 200:
            direct_link = res.json()['data']['url']
            print(f"   ✅ Image Ready: {direct_link}")
            return direct_link
    except Exception as e:
        print(f"   ⚠️ Image failed: {e}")
    return None

def load_kg():
    try:
        with open('knowledge_graph.json', 'r') as f: return f.read()
    except: return "[]"

def update_kg(slug, title, section):
    try:
        data = []
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f: data = json.load(f)
        data.append({"slug": slug, "title": title, "section": section})
        with open('knowledge_graph.json', 'w') as f: json.dump(data, f, indent=2)
    except: pass

# ==============================================================================
# 4. CORE GENERATION LOGIC (WITH KEY ROTATION)
# ==============================================================================

def generate_step(model_name, prompt, step_name):
    """
    Executes a step. If 429/Quota error occurs, switches key and retries.
    """
    print(f"   👉 Executing {step_name}...")
    
    while True: # Loop to handle key switching
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
            # Check for Quota/Rate limits
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"      ⚠️ Quota hit on Key #{key_manager.current_index + 1}.")
                
                # Try switching key
                if key_manager.switch_key():
                    print("      🔄 Retrying immediately with new key...")
                    continue # Retry the loop with new key
                else:
                    print("      ❌ Fatal: No more keys available.")
                    return None
            
            elif "503" in error_msg:
                print("      ⏳ Server busy (503). Waiting 30s...")
                time.sleep(30)
                continue
            
            else:
                print(f"      ❌ Error: {e}")
                return None

# ==============================================================================
# 5. UNIFIED PIPELINE (TRENDING & EVERGREEN)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    """
    Runs the full 5-step chain for either Trending or Evergreen.
    mode: 'trending' or 'evergreen'
    """
    model = config['settings'].get('model_name', 'models/gemini-2.5-flash')
    cat_config = config['categories'][category]
    
    print(f"\n🚀 STARTING {mode.upper()} CHAIN FOR: {category}")

    # --- STEP A: RESEARCH ---
    if mode == "trending":
        prompt_a = PROMPT_A_TRENDING.format(
            section=category,
            date_range=config['settings'].get('date_range_query', 'last 60 days'),
            section_focus=cat_config.get('trending_focus', '')
        )
    else: # evergreen
        prompt_a = PROMPT_A_EVERGREEN.format(
            section=category,
            evergreen_prompt=cat_config.get('evergreen_prompt', '')
        )

    json_a = generate_step(model, prompt_a, "Step A (Research)")
    if not json_a: return
    time.sleep(10) # Short pacing

    # --- STEP B: DRAFT ---
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a)
    json_b = generate_step(model, prompt_b, "Step B (Drafting)")
    if not json_b: return
    time.sleep(10)

    # --- STEP C: SEO ---
    kg = load_kg()
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b, knowledge_graph=kg)
    json_c = generate_step(model, prompt_c, "Step C (SEO)")
    if not json_c: return
    time.sleep(10)

    # --- STEP D: AUDIT ---
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c)
    json_d = generate_step(model, prompt_d, "Step D (Audit)")
    if not json_d: return
    time.sleep(10)

    # --- STEP E: PUBLISH ---
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d)
    json_e = generate_step(model, prompt_e, "Step E (Final)")
    if not json_e: return

    # --- FINAL PUBLISHING ---
    try:
        final = json.loads(json_e)
        title = final.get('finalTitle', f"{category} Article")
        content = final.get('finalContent', '')
        
        # Image Generation & Insertion
        img_prompt = final.get('imageGenPrompt', f"Abstract {category} technology")
        img_url = generate_and_upload_image(img_prompt)
        
        if img_url:
            alt_text = final.get('seo', {}).get('imageAltText', title)
            # Blogger-friendly image HTML
            img_html = f'<div class="separator" style="clear: both; text-align: center;"><a href="{img_url}" style="margin-left: 1em; margin-right: 1em;"><img border="0" src="{img_url}" alt="{alt_text}" data-original-width="1280" data-original-height="720" /></a></div><br />'
            content = img_html + content

        # Metadata Footer
        if 'auditMetadata' in final:
            content += f"<hr><small><i>Audit Stats: AI Prob {final['auditMetadata'].get('aiProbability')}%</i></small>"

        labels = [category, "AI News" if mode == "trending" else "Guide"]
        
        if publish_post(title, content, labels):
            print(f"✅ PUBLISHED: {title}")
            slug = title.lower().replace(' ', '-').replace(':', '')[:50]
            update_kg(slug, title, category)
            
    except Exception as e:
        print(f"❌ Final processing failed: {e}")

# ==============================================================================
# 6. MAIN
# ==============================================================================

def main():
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Process all categories
    for category in config['categories']:
        # 1. Trending Article (Full Chain)
        run_pipeline(category, config, mode="trending")
        print("💤 Cooling down (30s)...")
        time.sleep(30)
        
        # 2. Evergreen Article (Full Chain NOW)
        run_pipeline(category, config, mode="evergreen")
        print("💤 Cooling down (30s)...")
        time.sleep(30)

if __name__ == "__main__":
    main()
