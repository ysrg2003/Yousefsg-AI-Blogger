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
    
    # 🛠️ الحل الجذري: إجبار المكتبة على استخدام الإصدار v1 المستقر بدلاً من v1beta
    client = genai.Client(
        api_key=api_key,
        http_options={'api_version': 'v1'}
    )
    
    print("🔍 جاري فحص النماذج المتاحة في حسابك (إصدار v1)...")
    model_to_use = None
    try:
        # تصحيح طريقة جلب النماذج للمكتبة الجديدة
        for m in client.models.list():
            # في المكتبة الجديدة نتحقق من supported_actions
            if 'generateContent' in m.supported_actions or 'generate_content' in str(m.supported_actions):
                print(f"Found: {m.name}")
                # نفضل نماذج flash لأنها الأسرع في الحصة المجانية
                if 'flash' in m.name.lower():
                    model_to_use = m.name
                    break
        
        if not model_to_use:
            # محاولة أخيرة: استخدام الاسم المباشر بدون بادئة models/
            model_to_use = 'gemini-1.5-flash'
            
    except Exception as e:
        print(f"⚠️ فشل الفحص التلقائي: {e}")
        model_to_use = 'gemini-1.5-flash'

    print(f"🎯 النموذج الذي سيتم استخدامه: {model_to_use}")

    # تحميل الإعدادات
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # معالجة أول قسمين فقط للتأكد من تخطي الـ Quota
    categories = list(config['categories'].items())[:2]

    for category, details in categories:
        print(f"\n🚀 جاري توليد مقال لـ: {category}")
        try:
            # طلب التوليد
            response = client.models.generate_content(
                model=model_to_use,
                contents=f"Write a very long professional blog post about {category} in HTML format. Include headers and lists."
            )
            
            if response and response.text:
                publish_post(f"The Definitive Guide to {category}", response.text, [category])
                print("💤 انتظار دقيقة كاملة لتجنب حظر الحصة المجانية...")
                time.sleep(60)
            else:
                print(f"⚠️ استجابة فارغة من النموذج لـ {category}")
                
        except Exception as e:
            if "429" in str(e):
                print("⏳ تم استهلاك الحصة. توقف مؤقت لمدة دقيقتين...")
                time.sleep(120)
            else:
                print(f"❌ فشل التوليد: {e}")

if __name__ == "__main__":
    main()
