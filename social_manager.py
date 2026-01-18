import os
import requests
import json
import tweepy
from google import genai
from google.genai import types

def generate_social_hooks(client, model_name, title, category, url):
    """
    يولد 3 منشورات مختلفة بطلب واحد فقط لتوفير الرصيد.
    """
    prompt = f"""
    You are a Social Media Manager. Create 3 distinct posts for this article:
    Title: "{title}"
    Category: "{category}"
    Link: "{url}"

    1. **Facebook:** Engaging, uses emojis, asks a question. (Max 60 words).
    2. **X (Twitter):** Short, punchy, uses hashtags. (Max 200 chars).
    3. **Pinterest:** SEO-rich title and description.

    Output JSON ONLY:
    {{
      "facebook": "...",
      "twitter": "...",
      "pinterest_title": "...",
      "pinterest_desc": "..."
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

def post_to_twitter(content, image_url, link):
    consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
    consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

    if not consumer_key: 
        print("⚠️ Twitter credentials missing.")
        return

    try:
        auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
        api = tweepy.API(auth)

        img_data = requests.get(image_url).content
        with open("temp_tweet_img.jpg", "wb") as f:
            f.write(img_data)

        media = api.media_upload("temp_tweet_img.jpg")
        
        client = tweepy.Client(
            consumer_key=consumer_key, consumer_secret=consumer_secret,
            access_token=access_token, access_token_secret=access_token_secret
        )

        text = f"{content}\n{link}"
        client.create_tweet(text=text, media_ids=[media.media_id])
        print("   ✅ Posted to X (Twitter).")
        os.remove("temp_tweet_img.jpg")

    except Exception as e:
        print(f"   ❌ Twitter Error: {e}")

def post_to_pinterest(title, desc, image_url, link):
    access_token = os.getenv('PINTEREST_ACCESS_TOKEN')
    board_id = os.getenv('PINTEREST_BOARD_ID') 

    if not access_token:
        print("⚠️ Pinterest credentials missing.")
        return

    try:
        if not board_id:
            boards_req = requests.get("https://api.pinterest.com/v5/boards", headers={"Authorization": f"Bearer {access_token}"})
            if boards_req.status_code == 200:
                items = boards_req.json().get('items', [])
                if items:
                    board_id = items[0]['id']
                else:
                    print("   ⚠️ No Pinterest Boards found.")
                    return
        
        url = "https://api.pinterest.com/v5/pins"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": desc[:500],
            "link": link,
            "media": {"source_type": "image_url", "url": image_url}
        }
        
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code == 201:
            print("   ✅ Posted to Pinterest.")
        else:
            print(f"   ❌ Pinterest Failed: {r.text}")

    except Exception as e:
        print(f"   ❌ Pinterest Error: {e}")

def distribute_content(client, model_name, title, category, article_url, image_url):
    print(f"\n📢 Distributing to Social Media...")
    hooks = generate_social_hooks(client, model_name, title, category, article_url)
    if not hooks: return

    post_to_facebook(hooks['facebook'], image_url, article_url)
    post_to_twitter(hooks['twitter'], image_url, article_url)
    post_to_pinterest(hooks['pinterest_title'], hooks['pinterest_desc'], image_url, article_url)
