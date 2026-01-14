import os
import json
import time
import re
import requests
from google import genai
from google.genai import types

# ==========================================
# DEFINING THE PROMPT CHAIN (CONSTANTS)
# ==========================================

PROMPT_A_TEMPLATE = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index (Google Search, Google Scholar, arXiv, official blogs, SEC/10-Q when financial figures are used) for one specific, high-impact case, study, deployment, or company announcement that occurred within {date_range}.

SECTION FOCUS: {section} (See config for specific focus details).

MANDATORY SOURCE & VERIFICATION RULES (follow EXACTLY):
1. Return exactly one headline (plain English, single line).
2. Provide 2–3 primary sources that verify the story.
3. Output JSON only, EXACTLY in this format:
{{"headline": "One-line headline","sources": [{{"title":"Title","url":"...","date":"YYYY-MM-DD","type":"paper|arXiv|repo|blog|press|SEC","why":"...","credibility":"..."}}],"riskNote":"..."}}
"""

PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A.
Input Data: {input_json}

Write a polished HTML article (1500–2000 words).
I. STRUCTURE & VOICE RULES:
- H1 = headline exactly as provided.
- Intro: Human hook, no "Imagine".
- Tone: Journalistic, conversational.
- 40% short, 45% medium, 15% long sentences.
- Include one first-person editorial sentence.
- Include one rhetorical question.
- NO FORBIDDEN PHRASES: "In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion".

II. FORMATTING:
- Use H2 and H3 tags.
- Add one comparison table (text-only representation in HTML).
- Add "Sources" <ul> at the end.

Output JSON ONLY:
{{"draftTitle":"...","draftContent":"<html>...full HTML article...</html>","sources":[...],"notes":"..."}}
"""

PROMPT_C_TEMPLATE = """
C:You are Strategic Editor & SEO consultant. Input: {input_json} (Draft from B).
1. Add 3 "Key takeaways" bullets.
2. Provide metaTitle (50-60 chars) and metaDescription (150-160 chars).
3. Generate Article schema JSON-LD.
4. Run Adsense readiness check.
5. Return JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...final polished HTML...</html>","seo": {{ "metaTitle":"...","metaDescription":"..." }},"tags":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}}}}
"""

PROMPT_D_TEMPLATE = """
D:You are the Humanization & Final Audit specialist. Input: {input_json} (Output from C).
MANDATORY CHECKS:
- Numeric claims: Verify against sources.
- Human Style: Ensure 1 first-person sentence, 1 rhetorical question.
- Remove forbidden phrases ("In today's digital age", etc).
- AI-pattern sniff: Rewrite top 8 AI-sounding sentences.
- Final Output JSON ONLY:
{{"finalContent":"<html>...</html>","auditMetadata":{{...}}, "humanEditorConfirmation": {{...}}, "seo": {{...}} }}
"""

PROMPT_E_TEMPLATE = """
E:You are the Publisher. Transform the audited draft into a publication-quality piece.
Input: {input_json} (Output from D).

Steps:
1. Final sanity check on HTML structure.
2. Ensure no forbidden phrases remain.
3. Ensure YMYL disclaimer is present if needed.
4. Return FINAL JSON ONLY:
{
"finalTitle":"...",
"finalContent":"<html>...full HTML article...</html>",
"tags":[ "keyword1",... ]
}
"""

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

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
        print(f"❌ Error getting access token: {e}")
        return None

def publish_post(title, content, labels):
    token = get_access_token()
    if not token:
        return False
    
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"title": title, "content": content, "labels": labels}
    
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            print(f"✅ Published successfully: {title}")
            return True
        else:
            print(f"❌ Blogger Error: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

def clean_json_text(text):
    """Cleans Markdown code blocks from Gemini output to extract raw JSON."""
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    return text

def generate_with_retry(client, model, prompt, context_msg=""):
    """Helper to handle API calls with retries."""
    for attempt in range(3):
        try:
            # Using the new Google GenAI SDK syntax
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json" # Enforce JSON
                )
            )
            return response.text
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed for {context_msg}: {e}")
            time.sleep(10 * (attempt + 1))
    return None

# ==========================================
# MAIN LOGIC
# ==========================================

