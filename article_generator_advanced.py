import os
import json
import time
import requests
from google import genai
from google.genai import errors

# 1. وظيفة الحصول على Access Token (لا تغيير هنا)
def get_access_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    r = requests.post('https://oauth2.googleapis.com/token', data=payload)
    return r.json().get('access_token')

# 2. وظيفة النشر على بلوجر (لا تغيير هنا)
def publish_post(title, content, labels):
    token = get_access_token()
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    data = {"title": title, "content": content, "labels": labels}
    
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        print(f"✅ تم النشر بنجاح: {title}")
    else:
        print(f"❌ فشل النشر: {r.text}")

# 3. وظيفة التوليد مع نظام معالجة الأخطاء والانتظار (Retry Logic)
def generate_article(client, category, prompt_template):
    # جرب 1.5 فلاش أولاً لأنه الأقل استهلاكاً للحصة وأكثر استقراراً للمجاني
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-2.0-flash']
    
    full_prompt = f"{prompt_template}\n\nIMPORTANT: Use HTML tags (h2, p, ul, li). Write a long, professional English article."
    
    for model_name in models_to_try:
        attempts = 0
        while attempts < 2: # محاولتان لكل نموذج
            try:
                print(f"🔄 محاولة استخدام نموذج: {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt
                )
                return response.text
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"⏳ تم الوصول للحد الأقصى. سأنتظر 35 ثانية قبل المحاولة مجدداً...")
                    time.sleep(35) # انتظار إجباري لتفريغ الزحام
                    attempts += 1
                elif "404" in err_msg:
                    print(f"⚠️ النموذج {model_name} غير متاح، سأجرب التالي...")
                    break # اخرج من حلقة attempts لتجربة النموذج التالي
                else:
                    print(f"❌ خطأ غير متوقع: {e}")
                    return None
    return None

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY مفقود!")
        return

    client = genai.Client(api_key=api_key)
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    for category, details in config['categories'].items():
        print(f"\n📂 معالجة القسم: {category}")
        
        article_content = generate_article(client, category, details['evergreen_prompt'])
        
        if article_content:
            title = f"Future of {category}: Comprehensive Guide (2026)"
            publish_post(title, article_content, [category, "AI News Hub"])
            # زيادة وقت الانتظار بين المقالات لتجنب الحظر اليومي
            print("💤 انتظار 20 ثانية قبل الانتقال للقسم التالي...")
            time.sleep(20)
        else:
            print(f"⚠️ فشل توليد محتوى لـ {category} بعد عدة محاولات.")

if __name__ == "__main__":
    main()
