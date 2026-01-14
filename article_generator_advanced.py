import os
import json
import time
import requests
from google import genai

# 1. وظيفة الحصول على Access Token (كما هي)
def get_access_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    r = requests.post('https://oauth2.googleapis.com/token', data=payload)
    return r.json().get('access_token')

# 2. وظيفة النشر على بلوجر (كما هي)
def publish_post(title, content, labels):
    token = get_access_token()
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    data = {
        "title": title,
        "content": content,
        "labels": labels
    }
    
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        print(f"✅ Published successfully: {title}")
    else:
        print(f"❌ Publishing failed: {r.text}")

# 3. وظيفة التوليد مع تجربة نماذج مختلفة لتجنب خطأ 404
def generate_article(client, category, prompt_template):
    # نحاول استخدام Gemini 2.0 أولاً لأنه الأحدث في 2026، ثم نعود لـ 1.5
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash']
    
    full_prompt = f"{prompt_template}\n\nIMPORTANT: Use HTML tags (h2, p, ul, li). Write a professional English article."
    
    for model_name in models_to_try:
        try:
            print(f"🔄 Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            if "404" in str(e):
                continue # جرب النموذج التالي
            else:
                print(f"❌ Error with {model_name}: {e}")
                return None
    return None

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY is missing!")
        return

    # إنشاء العميل
    client = genai.Client(api_key=api_key)
    
    # تحميل الإعدادات
    try:
        with open('config_advanced.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config_advanced.json not found!")
        return

    for category, details in config['categories'].items():
        print(f"\n🤖 Processing category: {category}")
        
        article_content = generate_article(client, category, details['evergreen_prompt'])
        
        if article_content:
            title = f"Evolution of {category}: Future Perspectives"
            publish_post(title, article_content, [category, "AI 2026"])
            # انتظار 10 ثوانٍ لتجنب تخطي حدود الـ API
            time.sleep(10)
        else:
            print(f"⚠️ Could not generate content for {category}")

if __name__ == "__main__":
    main()