def run_trending_chain(client, model_name, category, prompt_a_base, date_range):
    print(f"   ⛓️ Starting Chain for {category}...")
    
    # --- STEP A: RESEARCH ---
    print("      👉 Step A: Research & Headline...")
    prompt_a = PROMPT_A_TEMPLATE.format(section=category, date_range=date_range)
    # Note: We rely on the model's internal knowledge/grounding for "Search"
    # Or enable Google Search Tool if available in your plan. Here we assume standard generation.
    res_a = generate_with_retry(client, model_name, prompt_a, "Step A")
    if not res_a: return None, None
    json_a = clean_json_text(res_a)

    # --- STEP B: DRAFTING ---
    print("      👉 Step B: Drafting...")
    prompt_b = PROMPT_B_TEMPLATE.format(input_json=json_a)
    res_b = generate_with_retry(client, model_name, prompt_b, "Step B")
    if not res_b: return None, None
    json_b = clean_json_text(res_b)

    # --- STEP C: SEO & POLISH ---
    print("      👉 Step C: SEO & Strategy...")
    prompt_c = PROMPT_C_TEMPLATE.format(input_json=json_b)
    res_c = generate_with_retry(client, model_name, prompt_c, "Step C")
    if not res_c: return None, None
    json_c = clean_json_text(res_c)

    # --- STEP D: AUDIT ---
    print("      👉 Step D: Humanization Audit...")
    prompt_d = PROMPT_D_TEMPLATE.format(input_json=json_c)
    res_d = generate_with_retry(client, model_name, prompt_d, "Step D")
    if not res_d: return None, None
    json_d = clean_json_text(res_d)

    # --- STEP E: PUBLISHER ---
    print("      👉 Step E: Final Publisher Package...")
    prompt_e = PROMPT_E_TEMPLATE.format(input_json=json_d)
    res_e = generate_with_retry(client, model_name, prompt_e, "Step E")
    if not res_e: return None, None
    
    try:
        final_data = json.loads(clean_json_text(res_e))
        return final_data.get('finalTitle'), final_data.get('finalContent')
    except json.JSONDecodeError:
        print("❌ Failed to parse final JSON")
        return None, None

def run_evergreen_task(client, model_name, category, prompt_text):
    print(f"   🌲 Generating Evergreen content for {category}...")
    try:
        # Simple generation for evergreen, asking for HTML directly
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_text
        )
        # Extract title manually or ask AI for it? 
        # For simplicity, we assume the H1 is the title or we generate a generic one.
        # Let's ask for a structured response to be safe.
        structured_prompt = prompt_text + "\nReturn result as JSON: {'title': '...', 'content': '<html>...</html>'}"
        
        response = client.models.generate_content(
            model=model_name,
            contents=structured_prompt,
            config=types.GenerateContentConfig(
                    response_mime_type="application/json"
            )
        )
        data = json.loads(clean_json_text(response.text))
        return data.get('title'), data.get('content')
    except Exception as e:
        print(f"❌ Evergreen generation failed: {e}")
        return None, None

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    model_name = config['settings'].get('model_name', 'gemini-2.0-flash-exp') # Or gemini-1.5-flash
    date_range = config['settings'].get('date_range_query', 'last 60 days')

    for category, details in config['categories'].items():
        print(f"\n🚀 Processing Category: {category}")

        # 1. Evergreen Article
        try:
            ev_title, ev_content = run_evergreen_task(client, model_name, category, details['evergreen_prompt'])
            if ev_title and ev_content:
                publish_post(ev_title, ev_content, [category, "AI Guide", "Evergreen"])
                time.sleep(30)
        except Exception as e:
            print(f"Skipping evergreen for {category}: {e}")

        # 2. Trending Article (The Complex Chain)
        try:
            tr_title, tr_content = run_trending_chain(client, model_name, category, details['trending_prompt'], date_range)
            if tr_title and tr_content:
                publish_post(tr_title, tr_content, [category, "AI News", "Trending"])
                print("💤 Cooling down (60s)...")
                time.sleep(60)
        except Exception as e:
            print(f"Skipping trending for {category}: {e}")

if __name__ == "__main__":
    main()
