import os
import requests
import json
import tweepy
from google import genai
from google.genai import types

# ==============================================================================
# 1. AI CONTENT GENERATOR (Facebook & Twitter Only)
# ==============================================================================
def generate_social_hooks(client, model_name, title, category, url):
    prompt = f"""
    You are a Social Media Manager. Create 2 distinct posts for this article:
    Title: "{title}"
    Category: "{category}"
    Link: "{url}"

    1. **Facebook:** Engaging, uses emojis, asks a question. (Max 60 words).
    2. **X (Twitter):** Short, punchy, uses hashtags. (Max 200 chars).

    Output JSON ONLY:
    {{
      "facebook": "...",
      "twitter": "..."
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
# 3. X (TWITTER) MANAGER (TEXT ONLY - FREE TIER SAFE)
# ==============================================================================
def post_to_twitter(content, link):
    consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
    consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

    if not consumer_key: 
        print("⚠️ Twitter credentials missing.")
        return

    try:
        # Authenticate v2 Client (Required for Free Tier Posting)
        client = tweepy.Client(
            consumer_key=consumer_key, consumer_secret=consumer_secret,
            access_token=access_token, access_token_secret=access_token_secret
        )

        # Post Text Only (Twitter will generate the card from the link automatically)
        text = f"{content}\n\n{link}"
        
        response = client.create_tweet(text=text)
        print(f"   ✅ Posted to X (Twitter). ID: {response.data['id']}")

    except Exception as e:
        print(f"   ❌ Twitter Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================
def distribute_content(client, model_name, title, category, article_url, image_url):
    print(f"\n📢 Distributing to Social Media...")
    
    hooks = generate_social_hooks(client, model_name, title, category, article_url)
    if not hooks: return

    # 1. Facebook (Image + Text)
    post_to_facebook(hooks['facebook'], image_url, article_url)

    # 2. Twitter (Text + Link Only - to avoid 402 Payment Error)
    post_to_twitter(hooks['twitter'], article_url)
    
    # 3. Pinterest is handled via RSS Auto-Publishing (No code needed)
