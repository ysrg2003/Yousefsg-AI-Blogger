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
        print(f"✅ تم النشر في بلوجر بنجاح: {title}")
        return True
    else:
        print(f"❌ خطأ في بلوجر: {r.text}")
        return False

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
    
    # 🔍 اكتشاف النموذج المتاح
    model_to_use = 'models/gemini-2.5-flash' # الافتراضي الذي نجح معك
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # سنحاول نشر كل الفئات الموجودة في الملف
    for category, details in config['categories'].items():
        print(f"\n🚀 جاري العمل على: {category}")
        
        success = False
        attempts = 0
        max_attempts = 3 # محاولة التوليد 3 مرات في حال كان الخادم مشغولاً
        
        while not success and attempts < max_attempts:
            try:
                response = client.models.generate_content(
                    model=model_to_use,
                    contents=f"Write a comprehensive professional blog post about {category} in HTML format. Use <h2> and <p> tags. Content must be long and informative."
                )
                
                if response and response.text:
                    if publish_post(f"The Future of {category}", response.text, [category, "AI"]):
                        success = True
                        print("💤 انتظار 70 ثانية لضمان استقرار الحصة...")
                        time.sleep(70) # زيادة وقت الانتظار قليلاً لضمان عدم حدوث Overload
                
            except Exception as e:
                attempts += 1
                if "503" in str(e) or "overloaded" in str(e).lower():
                    print(f"⏳ الخادم مشغول (محاولة {attempts}/{max_attempts}). سأنتظر 40 ثانية ثم أحاول مجدداً...")
                    time.sleep(40)
                elif "429" in str(e):
                    print("⏳ تم الوصول للحد الأقصى للطلبات. انتظار دقيقتين...")
                    time.sleep(120)
                else:
                    print(f"❌ فشل غير متوقع: {e}")
                    break # توقف عن المحاولة لهذا القسم وانتقل للتالي

if __name__ == "__main__":
    main()
