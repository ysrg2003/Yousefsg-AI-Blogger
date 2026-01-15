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
# 2. PROMPTS DEFINITIONS
# ==============================================================================

PROMPT_A_TRENDING = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index for one specific, high-impact case within {date_range}.

SECTION FOCUS: {section_focus}

**CRITICAL ANTI-DUPLICATION RULE:**
The following topics have already been covered. DO NOT write about them again:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return exactly one headline (journalist-style).
2. Provide 2–3 primary sources.
3. Output JSON ONLY:
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"...", "type":"...", "why":"...", "credibility":"..."}}], "riskNote":"..."}}
"""

PROMPT_A_EVERGREEN = """
A:You are an expert technical educator specialized in {section}. Outline a comprehensive "Ultimate Guide".

TOPIC PROMPT: {evergreen_prompt}

**CRITICAL ANTI-DUPLICATION RULE:**
Check existing guides. Ensure your angle is DISTINCT:
{recent_titles}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return a headline like "The Ultimate Guide to [Topic]".
2. Provide 2–3 authoritative sources.
3. Output JSON ONLY:
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"...", "type":"...", "why":"...", "credibility":"..."}}], "riskNote":"..."}}
"""

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
**AVAILABLE INTERNAL LINKS (Database):** 
{knowledge_graph}

TASKS:
1. **Strict Internal Linking:** 
   - Scan the draft for concepts matching the "title" in the provided database.
   - IF and ONLY IF a match is found, insert a link using the EXACT "url" provided in the database.
   - Format: `<a href="EXACT_URL_FROM_DB">Keyword</a>`.
   - **CRITICAL:** DO NOT invent links. DO NOT link to 404 pages. If no relevant article exists in the database, DO NOT add any internal links.

2. **Formatting & Design Structure (CRITICAL):**
   - **Key Takeaways:** MUST be wrapped in a div: `<div class="takeaways-box"><h3>🚀 Key Takeaways</h3><ul>...bullets...</ul></div>`.
   - **Tables:** MUST be wrapped in a div: `<div class="table-wrapper"><table>...</table></div>`.
   - **Quotes:** Ensure quotes are in `<blockquote>...</blockquote>`.
   
3. **Image Strategy:**
   - `imageGenPrompt`: Describe a visual specific to the headline.
   - `imageOverlayText`: A very short, punchy text (2-4 words max).

4. SEO: Meta Title/Desc, Tags, Schema.
5. Adsense Check.

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
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match: return match.group(1)
    return text

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
        
        # 2. Image Generation
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
