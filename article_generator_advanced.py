import os
import json
import time
import requests
import re
import random
import sys
import datetime
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# IMPORT SOCIAL MANAGER
import social_manager

# ==============================================================================
# 0. LOGGING HELPER
# ==============================================================================
def log(msg):
    """Prints message immediately to console, bypassing buffer."""
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
# 2. PROMPTS DEFINITIONS (FULL ORIGINAL VERSIONS)
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
2. `imageOverlayText`: A very short, punchy title (MAX 3-5 WORDS). Example: "AI Energy Crisis", "Future of Robotics".

NETWORK-LEVEL OPTIMIZATION:
Analyze knowledge_graph array and select 3–5 best internal articles to link. Provide exact HTML anchor tags using slugs from knowledge_graph. For each internal link, include a one-line note: which Section Focus point it fills (e.g., "fills: dataset comparison, reproducibility").
**STRICT LINKING RULE:** Scan the draft for concepts matching the "title" in the provided database. IF and ONLY IF a match is found, insert a link using the EXACT "url" provided in the database. Format: `<a href="EXACT_URL_FROM_DB">Keyword</a>`. DO NOT invent links.
Propose 2 future article titles to fill content gaps (be precise, SEO-friendly).

SEO & PUBLISHING PACKAGE:
Provide metaTitle (50–60 chars) and metaDescription (150–160 chars).
Provide 5–7 tags (exact keywords).
Generate Article schema JSON-LD (fully populated with placeholders for image URL and author URL).
Provide FAQ schema (3 Q&A) optimized for featured snippets (each answer ≤ 40 words).

ADSENSE READINESS & RISK ASSESSMENT:
Run Adsense readiness evaluation and return adsenseReadinessScore from 0–100. Include precise numeric breakdown for:
- Accuracy (0–25)
- E-E-A-T (0–25)
- YMYL risk (0–25, where 0 = no risk, 25 = high risk)
- Ads placement risk (0–25)
Also include short sentences (1 line) explaining each sub-score.
If score < 85, list exact action items (ordered by priority) to reach >= 90.

FINAL TECHNICAL CHECKS:
Validate metaTitle length (50–60) and metaDescription length (150–160); if not within ranges, propose corrected strings.
Ensure schema markup fields are consistent with final content (title, datePublished).
Ensure at least 3 internal links included.
Ensure at least one imageAltText present.
Run a final "citation completeness" check: every inline citation present in content must appear in final sources array.

