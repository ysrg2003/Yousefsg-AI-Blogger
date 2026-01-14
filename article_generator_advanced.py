import os
import json
import time
import requests
import google.generativeai as genai

# 1. وظيفة الحصول على Access Token جديد
def get_access_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    r = requests.post('https://oauth2.googleapis.com/token', data=payload)
    if r.status_code != 200:
        raise Exception(f"فشل في جلب Token: {r.text}")
    return r.json().get('access_token')

# 2. وظيفة النشر على بلوجر
def publish_post(title, content, labels):
    token = get_access_token()
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    data = {
        "kind": "blogger#post",
        "title": title,
        "content": content,
        "labels": labels
    }
    
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        print(f"✅ تم نشر المقال بنجاح: {title}")
    else:
        print(f"❌ فشل النشر: {r.text}")

# 3. وظيفة توليد المقال باستخدام Gemini
def generate_article(category, prompt_template):
    model = genai.GenerativeModel('gemini-1.5-flash')
    full_prompt = f"{prompt_template}\n\nIMPORTANT: Use HTML tags for formatting (h2, p, ul, li). Write a long, professional article in English."
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"❌ خطأ في توليد المحتوى لـ {category}: {e}")
        return None

def main():
    # إعداد Gemini
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    
    # تحميل الإعدادات
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for category, details in config['categories'].items():
        print(f"🤖 جاري العمل على فئة: {category}...")
        
        # توليد ونشر مقال الـ Evergreen
        article_content = generate_article(category, details['evergreen_prompt'])
        if article_content:
            title = f"Deep Dive: Understanding {category}"
            publish_post(title, article_content, [category, "AI Insights"])
            time.sleep(15) # انتظار لتجنب ضغط الـ API
            
if __name__ == "__main__":
    main()
