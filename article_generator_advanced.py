import os
import json
import time
import requests
import re
from google import genai
from google.genai import types

# ==============================================================================
# 1. FULL PROMPTS DEFINITIONS
# ==============================================================================

PROMPT_A_TEMPLATE = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index (Google Search, Google Scholar, arXiv, official blogs, SEC/10-Q when financial figures are used) for one specific, high-impact case, study, deployment, or company announcement that occurred within {date_range} (for example "last 60 days").

SECTION FOCUS (choose the relevant focus for {section}; these must guide your search terms):
{section_focus}

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

PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A (headline + sources). Write a polished HTML article (1500–2000 words) using the provided headline and sources. Follow these rules exactly.

INPUT DATA FROM PROMPT A:
{json_input}

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
Inline citation format EXACTLY: (Source: ShortTitle — YYYY-MM-DD — URL) e.g., (Source: CoTracker3 arXiv — 2024-10-15 — https://arxiv.org/...)
At the end include a "Sources" <ul> listing full source entries (title + URL + date + short credibility note).
If you paraphrase any statistic, include the exact location in the source (e.g., "see Table 2, p.6").
For market/financial numbers, prefer SEC filings, company reports, or named market research with publisher and year.

IV. SECTION-SPECIFIC FOCUS (must be explicit in article):
Use the section focus from the input — ensure the article addresses at least TWO focus points (state them explicitly in the text as subheadings).

V. HUMANIZATION / ANTI-AI-PATTERNS:
Insert at least two small humanizing details: (a) One short anecdote/example, (b) One sentence of personal observation.
Vary sentence rhythm: include one parenthetical aside, and one comma-spliced sentence (once).
Insert one small, deliberate stylistic imperfection (e.g., an interjection "Look," or "Here’s the rub:").

VI. FORMATTING & SEO:
Use H2 and H3 subheadings.
Add one small comparison table (text-only) and 3 bullet "Why it matters" bullets near the top.
Add schema-ready attributes.
Word count: 1500–2000 words.

Output JSON ONLY, EXACTLY in this shape:
{{"draftTitle":"...","draftContent":"<html>...full HTML article...</html>","sources":[ {{ "title":"", "url":"", "date":"", "type":"", "credibility":"" }}, ... ],"notes":"List any remaining issues or empty string"}}
"""

PROMPT_C_TEMPLATE = """
C:You are Strategic Editor & SEO consultant for 'AI News Hub'.
Input Draft JSON: {json_input}
Knowledge Graph: {knowledge_graph}

Produce a final publishing package with the following exact tasks.

ARTICLE-LEVEL POLISH:
Improve clarity, tighten prose, and ensure "human first" voice remains. Do NOT convert to academic tone.
Add 2–4 textual rich elements: a short comparison table (if none present, create one), 3 bullets "Key takeaways", and 1 highlighted blockquote.
Extract one conceptual icon (1–2 English words).
Create author byline and short author bio (40–60 words). Use placeholder if unknown.

NETWORK-LEVEL OPTIMIZATION:
Analyze knowledge_graph array and select 3–5 best internal articles to link. Provide exact HTML anchor tags using slugs from knowledge_graph. For each internal link, include a one-line note: which Section Focus point it fills.
Propose 2 future article titles to fill content gaps.

SEO & PUBLISHING PACKAGE:
Provide metaTitle (50–60 chars) and metaDescription (150–160 chars).
Provide 5–7 tags (exact keywords).
Generate Article schema JSON-LD.
Provide FAQ schema (3 Q&A).

ADSENSE READINESS & RISK ASSESSMENT:
Run Adsense readiness evaluation and return adsenseReadinessScore from 0–100.
Include breakdown for: Accuracy, E-E-A-T, YMYL risk, Ads placement risk.

OUTPUT:
Return single JSON ONLY with these fields:
{{"finalTitle":"...","finalContent":"<html>...final polished HTML with inline links and sources...</html>","excerpt":"...short excerpt...","seo": {{ "metaTitle":"...","metaDescription":"...","imageAltText":"..." }},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[ "<a href='...'>...</a>", ... ],"schemaMarkup":"{{...JSON-LD...}}","adsenseReadinessScore":{{ "score":0-100, "breakdown": {{...}}, "notes":"..." }},"sources":[ ... ],"authorBio":{{ "name":"...", "bio":"...", "profileUrl":"..." }}}}
"""

PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Final Audit (UPDATED — includes mandatory A, B, C checks)
You are the Humanization & Final Audit specialist for 'AI News Hub'.
Input: {json_input}

Your job: apply a comprehensive, human-level audit and humanization pass.
MANDATORY CHECKS:

STEP 2 — MANDATORY CHECK A: Sources & Fact Claims
A.1 Numeric claim verification: Verify at least one source contains exact number. If not, correct it or hedge it.
A.2 Load-bearing claim verification: Ensure two independent sources.
A.3 Quote verification: Verify exact text exists.
A.4 Inline citation completeness: Mismatch check.

STEP 3 — MANDATORY CHECK B: Human Style
B.1 First-person writer sentence: Ensure presence of exactly one.
B.2 Rhetorical question: Ensure presence of one.
B.3 Forbidden phrases: Remove "In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion".
B.4 Sentence length distribution: Enforce 40/45/15 split.
B.6 "AI-pattern sniff" and rewrite: Identify 8 sentences that look AI-generated and rewrite them.

STEP 4 — MANDATORY CHECK C: E-E-A-T & YMYL
C.1 Author bio verification.
C.2 YMYL disclaimer: Insert if needed.
C.4 AI-detection threshold: If > 50, re-run humanization.

STEP 6 — Safety, Legal & Final Editorial Confirmation
Include "humanEditorConfirmation" object.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"...","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}},"edits":[ {{"type":"...", "original":"...", "new":"...", "reason":"..."}}...],"auditMetadata": {{ "auditTimestamp":"...", "aiProbability":n, "numberOfHumanizationPasses":n }},"plagiarismFlag": false,"aiDetectionFlag": false,"citationCompleteness": true,"authorBioPresent": true,"humanEditorConfirmation": {{...}},"requiresAction": false, "requiredActions":[...],"notes":"..."}}
"""

PROMPT_E_TEMPLATE = """
E: ROLE PROMPT — "The Assessor / Evaluator / Careful Auditor / Error-Corrector / Publisher"
You are the Publisher.
Input: {json_input}

Your single mission: take the provided draft/final article and transform it into a publication-quality piece.

STEP-BY-STEP WORKFLOW:
1. INPUTS: Read finalContent, sources.
2. SOURCE & FACT VERIFICATION: Final check on numeric claims and quotes.
3. HUMANIZATION & STYLE: Enforce first-person sentence, rhetorical question, remove forbidden phrases ("In today's digital age", etc).
4. SEO & PUBLISHING PACKAGE: Validate meta tags, schema, internal links.
5. FINAL OUTPUT: Return single JSON ONLY.

{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio": {{...}},"edits":[...],"auditMetadata": {{...}},"requiredActions":[...]}}
"""

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================

def get_access_token():
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
    token = get_access_token()
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

def clean_json_response(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    return text

def generate_step(client, model, prompt_text, step_name):
    """Executes a single step of the chain with robust retry logic matching old system style"""
    print(f"   👉 Executing {step_name}...")
    
    max_retries = 3
    
    for i in range(max_retries):
        try:
            # Using the new SDK syntax but with the OLD MODEL name
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            if response and response.text:
                return clean_json_response(response.text)
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str:
                wait_time = 70 if i == 0 else 120 # Matches your old system's 70s/120s logic
                print(f"      ⏳ Server Busy/Quota (Attempt {i+1}/{max_retries}). Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"      ❌ Unexpected Error in {step_name}: {e}")
                time.sleep(10)
                
    print(f"      ❌ Failed {step_name} after {max_retries} retries.")
    return None

def load_knowledge_graph():
    try:
        with open('knowledge_graph.json', 'r') as f:
            return f.read()
    except:
        return "[]"

def update_knowledge_graph(slug, title, section):
    try:
        data = []
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f:
                data = json.load(f)
        data.append({"slug": slug, "title": title, "section": section})
        with open('knowledge_graph.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to update knowledge graph: {e}")

# ==============================================================================
# 3. MAIN PIPELINE LOGIC
# ==============================================================================

def run_trending_pipeline(client, model, category, config):
    date_range = config['settings'].get('date_range_query', 'last 60 days')
    cat_config = config['categories'][category]
    section_focus = cat_config.get('trending_focus', '')

    # --- Step A: Research ---
    prompt_a = PROMPT_A_TEMPLATE.format(
        section=category,
        date_range=date_range,
        section_focus=section_focus
    )
    json_a = generate_step(client, model, prompt_a, "Step A (Research)")
    if not json_a: return
    time.sleep(5) 

    # --- Step B: Draft ---
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a)
    json_b = generate_step(client, model, prompt_b, "Step B (Drafting)")
    if not json_b: return
    time.sleep(5)

    # --- Step C: SEO & Strategy ---
    kg = load_knowledge_graph()
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b, knowledge_graph=kg)
    json_c = generate_step(client, model, prompt_c, "Step C (SEO)")
    if not json_c: return
    time.sleep(5)

    # --- Step D: Audit ---
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c)
    json_d = generate_step(client, model, prompt_d, "Step D (Audit)")
    if not json_d: return
    time.sleep(5)

    # --- Step E: Publisher ---
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d)
    json_e = generate_step(client, model, prompt_e, "Step E (Final Polish)")
    if not json_e: return

    # --- Publish ---
    try:
        final_data = json.loads(json_e)
        title = final_data.get('finalTitle', f"New in {category}")
        content = final_data.get('finalContent', '')
        
        if 'auditMetadata' in final_data:
            audit = final_data['auditMetadata']
            content += f"<hr><small><i>Audit Stats: AI Prob {audit.get('aiProbability')}%, Passes {audit.get('numberOfHumanizationPasses')}</i></small>"

        if publish_post(title, content, [category, "Trending", "AI News"]):
            slug = title.lower().replace(' ', '-').replace(':', '')[:50]
            update_knowledge_graph(slug, title, category)
            
    except Exception as e:
        print(f"❌ Failed to parse/publish final JSON: {e}")