OUTPUT:
Return single JSON ONLY with these fields:
{{"finalTitle":"...","finalContent":"<html>...final polished HTML with inline links and sources...</html>","excerpt":"...short excerpt...","imageGenPrompt":"...","imageOverlayText":"...","seo": {{ "metaTitle":"...","metaDescription":"...","imageAltText":"..." }},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[ "...","..." ],"internalLinks":[ "<a href='...'>...</a>", ... ],"schemaMarkup":"{{...JSON-LD...}}","adsenseReadinessScore":{{ "score":0-100, "breakdown": {{ "accuracy":n, "E-E-A-T":n, "YMYL":n, "adsPlacement":n }}, "notes":"..." }},"sources":[ ... ],"authorBio":{{ "name":"...", "bio":"...", "profileUrl":"..." }}}}
"""

PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Final Audit (UPDATED — includes mandatory A, B, C checks)
You are the Humanization & Final Audit specialist for 'AI News Hub' (a human editor role simulated by the model). Input: the JSON output from Prompt C. Your job: apply a comprehensive, human-level audit and humanization pass, with explicit mandatory checks. Do not invent facts. If something cannot be verified, mark it clearly.

IMPORTANT: This prompt includes a set of MANDATORY CHECKS (A, B, C). For each check you must (1) validate, (2) either fix the issue automatically according to the remediation rules below, or (3) if you cannot fix it, mark it in the "notes" and set "requiresAction": true and list precise "requiredActions". Do not proceed silently if checks fail.

STEP 2 — MANDATORY CHECK A: Sources & Fact Claims (strict rules + remediation)
A.1 Numeric claim verification:
Find every numeric claim in finalContent (percentages, dataset sizes, market numbers, dates, version numbers).
For each numeric claim:
Verify that at least one source in sources[] contains that exact number and that the inline citation references that source.
If claim is "load-bearing" (major conclusion, market size, adoption %, where removal would change article meaning) verify at least TWO independent sources.
If the exact number does not appear in any provided source:
Attempt automatic correction: replace the number with the exact figure from the best source and add parenthetical "(corrected per SourceShortTitle — YYYY-MM-DD)" with inline citation.
If no source provides any supporting number, REMOVE the numeric claim or convert to hedged phrasing (e.g., "a majority" or "many studies") and annotate in notes: "numeric-claim-removed-or-hedged" with reason & suggested follow-up.
Record each check result in edits array with fields: {{ "type": "numericCheck", "original": "...", "actionTaken": "...", "sourceUsed": "..." }}

A.2 Load-bearing claim verification:
For each load-bearing claim, ensure two independent credible sources. If only one exists:
Flag as "single-source-claim" in notes and requiredActions; do not invent a second source.
In the article body, add a short inline parenthetical: "(single-source claim — needs further verification)".

A.3 Quote verification:
For every direct quote:
Verify exact text exists in one of the sources (match exact phrase or provide a linkable match).
If the quote is not verifiable:
Remove the quote and replace with a paraphrase + citation OR mark the paragraph as "illustrative composite: paraphrase of sources" with inline note.
For each quote fixed, add an edits entry: {{ "type":"quoteCheck", "originalQuote":"...", "actionTaken":"replaced/paraphrased/verified", "verificationSource":"..." }}

A.4 Inline citation completeness:
Every inline citation present in finalContent must appear in final sources[] and vice versa. If mismatch, add the missing source entry (with type and credibility) or remove the stray inline citation.
Add "citationCompleteness": true/false in output with list of mismatches if any.

STEP 3 — MANDATORY CHECK B: Human Style (make article human, not AI-like)
B.1 First-person writer sentence:
Ensure presence of exactly one first-person editorial sentence (writer POV), e.g., "In my experience covering X, I've seen..." If missing:
Insert one concise, natural sentence before the first H2: "In my experience covering [topic], I've found..." with no more than 20 words. Add to edits.
B.2 Rhetorical question:
Ensure there is one rhetorical question somewhere in the body. If missing, insert a short rhetorical question (<=10 words) in a natural location. Add to edits.
B.3 Forbidden phrases:
Check that none of the forbidden exact phrases exist in content:
"In today's digital age"
"The world of AI is ever-evolving"
"This matters because"
"In conclusion"
If any forbidden phrase is found: replace with human alternative and record edit. Add to notes which phrases were removed.
B.4 Sentence length distribution:
Analyze sentence lengths and compute distribution:
Short (6–12 words): target ~40%
Medium (13–22 words): target ~45%
Long (23–35 words): target ~15%
If distribution deviates by more than ±10 percentage points in any bucket:
Implement adjustments by splitting long sentences or combining short sentences, favoring simple journalistic style.
Record all sentence-splitting/combining operations in edits array with before/after text.
B.6 "AI-pattern sniff" and rewrite:
Identify top 8 sentences that most resemble AI-generated prose (e.g., long, highly structured, generic claims). For each:
Provide two human rewrite options in the output: OptionA (concise journalist) and OptionB (narrative/personal). Replace the article's sentence with OptionA by default and include OptionB in notes.
Record these 8 replacements in edits array with before/after.

STEP 4 — MANDATORY CHECK C: E-E-A-T & YMYL (strict)
C.1 Author bio verification:
Ensure authorBio exists with fields: name, short cred (1 sentence), profileUrl.
If authorBio missing or incomplete:
Insert placeholder authorBio with name = "AI News Hub Editorial Staff" and recommended author line: "Human editor: Yousef Sameer" (or actual name if provided). Add to edits and set "authorBioInserted": true.
C.2 YMYL disclaimer:
If riskNote from Prompt A or content touches YMYL topics, ensure explicit disclaimer in bold near top:
Example: "<strong>Disclaimer:</strong> This article is for informational purposes and is not medical/legal/financial advice. ..."
If missing, insert and record.
C.4 AI-detection threshold and remediation:
Run an AI-detection estimate (conceptual): assign an "aiProbability" score 0–100 based on style features (sentence length, repetition, template phrases). If aiProbability > 50:
Re-run the humanization steps (B.1–B.6) iteratively until aiProbability <= 50 or until 3 passes attempted.
If after 3 passes aiProbability > 50, set "requiresAction": true with requiredAction "human-editor-rewrite" and include the aiProbability number and edits made.
Record final aiProbability and numberOfPasses in auditMetadata.

STEP 6 — Safety, Legal & Final Editorial Confirmation (MANDATORY G additions)
6.1 Defamation check: If article alleges wrongdoing by named entities/individuals, ensure TWO independent sources confirm. If not, soften language and annotate.
6.2 Final human editor confirmation (MANDATORY):
At the end of the output JSON include the following field exactly:"humanEditorConfirmation": {{"editorName": "Yousef Sameer","editorRole": "Human Editor, AI News Hub","confirmationLine": "I have reviewed this article and verified the sources, quotes and numeric claims to the best of my ability.","dateReviewed": "YYYY-MM-DD"}}
If the actual human editor is someone else, replace name accordingly. If no human has actually reviewed, set "humanEditorConfirmation.reviewStatus": "pending" and add requiredAction "human-editor-review".
This confirmation line must appear in the article HTML as a short line below the author bio (when reviewStatus = "confirmed") or a "Pending editorial review" note if pending.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","excerpt":"...","imageGenPrompt":"...preserve...","imageOverlayText":"...preserve...","seo": {{...}},"tags":[...],"conceptualIcon":"...","futureArticleSuggestions":[...],"internalLinks":[...],"schemaMarkup":"...","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}},"edits":[ {{"type":"...", "original":"...", "new":"...", "reason":"..."}}...],"auditMetadata": {{ "auditTimestamp":"...", "aiProbability":n, "numberOfHumanizationPasses":n }},"plagiarismFlag": false,"aiDetectionFlag": false,"citationCompleteness": true,"authorBioPresent": true,"humanEditorConfirmation": {{...}},"requiresAction": false, "requiredActions":[...],"notes":"..."}}
"""

