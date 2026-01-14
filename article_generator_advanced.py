import os
import json
import time
import requests
import re
import random
from google import genai
from google.genai import types

# ==============================================================================
# 1. PROMPTS DEFINITIONS
# ==============================================================================

# --- TRENDING RESEARCH (NEWS) ---
PROMPT_A_TRENDING = """
A:You are an investigative tech reporter specialized in {section}. Search the modern index (Google Search, Google Scholar, arXiv, official blogs) for one specific, high-impact case, study, or announcement from {date_range}.

SECTION FOCUS: {section_focus}

MANDATORY SOURCE & VERIFICATION RULES:
1. Return exactly one headline (journalist-style).
2. Provide 2–3 primary sources (Tech Source + Corroborating Source).
3. For numeric claims, cite exact figures.
4. Output JSON ONLY:
{{"headline": "...", "sources": [{{"title":"...", "url":"...", "date":"...", "type":"...", "why":"...", "credibility":"..."}}], "riskNote":"..."}}
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
B:You are Editor-in-Chief. Input: JSON from Prompt A. Write a polished HTML article (1500–2000 words).
INPUT: {json_input}

RULES:
- H1 = headline.
- Intro: Human hook.
- Tone: Journalistic/Educational.
- 40% short, 45% medium, 15% long sentences.
- 1 First-person sentence.
- 1 Rhetorical question.
- NO FORBIDDEN PHRASES ("In today's digital age", etc).
- Use H2, H3.
- Add Comparison Table.
- Add Sources <ul>.

Output JSON ONLY: {{"draftTitle":"...","draftContent":"<html>...</html>","sources":[...],"notes":"..."}}
"""

PROMPT_C_TEMPLATE = """
C:Strategic Editor & SEO. Input: {json_input}. Knowledge Graph: {knowledge_graph}.
TASKS:
1. Add 3 "Key takeaways".
2. Create Image Prompt (Abstract, Tech, No Humans).
3. Internal Links (3-5).
4. SEO (Meta Title/Desc, Tags, Schema).
5. Adsense Check.

Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","seo":{{...}},"tags":[...],"internalLinks":[...],"schemaMarkup":"{{...}}","adsenseReadinessScore":{{...}},"sources":[...],"authorBio":{{...}}}}
"""

PROMPT_D_TEMPLATE = """
D:Humanization & Audit. Input: {json_input}.
CHECKS:
- Verify Numeric Claims & Quotes.
- Ensure Human Style (1st person, rhetorical Q).
- Remove Forbidden Phrases.
- Rewrite AI-sounding sentences.
- Check YMYL.

Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","seo":{{...}},"tags":[...],"auditMetadata":{{...}},"humanEditorConfirmation":{{...}}}}
"""

PROMPT_E_TEMPLATE = """
E:Publisher. Final Sanity Check.
Input: {json_input}
Output JSON ONLY: {{"finalTitle":"...","finalContent":"...","imageGenPrompt":"...","seo":{{...}},"tags":[...],"auditMetadata":{{...}}}}
"""

# ==============================================================================
# 2. KEY MANAGER (ROTATION LOGIC)
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        # Load keys 1 through 4
        for i in range(1, 5):
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
    except:
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
        return r.status_code == 200
    except:
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
    if not key: return None
    print(f"   🎨 Generating Image...")
    try:
        safe_prompt = requests.utils.quote(f"{prompt_text}, abstract, futuristic, 3d render, --no people, text")
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1280&height=720&nologo=true&seed={random.randint(1,999)}"
        img_data = requests.get(url, timeout=30).content
        
        res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":img_data})
        if res.status_code == 200:
            return res.json()['data']['url']
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
        
        # Image
        img_prompt = final.get('imageGenPrompt', f"Abstract {category}")
        img_url = generate_and_upload_image(img_prompt)
        if img_url:
            content = f'<div class="separator" style="clear: both; text-align: center;"><a href="{img_url}"><img src="{img_url}" alt="{title}" /></a></div><br />' + content

        # Metadata Footer
        if 'auditMetadata' in final:
            content += f"<hr><small><i>Audit: AI Prob {final['auditMetadata'].get('aiProbability')}%</i></small>"

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