def run_evergreen_pipeline(client, model, category, prompt_text):
    print(f"   🌲 Generating Evergreen Article for {category}...")
    try:
        wrapper = f"{prompt_text}\n\nOutput JSON ONLY: {{'title': '...', 'content': '<html>...</html>'}}"
        json_res = generate_step(client, model, wrapper, "Evergreen Generation")
        if json_res:
            data = json.loads(json_res)
            publish_post(data['title'], data['content'], [category, "Guide", "Evergreen"])
            update_knowledge_graph("guide-" + category.lower().replace(' ', '-'), data['title'], category)
    except Exception as e:
        print(f"❌ Evergreen failed: {e}")

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Missing GEMINI_API_KEY")
        return

    client = genai.Client(api_key=api_key)
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Using the model exactly as defined in the config
    model = config['settings'].get('model_name', 'models/gemini-2.5-flash')

    for category in config['categories']:
        print(f"\n🚀 PROCESSING CATEGORY: {category}")
        
        # 1. Trending Article
        run_trending_pipeline(client, model, category, config)
        print("💤 Cooling down (60s)...")
        time.sleep(60) # Increased cool down to match old system safety margins
        
        # 2. Evergreen Article
        evergreen_prompt = config['categories'][category].get('evergreen_prompt')
        if evergreen_prompt:
            run_evergreen_pipeline(client, model, category, evergreen_prompt)
            print("💤 Cooling down (60s)...")
            time.sleep(60)

if __name__ == "__main__":
    main()