PROMPT_E_TEMPLATE = """
E: ROLE PROMPT — "The Assessor / Evaluator / Careful Auditor / Error-Corrector / Publisher"
You are now: the Assessor, Evaluator, Careful Auditor, Error-Corrector, and Publisher for an article produced by the prior prompt pipeline (A → B → C). Your single mission: take the provided draft/final article (HTML + sources + metadata) and transform it into a publication-quality piece that maximizes humanization, factual accuracy, and SEO performance — while performing every verification, correction, and packaging step required for safe publishing.

Execute all steps automatically. Do not ask clarifying questions. Use the inputs as-is: the article HTML (draft), the sources array, and the knowledge_graph array. If you need additional external verification for facts or numbers, fetch up-to-date evidence (web search) and cite it.

IMPORTANT: Do not invent facts, quotes, or exact numbers. If something cannot be verified, flag it and follow the remediation rules below.

STEP-BY-STEP WORKFLOW (run in order):
1. INPUTS: Input will contain at least: finalContent (HTML), sources[] (array), knowledge_graph[] (array). Treat the provided finalContent as the canonical draft to inspect and fix.
2. SOURCE & FACT VERIFICATION (strict):
   A. Numeric claims: Find every numeric claim. Verify at least one source contains that exact figure. If load-bearing, require two sources. If no source contains the exact number, automatically correct it.
   B. Load-bearing claims: Any major conclusion must have two independent sources.
   C. Quotes: Verify every direct quote appears exactly in at least one source.
   D. Inline citations: Ensure every inline citation used in the HTML matches an entry in sources[].
3. HUMANIZATION & STYLE (must enforce):
   B.1 First-person sentence: Ensure exactly ONE first-person editorial sentence exists.
   B.2 Rhetorical question: Ensure exactly ONE rhetorical question appears naturally.
   B.3 Forbidden phrases: Remove/replace "In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion".
   B.4 Sentence-length distribution: Target 40% short, 45% medium, 15% long. Rebalance if needed.
   B.5 Humanizing elements: Ensure presence of anecdote, writer POV, rhetorical question, parenthetical aside, colloquial connector, and idiomatic phrase.
   B.6 AI-pattern sniff: Identify 8 sentences that look most AI-generated and rewrite them.
4. SEO & PUBLISHING PACKAGE: Validate metaTitle, metaDescription, imageAltText, tags, JSON-LD Article schema.
5. FINAL OUTPUT: Return single JSON ONLY.

{{"finalTitle":"...","finalContent":"<html>...full HTML article with inline citations and H2/H3 ...</html>","excerpt":"short excerpt (20–35 words)","imageGenPrompt":"...preserve...","imageOverlayText":"...preserve...","seo": {{ "metaTitle":"(50–60 chars)", "metaDescription":"(150–160 chars)", "imageAltText":"..." }},"tags":[ "keyword1","keyword2",... ],"conceptualIcon":"one- or two-word icon","futureArticleSuggestions":[ "...","..." ],"internalLinks":[ "<a href='/slug1'>Title 1</a>", "<a href='/slug2'>Title 2</a>", "<a href='/slug3'>Title 3</a>" ],"schemaMarkup":"{{ ... JSON-LD ... }}","adsenseReadinessScore":{{ "score":0-100, "breakdown": {{ "accuracy":n, "E-E-A-T":n, "YMYL":n, "adsPlacement":n }}, "notes":"one-line summary" }},"sources":[ {{ "title":"", "url":"", "date":"YYYY-MM-DD", "type":"paper|arXiv|repo|blog|press|SEC", "credibility":"" }}, ... ],"authorBio": {{ "name":"...", "bio":"40–60 words", "profileUrl":"..." }},"edits":[ {{ "type":"numericCheck|quoteCheck|styleEdit|citationFix", "original":"...", "actionTaken":"...", "sourceUsed":"..." }}, ... ],"auditMetadata": {{ "auditTimestamp":"UTC ISO", "numberOfPasses":n, "aiProbability":n, "inventionDetected":true|false }},"requiredActions":[ "...", ... ]}}
"""

