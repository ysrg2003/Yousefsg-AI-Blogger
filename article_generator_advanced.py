import os
import json
import time
import requests
import re
import base64
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
1. Return exactly one headline (plain English, single line).
2. Provide 2–3 primary sources that verify the story.
3. Output JSON only, EXACTLY in this format:
{{"headline": "One-line headline","sources": [{{"title":"Exact source title","url":"https://...","date":"YYYY-MM-DD","type":"paper|arXiv|repo|blog|press|SEC","why":"One-line why this verifies","credibility":"short note"}}],"riskNote":"If YMYL risk exists list regulators; otherwise empty string"}}
"""

PROMPT_B_TEMPLATE = """
B:You are Editor-in-Chief of 'AI News Hub'. Input: the JSON output from Prompt A. Write a polished HTML article (1500–2000 words).
INPUT DATA: {json_input}

STRUCTURE & VOICE RULES:
- H1 = headline exactly as provided.
- Intro: Human hook, no "Imagine".
- Tone: Journalistic, conversational.
- 40% short, 45% medium, 15% long sentences.
- Include one first-person editorial sentence.
- Include one rhetorical question.
- NO FORBIDDEN PHRASES: "In today's digital age", "The world of AI is ever-evolving", "This matters because", "In conclusion".

FORMATTING:
- Use H2 and H3 tags.
- Add one comparison table (text-only).
- Add "Sources" <ul> at the end.

