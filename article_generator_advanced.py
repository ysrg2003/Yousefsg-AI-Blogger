import os
import json
import time
from datetime import datetime
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# الإعدادات من البيئة
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BLOGGER_CREDENTIALS_JSON = os.getenv('BLOGGER_CREDENTIALS')
BLOGGER_BLOG_ID = os.getenv('BLOGGER_BLOG_ID')

def setup_gemini():
    if not GEMINI_API_KEY: raise ValueError("GEMINI_API_KEY missing")
    genai.configure(api_key=GEMINI_API_KEY)

def get_blogger_service():
    if not BLOGGER_CREDENTIALS_JSON: raise ValueError("BLOGGER_CREDENTIALS missing")
    info = json.loads(BLOGGER_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/blogger'])
    return build('blogger', 'v3', credentials=creds)

def generate_article(config, category):
    # استخدام نموذج gemini-1.5-flash
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = config['categories'][category]['evergreen_prompt']
    
    full_prompt = f"{prompt}\nOutput JSON format with 'title' and 'content' keys. Use HTML for content."
    
    response = model.generate_content(full_prompt)
    try:
        # تنظيف الرد لاستخراج JSON
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        return json.loads(text)
    except:
        print(f"Failed to parse AI response for {category}")
        return None

def publish(service, data):
    body = {
        'title': data['title'],
        'content': data['content'],
        'labels': [data.get('category', 'AI News')]
    }
    service.posts().insert(blogId=BLOGGER_BLOG_ID, body=body, isDraft=False).execute()
    print(f"✅ Published: {data['title']}")

def main():
    setup_gemini()
    service = get_blogger_service()
    
    with open('config_advanced.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for category in config['categories']:
        print(f"Processing {category}...")
        article = generate_article(config, category)
        if article:
            publish(service, article)
            time.sleep(5) # لتجنب الـ Rate Limit

if __name__ == '__main__':
    main()