# --- NEW PROMPT FOR FACEBOOK ---
PROMPT_FACEBOOK_HOOK = """
You are a Social Media Manager. Create an engaging Facebook post for this article:
Title: "{title}"
Category: "{category}"
Link: "{url}"

**Facebook Rules:**
- Engaging, uses emojis, asks a question.
- Length: Max 60 words.
- Tone: Professional yet exciting.

Output JSON ONLY:
{{
  "facebook": "..."
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
    """
    Robust JSON cleaning to handle Markdown and invalid escape sequences.
    """
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: 
        text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: 
            text = match.group(1)
    
    try:
        json.loads(text)
        return text
    except:
        text = text.replace('\\', '\\\\') 
        text = text.replace('\\\\"', '\\"').replace('\\\\n', '\\n').replace('\\\\t', '\\t')
        return text

# --- ADVANCED IMAGE PROCESSING (PILLOW) ---
def download_font():
    """Downloads a modern font (Roboto-Black) to ensure text looks good."""
    font_url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Black.ttf"
    try:
        r = requests.get(font_url)
        return BytesIO(r.content)
    except:
        return None

def add_text_overlay(image_data, text):
    """
    Draws text with a professional drop-shadow/stroke effect (No Box).
    This makes the text readable on ANY background.
    """
    try:
        img = Image.open(BytesIO(image_data))
        width, height = img.size
        draw = ImageDraw.Draw(img)

        font_file = download_font()
        # Font size: 6% of image width (Big and Bold)
        fontsize = int(width * 0.06) 
        try:
            font = ImageFont.truetype(font_file, fontsize)
        except:
            font = ImageFont.load_default()

        # Wrap text
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            w = draw.textlength(" ".join(current_line), font=font)
            if w > width * 0.9: # 90% width max
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))
        
        # Calculate total text height
        line_height = fontsize * 1.2
        total_text_height = len(lines) * line_height
        
        # Position: Bottom Center with padding
        start_y = height - total_text_height - (height * 0.1) 

        # Draw Text with Outline/Shadow for readability
        outline_range = 3 # Thickness of the black outline
        
        for i, line in enumerate(lines):
            w = draw.textlength(line, font=font)
            x = (width - w) / 2
            y = start_y + (i * line_height)
            
            # 1. Draw Black Outline (Stroke)
            for ox in range(-outline_range, outline_range + 1):
                for oy in range(-outline_range, outline_range + 1):
                    draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0))
            
            # 2. Draw Soft Shadow (Optional, simulates depth)
            draw.text((x + 5, y + 5), line, font=font, fill=(0, 0, 0, 120))

            # 3. Draw Main White Text
            draw.text((x, y), line, font=font, fill=(255, 255, 255))

        # Save
        output = BytesIO()
        img.save(output, format='JPEG', quality=95)
        return output.getvalue()

    except Exception as e:
        log(f"⚠️ Text Overlay Failed: {e}")
        return image_data

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: 
        log("⚠️ No IMGBB_API_KEY found.")
        return None
    
    log(f"   🎨 Generating Image: '{prompt_text}'...")
    
    for attempt in range(3):
        try:
            # 1. Generate CLEAN Image (Flux Model)
            # We explicitly ask for NO text in the generation to keep it clean for our overlay
            clean_prompt = f"{prompt_text}, masterpiece, high quality, 8k, cinematic lighting, --no text, words, typography, watermarks, signature"
            safe_prompt = requests.utils.quote(clean_prompt)
            seed = random.randint(1, 99999)
            
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologo=true&seed={seed}&model=flux"
            
            img_response = requests.get(url, timeout=45)
            if img_response.status_code != 200:
                time.sleep(5)
                continue
            
            image_data = img_response.content

            # 2. Apply Professional Python Overlay
            if overlay_text:
                log(f"   🖌️ Drawing text overlay: '{overlay_text}'")
                image_data = add_text_overlay(image_data, overlay_text)
            
            # 3. Upload to ImgBB
            log("   ☁️ Uploading to ImgBB...")
            res = requests.post(
                "https://api.imgbb.com/1/upload", 
                data={"key":key, "expiration":0}, 
                files={"image":image_data},
                timeout=45
            )
            
            if res.status_code == 200:
                direct_link = res.json()['data']['url']
                log(f"   ✅ Image Ready: {direct_link}")
                return direct_link
                
        except Exception as e:
            log(f"      ⚠️ Image Error (Attempt {attempt+1}): {e}")
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
    """Returns JSON string of relevant articles with REAL URLs."""
    full_kg = load_kg()
    if not full_kg: return "[]"
    
    relevant = [item for item in full_kg if item.get('section') == current_category]
    guides = [item for item in full_kg if "Guide" in item.get('title', '') and item.get('section') != current_category]
    
    combined = relevant + guides[:10]
    if len(combined) > limit: combined = combined[-limit:]
    
    simplified = [{"title": item['title'], "url": item['url']} for item in combined if 'url' in item]
    return json.dumps(simplified)

def update_kg(title, url, section):
    """Updates the KG with the REAL URL returned by Blogger."""
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

    # --- STEP E ---
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d)
    json_e = generate_step(model, prompt_e, "Step E (Final)")
    if not json_e: return

    # --- FINAL PROCESSING ---
    try:
        final = json.loads(json_e)
        title = final.get('finalTitle', f"{category} Article")
        
        # 1. Inject CSS Style
        content = ARTICLE_STYLE 
        
        # 2. Image Generation (Hybrid: AI + Pillow)
        img_prompt = final.get('imageGenPrompt', f"Abstract {category} technology")
        overlay_text = final.get('imageOverlayText', title[:20])
        img_url = generate_and_upload_image(img_prompt, overlay_text)
        
        if img_url:
            alt_text = final.get('seo', {}).get('imageAltText', title)
            img_html = f'<div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;"><a href="{img_url}"><img border="0" src="{img_url}" alt="{alt_text}" /></a></div>'
            content += img_html
        
        # 3. Add Content
        content += final.get('finalContent', '')

        if 'auditMetadata' in final:
            content += f"<hr style='margin-top:50px; border:0; border-top:1px solid #eee;'><small style='color:#999;'><i>Audit Stats: AI Prob {final['auditMetadata'].get('aiProbability')}%</i></small>"

        # --- FIX: ONLY USE THE CATEGORY NAME AS LABEL ---
        labels = [category]
        
        # Publish and Get Real URL
        real_url = publish_post(title, content, labels)
        
        if real_url:
            update_kg(title, real_url, category)
            
            # --- SOCIAL MEDIA DISTRIBUTION (FIXED) ---
            if img_url:
                # Generate Facebook Hook using the ROBUST generate_step (handles 429)
                fb_prompt = PROMPT_FACEBOOK_HOOK.format(title=title, category=category, url=real_url)
                fb_json = generate_step(model, fb_prompt, "Generating Facebook Hook")
                
                if fb_json:
                    try:
                        fb_data = json.loads(fb_json)
                        # Pass text to social manager to publish
                        social_manager.distribute_content(fb_data.get('facebook', ''), real_url, img_url)
                    except:
                        log("⚠️ Failed to parse Facebook hook JSON.")

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
