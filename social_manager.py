import os
import requests
import json
from google import genai
from google.genai import types

# ==============================================================================
# 1. AI CONTENT GENERATOR (Facebook Only)
# ==============================================================================
def generate_social_hooks(client, model_name, title, category, url):
    """
    Generates a post specifically for Facebook.
    """
    prompt = f"""
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
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Social Hook Generation Failed: {e}")
        return None

# ==============================================================================
# 2. FACEBOOK MANAGER
# ==============================================================================
def post_to_facebook(content, image_url, link):
    page_id = os.getenv('FB_PAGE_ID')
    access_token = os.getenv('FB_PAGE_ACCESS_TOKEN')
    
    if not page_id or not access_token:
        print("⚠️ Facebook credentials missing.")
        return

    post_url = f"https://graph.facebook.com/{page_id}/photos"
    payload = {
        'url': image_url,
        'caption': f"{content}\n\n🔗 Read here: {link}",
        'access_token': access_token
    }
    
    try:
        r = requests.post(post_url, data=payload)
        if r.status_code == 200:
            print("   ✅ Posted to Facebook.")
        else:
            print(f"   ❌ Facebook Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ Facebook Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================
def distribute_content(client, model_name, title, category, article_url, image_url):
    print(f"\n📢 Distributing to Social Media (Facebook)...")
    
    hooks = generate_social_hooks(client, model_name, title, category, article_url)
    if not hooks: return

    # Post to Facebook
    post_to_facebook(hooks['facebook'], image_url, article_url)
