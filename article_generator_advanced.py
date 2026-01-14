import os
import json
import time
import requests
import re
import random
from google import genai
from google.genai import types

# ==============================================================================
# 1. PROMPTS DEFINITIONS (UPDATED FOR DUPLICATION & IMAGES)
# ==============================================================================

# --- TRENDING RESEARCH (NEWS) ---
PROMPT_A_TRENDING = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index for one specific, high-impact case within {date_range}.

SECTION FOCUS: {section_focus}

**CRITICAL ANTI-DUPLICATION RULE:**
The following topics have already been covered recently. DO NOT write about them again. Find a DIFFERENT story:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return exactly one headline (journalist-style).
2. Provide 2–3 primary sources.
3. Output JSON ONLY:
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"...", "type":"...", "why":"...", "credibility":"..."}}], "riskNote":"..."}}
"""

# --- EVERGREEN RESEARCH (CONCEPTS) ---
PROMPT_A_EVERGREEN = """
A:You are an expert technical educator specialized in {section}. Outline a comprehensive "Ultimate Guide".

TOPIC PROMPT: {evergreen_prompt}

**CRITICAL ANTI-DUPLICATION RULE:**
Check the following list of existing guides. Ensure your angle or specific topic is DISTINCT or an UPDATE:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return a headline like "The Ultimate Guide to [Topic]".
2. Provide 2–3 authoritative sources.
3. Output JSON ONLY:
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"...", "type":"...", "why":"...", "credibility":"..."}}], "riskNote":"..."}}
"""

# --- COMMON STEPS ---
PROMPT_B_TEMPLATE = """
B:Editor-in-Chief. Input: JSON from Prompt A. Write a polished HTML article (1500–2000 words).
INPUT: {json_input}

RULES:
- H1 = headline.
- Intro: Human hook.
- Tone: Journalistic/Educational.
- 40% short, 45% medium, 15% long sentences.
- 1 First-person sentence.
- 1 Rhetorical question.
- NO FORBIDDEN PHRASES.
- Use H2, H3.
- Add Comparison Table.
- Add Sources <ul>.

Output JSON ONLY: {{"draftTitle":"...","draftContent":"<html>...</html>","sources":[...],"notes":"..."}}
"""

PROMPT_C_TEMPLATE = """
C:Strategic Editor & SEO. Input: {json_input}.
Knowledge Graph (Existing Articles): {knowledge_graph}

TASKS:
1. **Smart Internal Linking:** Scan the draft for concepts that match titles/slugs in the Knowledge Graph. Create 3-5 *contextual* links (e.g., "For more on [Concept], see our [Article Title]"). Do NOT just list links at the bottom; weave them into the text logically.
2. **Image Strategy:**
   - `imageGenPrompt`: Describe a visual specific to the headline (e.g., "A robot hand holding a microchip" NOT just "Technology").
   - `imageOverlayText`: A very short, punchy text (2-4 words max) to be written ON the image (e.g., "AI vs Human", "New GPT-5").
