import os
import json
import time
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def main():
    # 1. الإعدادات
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    BLOGGER_CREDENTIALS = os.getenv('BLOGGER_CREDENTIALS')
    BLOGGER_BLOG_ID = os.getenv('BLOGGER_BLOG_ID')

    # 2. إعداد Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # تم تصحيح اسم النموذج

    # 3. إعداد Blogger
    info = json.loads(BLOGGER_CREDENTIALS)
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/blogger'])
    service = build('blogger', 'v3', credentials=creds)

    # 4. تحميل ملف الإعدادات
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 5. دورة النشر
    for category in config['categories']:
        print(f"Generating for {category}...")
        prompt = config['categories'][category]['evergreen_prompt'] + "\nOutput in HTML format with a <h1> title."
        
        try:
            response = model.generate_content(prompt)
            content = response.text
            
            body = {
                'title': f"Latest updates in {category}",
                'content': content,
                'labels': [category]
            }
            
            service.posts().insert(blogId=BLOGGER_BLOG_ID, body=body).execute()
            print(f"✅ Success!")
            time.sleep(10)
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
