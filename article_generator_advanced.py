import os
import json
import time
import requests
from google import genai

def get_access_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    r = requests.post('https://oauth2.googleapis.com/token', data=payload)
    return r.json().get('access_token')

def publish_post(title, content, labels):
    token = get_access_token()
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"title": title, "content": content, "labels": labels}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        print(f"✅ Success: {title}")
    else:
        print(f"❌ Blogger Error: {r.text}")

def generate_article(client, category, prompt):
    # استخدام اسم النموذج المباشر (الأكثر استقراراً في v1)
    model_name = 'gemini-1.5-flash' 
    
    try:
        print(f"🔄 Generating for {category} using {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=f"Write a 1000-word blog post about {category} in HTML format. Topic: {prompt}"
        )
        if response and response.text:
            return response.text
        return None
    except Exception as e:
        print(f"⚠️ Gemini Error: {str(e)}")
        return None

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # معالجة أول 3 أقسام فقط في كل مرة لتجنب الحظر (Quota Management)
    categories = list(config['categories'].items())[:4] 

    for category, details in categories:
        print(f"\n--- Starting: {category} ---")
        
        article_content = generate_article(client, category, details['evergreen_prompt'])
        
        if article_content:
            publish_post(f"Guide to {category}", article_content, [category])
            print("💤 Waiting 60 seconds (Anti-Ban delay)...")
            time.sleep(60) # انتظار طويل لضمان عدم تجاوز الـ Quota
        else:
            print("⏳ Rate limit hit or error. Waiting 2 minutes...")
            time.sleep(120) # إذا فشل، انتظر دقيقتين كاملتين

if __name__ == "__main__":
    main()
