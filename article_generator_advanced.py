import os
import json
import time
import requests
from google import genai # المكتبة الجديدة

# 1. وظيفة الحصول على Access Token
def get_access_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    r = requests.post('https://oauth2.googleapis.com/token', data=payload)
    return r.json().get('access_token')

# 2. وظيفة النشر على بلوجر
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
        print(f"✅ تم النشر: {title}")
    else:
        print(f"❌ فشل النشر: {r.text}")

# 3. وظيفة توليد المقال باستخدام المكتبة الجديدة
def generate_article(client, category, prompt_template):
    full_prompt = f"{prompt_template}\n\nIMPORTANT: Use HTML tags for formatting (h2, p, ul, li). Write a long, professional article in English."
    
    try:
        # استخدام الطريقة الجديدة لاستدعاء Gemini
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        print(f"❌ خطأ في توليد المحتوى لـ {category}: {e}")
        return None

def main():
    # إعداد العميل الجديد
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    
    # تحميل الإعدادات
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for category, details in config['categories'].items():
        print(f"🤖 جاري توليد مقال لـ: {category}...")
        
        article_content = generate_article(client, category, details['evergreen_prompt'])
        if article_content:
            title = f"Latest Insights: {category} in 2026"
            publish_post(title, article_content, [category, "AI News Hub"])
            time.sleep(10) # انتظار لتجنب الحظر

if __name__ == "__main__":
    main()