Output JSON ONLY:
{{"draftTitle":"...","draftContent":"<html>...full HTML article...</html>","sources":[...],"notes":"..."}}
"""

PROMPT_C_TEMPLATE = """
C:You are Strategic Editor & SEO consultant. Input: {json_input}. Knowledge Graph: {knowledge_graph}
Tasks:
1. Add 3 "Key takeaways" bullets.
2. Provide metaTitle (50-60 chars) and metaDescription (150-160 chars).
3. Generate Article schema JSON-LD.
4. Run Adsense readiness check.
5. Internal Links: Select 3-5 from knowledge graph.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","seo": {{ "metaTitle":"...","metaDescription":"...","imageAltText":"..." }},"tags":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}}}}
"""

PROMPT_D_TEMPLATE = """
PROMPT D — Humanization & Final Audit. Input: {json_input}
MANDATORY CHECKS:
A. Verify numeric claims & sources.
B. Human Style: Ensure 1 first-person sentence, 1 rhetorical question. Remove forbidden phrases.
C. E-E-A-T: Check Author bio.
D. Safety: Add humanEditorConfirmation.

Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","seo": {{...}},"tags":[...],"internalLinks":[...],"schemaMarkup":"...","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}},"auditMetadata": {{...}},"humanEditorConfirmation": {{"editorName": "Yousef Sameer","editorRole": "Human Editor, AI News Hub","confirmationLine": "I have reviewed this article and verified the sources.","dateReviewed": "YYYY-MM-DD"}}}}
"""

PROMPT_E_TEMPLATE = """
E: Publisher Role. Input: {json_input}
Final sanity check and JSON packaging.
Output JSON ONLY:
{{"finalTitle":"...","finalContent":"<html>...</html>","seo": {{...}},"tags":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio": {{...}},"auditMetadata": {{...}}}}
"""

# ==============================================================================
# 2. HELPER FUNCTIONS
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

def clean_json_response(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    return text

def generate_step(client, model, prompt_text, step_name):
    """
    Executes a step using the MODERN SDK (google-genai) with Retry Logic
    """
    print(f"   👉 Executing {step_name}...")
    
    max_retries = 6
    for i in range(max_retries):
        try:
            # Modern SDK Call
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response and response.text:
                return clean_json_response(response.text)
                
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = 60 + (i * 45)
                print(f"      ⏳ Quota Hit (429). Waiting {wait_time}s (Attempt {i+1}/{max_retries})...")
                time.sleep(wait_time)
            elif "404" in error_str:
                print(f"      ❌ Model Not Found: {model}. Check config name.")
                # If 404, waiting won't help usually, but we retry just in case of glitch
                time.sleep(10)
            else:
                print(f"      ❌ Error in {step_name}: {e}")
                time.sleep(20)
    
    print(f"      ❌ Failed {step_name} after retries.")
    return None

def load_knowledge_graph():
    try:
        with open('knowledge_graph.json', 'r') as f: return f.read()
    except: return "[]"

def update_knowledge_graph(slug, title, section):
    try:
        data = []
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json', 'r') as f: data = json.load(f)
        data.append({"slug": slug, "title": title, "section": section})
        with open('knowledge_graph.json', 'w') as f: json.dump(data, f, indent=2)
    except: pass

# ==============================================================================
# 4. IMAGE GENERATION (DIRECT REST API)
# ==============================================================================

def generate_and_upload_image(topic):
    imgbb_key = os.getenv('IMGBB_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    
    if not imgbb_key: return ""

    print(f"   🎨 Generating Image for: {topic}...")
    
    # Using REST API for images is safer/more stable than SDK for now
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={gemini_key}"
    
    prompt = (
        f"A futuristic, high-tech, abstract illustration representing '{topic}'. "
        "Style: 3D isometric render, glowing data streams, silicon chips, server racks, "
        "blue and purple neon lighting, clean minimalist geometry. "
        "CRITICAL RULES: NO humans, NO faces, NO animals. Abstract technology only."
    )
    
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
    }
    
    try:
        r = requests.post(url, json=payload)
        if r.status_code != 200:
            print(f"      ⚠️ Image Gen Error: {r.text}")
            return ""
            
        response_json = r.json()
        if 'predictions' not in response_json:
            return ""
            
        b64_string = response_json['predictions'][0]['bytesBase64Encoded']
        
        # Upload to ImgBB
        print("      ☁️ Uploading to ImgBB...")
        upload_url = "https://api.imgbb.com/1/upload"
        upload_payload = {
            "key": imgbb_key,
            "image": b64_string,
            "name": topic.replace(" ", "_")[:20]
        }
        res = requests.post(upload_url, data=upload_payload)
        if res.status_code == 200:
            img_url = res.json()['data']['url']
            print(f"      ✅ Uploaded: {img_url}")
            return f'<div class="separator" style="clear: both; text-align: center;"><a href="{img_url}" style="margin-left: 1em; margin-right: 1em;"><img border="0" data-original-height="720" data-original-width="1280" src="{img_url}" alt="{topic}" /></a></div><br />'
            
    except Exception as e:
        print(f"      ⚠️ Image Error: {e}")
    
    return ""

# ==============================================================================
# 5. PIPELINES
# ==============================================================================

def run_trending_pipeline(client, model, category, config):
    date_range = config['settings'].get('date_range_query', 'last 60 days')
    cat_config = config['categories'][category]
    section_focus = cat_config.get('trending_focus', '')

    # Step A
    prompt_a = PROMPT_A_TEMPLATE.format(section=category, date_range=date_range, section_focus=section_focus)
    json_a = generate_step(client, model, prompt_a, "Step A (Research)")
    if not json_a: return
    time.sleep(40)

    # Step B
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a)
    json_b = generate_step(client, model, prompt_b, "Step B (Drafting)")
    if not json_b: return
    time.sleep(40)

    # Step C
    kg = load_knowledge_graph()
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b, knowledge_graph=kg)
    json_c = generate_step(client, model, prompt_c, "Step C (SEO)")
    if not json_c: return
    time.sleep(40)

    # Step D
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json_c)
    json_d = generate_step(client, model, prompt_d, "Step D (Audit)")
    if not json_d: return
    time.sleep(40)

    # Step E
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json_d)
    json_e = generate_step(client, model, prompt_e, "Step E (Final Polish)")
    if not json_e: return

    try:
        final_data = json.loads(json_e)
        title = final_data.get('finalTitle', f"New in {category}")
        content = final_data.get('finalContent', '')
        
        # Image
        img_html = generate_and_upload_image(title)
        if img_html: content = img_html + content
        
        # Footer
        if 'humanEditorConfirmation' in final_data:
            editor = final_data['humanEditorConfirmation']
            content += f"""<div style="margin-top:20px; padding:15px; background:#f9f9f9; border-left:4px solid #333;">
            <strong>Human Editor: {editor.get('editorName', 'Yousef Sameer')}</strong><br>
            <em>{editor.get('confirmationLine')}</em><br>
            <small>Reviewed on: {editor.get('dateReviewed')}</small></div>"""

        if publish_post(title, content, [category, "Trending", "AI News"]):
            slug = title.lower().replace(' ', '-').replace(':', '')[:50]
            update_knowledge_graph(slug, title, category)
            
    except Exception as e:
        print(f"❌ Final Publish Error: {e}")

def run_evergreen_pipeline(client, model, category, prompt_text):
    print(f"   🌲 Generating Evergreen Article for {category}...")
    try:
        wrapper = f"{prompt_text}\n\nOutput JSON ONLY: {{'title': '...', 'content': '<html>...</html>'}}"
        json_res = generate_step(client, model, wrapper, "Evergreen Generation")
        if json_res:
            data = json.loads(json_res)
            title = data['title']
            content = data['content']
            
            img_html = generate_and_upload_image(f"{category} Guide")
            if img_html: content = img_html + content
            
            publish_post(title, content, [category, "Guide", "Evergreen"])
            update_knowledge_graph("guide-" + category.lower().replace(' ', '-'), title, category)
    except Exception as e:
        print(f"❌ Evergreen failed: {e}")

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Missing GEMINI_API_KEY")
        return

    # Initialize Modern Client with v1beta to avoid 404s
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Ensure model name is clean (no 'models/' prefix)
    model_name = config['settings'].get('model_name', 'gemini-1.5-flash')
    if model_name.startswith('models/'):
        model_name = model_name.replace('models/', '')
        
    print(f"ℹ️ Using Model: {model_name}")

    for category in config['categories']:
        print(f"\n🚀 PROCESSING CATEGORY: {category}")
        
        run_trending_pipeline(client, model_name, category, config)
        print("💤 Cooling down (120s)...")
        time.sleep(120)
        
        evergreen_prompt = config['categories'][category].get('evergreen_prompt')
        if evergreen_prompt:
            run_evergreen_pipeline(client, model_name, category, evergreen_prompt)
            print("💤 Cooling down (120s)...")
            time.sleep(120)

if __name__ == "__main__":
    main()