3. SEO: Meta Title/Desc, Tags, Schema.
4. Adsense Check.

Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","imageOverlayText":"...","seo":{{...}},"tags":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}}}}
"""

PROMPT_D_TEMPLATE = """
D:Humanization & Audit. Input: {json_input}.
CHECKS:
- Verify Numeric Claims & Quotes.
- Ensure Human Style.
- Remove Forbidden Phrases.
- Rewrite AI-sounding sentences.
- Check YMYL.

Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","imageOverlayText":"...","seo":{{...}},"tags":[...],"auditMetadata":{{...}},"humanEditorConfirmation":{{...}}}}
"""

PROMPT_E_TEMPLATE = """
E:Publisher. Final Sanity Check.
Input: {json_input}
Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","imageOverlayText":"...","seo":{{...}},"tags":[...],"auditMetadata":{{...}}}}
"""

# ==============================================================================
# 2. KEY MANAGER (6 KEYS)
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
    except: return None

def publish_post(title, content, labels):
    token = get_blogger_token()
    if not token: return False
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"title": title, "content": content, "labels": labels}
    try:
        r = requests.post(url, headers=headers, json=data)
        return r.status_code == 200
    except: return False

def clean_json(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    return text

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    print(f"   🎨 Generating Image: '{prompt_text}' with text '{overlay_text}'...")
    try:
        # 1. Prepare Pollinations URL with Text Overlay
        safe_prompt = requests.utils.quote(f"{prompt_text}, abstract, futuristic, 3d render, high quality, --no people, humans, animals, faces")
        
        # Add text parameter if provided
        text_param = ""
        if overlay_text:
            safe_text = requests.utils.quote(overlay_text)
            text_param = f"&text={safe_text}&font=roboto&fontsize=50"

        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologo=true&seed={random.randint(1,99999)}&model=flux{text_param}"
        
        # 2. Download
        img_response = requests.get(url, timeout=30)
        if img_response.status_code != 200: return None
        
        # 3. Upload to ImgBB
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
        with open('knowledge_graph.json', 'r') as f: return json.load(f)
    except: return []

def get_recent_titles_string():
    kg = load_kg()
    # Get last 50 titles
    titles = [item['title'] for item in kg[-50:]] if kg else []
    return ", ".join(titles)

def update_kg(slug, title, section):
    try:
        data = load_kg()
        # Check if exists
        for item in data:
            if item['slug'] == slug: return
        data.append({"slug": slug, "title": title, "section": section})
        with open('knowledge_graph.json', 'w') as f: json.dump(data, f, indent=2)
    except: pass

# ==============================================================================
# 4. CORE GENERATION LOGIC
# ==============================================================================

def generate_step(model_name, prompt, step_name):
    print(f"   👉 Executing {step_name}...")
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
                print(f"      ⚠️ Quota hit on Key #{key_manager.current_index + 1}.")
                if key_manager.switch_key():
                    print("      🔄 Retrying with new key...")
                    continue
                else: return None
            elif "503" in error_msg:
                time.sleep(30)
                continue
            else:
                print(f"      ❌ Error: {e}")
                return None

# ==============================================================================
# 5. UNIFIED PIPELINE
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name', 'models/gemini-2.5-flash')
    cat_config = config['categories'][category]
    
    print(f"\n🚀 STARTING {mode.upper()} CHAIN FOR: {category}")

    # Get recent titles to prevent duplication
    recent_titles = get_recent_titles_string()

    # --- STEP A: RESEARCH ---
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

    # --- STEP B: DRAFT ---
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=json_a)
    json_b = generate_step(model, prompt_b, "Step B (Drafting)")
    if not json_b: return
    time.sleep(10)

    # --- STEP C: SEO & IMAGES ---
    kg_str = json.dumps(load_kg()) # Pass full KG for linking
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json_b, knowledge_graph=kg_str)
    json_c = generate_step(model, prompt_c, "Step C (SEO & Images)")
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

    # --- FINAL PROCESSING ---
    try:
        final = json.loads(json_e)
        title = final.get('finalTitle', f"{category} Article")
        content = final.get('finalContent', '')
        
        # Image Generation with Overlay
        img_prompt = final.get('imageGenPrompt', f"Abstract {category} technology")
        overlay_text = final.get('imageOverlayText', title[:20]) # Fallback to title start if missing
        
        img_url = generate_and_upload_image(img_prompt, overlay_text)
        
        if img_url:
            alt_text = final.get('seo', {}).get('imageAltText', title)
            img_html = f'<div class="separator" style="clear: both; text-align: center;"><a href="{img_url}" style="margin-left: 1em; margin-right: 1em;"><img border="0" src="{img_url}" alt="{alt_text}" data-original-width="1280" data-original-height="720" /></a></div><br />'
            content = img_html + content

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

    for category in config['categories']:
        run_pipeline(category, config, mode="trending")
        print("💤 Cooling down (30s)...")
        time.sleep(30)
        
        run_pipeline(category, config, mode="evergreen")
        print("💤 Cooling down (30s)...")
        time.sleep(30)

if __name__ == "__main__":
    main()
