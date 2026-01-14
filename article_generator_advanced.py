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
        print(f"✅ تم النشر في بلوجر بنجاح")
    else:
        print(f"❌ خطأ في بلوجر: {r.text}")

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    
    # 🔍 الخطوة الأهم: اكتشاف النماذج المتاحة في حسابك حالياً
    print("🔍 جاري البحث عن النماذج المتاحة في حسابك...")
    model_to_use = None
    try:
        available_models = [m.name for m in client.models.list() if 'generateContent' in m.supported_methods]
        print(f"📋 النماذج التي تدعم الكتابة في حسابك: {available_models}")
        
        # ترتيب الأولويات: نبحث عن Flash أولاً لأنه الأسرع والأرخص
        for m in available_models:
            if 'flash' in m.lower():
                model_to_use = m
                break
        
        # إذا لم نجد Flash، نأخذ أول نموذج متاح
        if not model_to_use and available_models:
            model_to_use = available_models[0]
            
    except Exception as e:
        print(f"⚠️ فشل استخراج قائمة النماذج: {e}")
        model_to_use = 'gemini-1.5-flash' # محاولة أخيرة بالاسم التقليدي

    if not model_to_use:
        print("❌ لم يتم العثور على أي نموذج متاح للكتابة!")
        return

    print(f"🎯 النموذج المختار للعمل: {model_to_use}")

    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # معالجة أول 3 أقسام فقط لضمان النجاح
    categories = list(config['categories'].items())[:3]

    for category, details in categories:
        print(f"\n🚀 جاري توليد محتوى لـ: {category}")
        try:
            response = client.models.generate_content(
                model=model_to_use,
                contents=f"Write a comprehensive professional blog post about {category} in HTML format. Detailed content is required."
            )
            
            if response and response.text:
                publish_post(f"The Future of {category}", response.text, [category])
                print("💤 انتظار 40 ثانية لتجنب ضغط الـ API...")
                time.sleep(40)
            else:
                print(f"⚠️ النموذج استجاب ولكن بدون نص لـ {category}")
                
        except Exception as e:
            print(f"❌ فشل التوليد لـ {category}: {e}")
            time.sleep(30) # انتظار قبل المحاولة التالية

if __name__ == "__main__":
    main()
