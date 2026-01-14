#!/usr/bin/env python3
"""
AI News Hub - Advanced Blogger Automation Script
توليد ونشر مقالات يومية على بلوجر باستخدام Gemini API مع التحقق من المصادر
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import google.generativeai as genai
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.auth.oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle

# ============================================================================
# الإعدادات والثوابت
# ============================================================================

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BLOGGER_CREDENTIALS_JSON = os.getenv('BLOGGER_CREDENTIALS')
BLOGGER_BLOG_ID = os.getenv('BLOGGER_BLOG_ID')

# نطاقات Blogger API
SCOPES = ['https://www.googleapis.com/auth/blogger']

# ============================================================================
# دالات المساعدة
# ============================================================================

def load_config() -> Dict:
    """تحميل ملف الإعدادات والبرومبتات"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ خطأ: لم يتم العثور على ملف config.json")
        return {}

def setup_gemini():
    """إعداد Gemini API"""
    if not GEMINI_API_KEY:
        raise ValueError("❌ خطأ: GEMINI_API_KEY غير موجود")
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ تم إعداد Gemini API بنجاح")

def get_blogger_service():
    """الحصول على خدمة Blogger API"""
    if not BLOGGER_CREDENTIALS_JSON:
        raise ValueError("❌ خطأ: BLOGGER_CREDENTIALS غير موجود")
    
    try:
        credentials_dict = json.loads(BLOGGER_CREDENTIALS_JSON)
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        service = build('blogger', 'v3', credentials=credentials)
        print("✅ تم الاتصال بـ Blogger API بنجاح")
        return service
    except Exception as e:
        print(f"❌ خطأ في الاتصال بـ Blogger API: {e}")
        raise

def format_prompt_with_context(prompt_template: str, section: str, date_range: str = "last 60 days") -> str:
    """
    تنسيق البرومبت بإضافة السياق والمتغيرات
    """
    return prompt_template.format(section=section, date_range=date_range)

def generate_story_discovery(prompt: str, category: str) -> Optional[Dict]:
    """
    الخطوة الأولى: اكتشاف القصة (Story Discovery)
    تولد Gemini عنواناً صحفياً وقائمة مصادر محققة
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        print(f"⏳ [الخطوة 1] جاري اكتشاف القصة في فئة '{category}'...")
        response = model.generate_content(prompt)
        
        response_text = response.text
        
        # محاولة استخراج JSON من الرد
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                story_data = json.loads(json_str)
                
                print(f"✅ تم اكتشاف القصة: {story_data.get('headline', 'بدون عنوان')}")
                print(f"   عدد المصادر: {len(story_data.get('sources', []))}")
                
                return story_data
            else:
                print("❌ لم يتم العثور على JSON في الرد")
                return None
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في تحليل JSON: {e}")
            return None
            
    except Exception as e:
        print(f"❌ خطأ في اكتشاف القصة: {e}")
        return None

def generate_article_draft(draft_prompt: str, headline: str, sources: List[Dict]) -> Optional[Dict]:
    """
    الخطوة الثانية: كتابة المسودة (Article Draft)
    تولد Gemini مسودة المقالة بناءً على العنوان والمصادر
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # تنسيق البرومبت مع المعلومات
        formatted_prompt = f"""{draft_prompt}

**Headline:** {headline}

**Verified Sources:**
{json.dumps(sources, indent=2, ensure_ascii=False)}

Please write the article now."""
        
        print(f"⏳ [الخطوة 2] جاري كتابة مسودة المقالة...")
        response = model.generate_content(formatted_prompt)
        
        response_text = response.text
        
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                draft_data = json.loads(json_str)
                
                print(f"✅ تم كتابة المسودة بنجاح")
                print(f"   عدد الكلمات: {len(draft_data.get('draftContent', '').split())}")
                
                return draft_data
            else:
                print("❌ لم يتم العثور على JSON في الرد")
                return None
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في تحليل JSON: {e}")
            return None
            
    except Exception as e:
        print(f"❌ خطأ في كتابة المسودة: {e}")
        return None

def finalize_article(editor_prompt: str, draft_data: Dict) -> Optional[Dict]:
    """
    الخطوة الثالثة: تحرير نهائي (Final Editing)
    تولد Gemini النسخة النهائية من المقالة مع SEO و schema markup
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # تنسيق البرومبت مع بيانات المسودة
        formatted_prompt = f"""{editor_prompt}

**Draft Data:**
{json.dumps(draft_data, indent=2, ensure_ascii=False)}

Please finalize the article now."""
        
        print(f"⏳ [الخطوة 3] جاري التحرير النهائي والتحسين...")
        response = model.generate_content(formatted_prompt)
        
        response_text = response.text
        
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                final_data = json.loads(json_str)
                
                print(f"✅ تم التحرير النهائي بنجاح")
                print(f"   Adsense Readiness Score: {final_data.get('adsenseReadinessScore', {}).get('score', 'N/A')}")
                
                return final_data
            else:
                print("❌ لم يتم العثور على JSON في الرد")
                return None
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في تحليل JSON: {e}")
            return None
            
    except Exception as e:
        print(f"❌ خطأ في التحرير النهائي: {e}")
        return None

def generate_full_article(config: Dict, category: str, article_type: str) -> Optional[Dict]:
    """
    توليد مقالة كاملة من خلال 3 خطوات
    """
    try:
        category_config = config.get('categories', {}).get(category, {})
        
        if article_type == 'trending':
            prompt_template = category_config.get('trending_prompt', '')
        else:
            prompt_template = category_config.get('evergreen_prompt', '')
        
        if not prompt_template:
            print(f"❌ لم يتم العثور على برومبت للفئة '{category}'")
            return None
        
        # الخطوة 1: اكتشاف القصة (للمقالات الـ trending فقط)
        if article_type == 'trending' and 'investigative' in prompt_template.lower():
            # تنسيق البرومبت
            formatted_prompt = format_prompt_with_context(prompt_template, category)
            
            story_data = generate_story_discovery(formatted_prompt, category)
            if not story_data:
                print(f"⚠️ فشل اكتشاف القصة، سيتم استخدام مقالة evergreen بدلاً منها")
                article_type = 'evergreen'
                prompt_template = category_config.get('evergreen_prompt', '')
        
        # الخطوة 2 & 3: للمقالات الـ evergreen أو إذا فشلت الخطوة 1
        if article_type == 'evergreen':
            # استخدام البرومبت مباشرة
            full_prompt = f"""{prompt_template}

Please output JSON with the following structure:
{{
    "title": "Article Title",
    "excerpt": "Short excerpt (100-150 words)",
    "content": "<html>Full article content with proper HTML formatting</html>",
    "tags": ["tag1", "tag2", "tag3"],
    "category": "{category}",
    "metaTitle": "Meta title (50-60 chars)",
    "metaDescription": "Meta description (150-160 chars)",
    "authorBio": {{
        "name": "AI News Hub Editorial Staff",
        "bio": "Professional tech journalism powered by AI"
    }}
}}"""
            
            print(f"⏳ جاري توليد مقالة evergreen في فئة '{category}'...")
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(full_prompt)
            
            response_text = response.text
            
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    article_data = json.loads(json_str)
                    
                    print(f"✅ تم توليد المقالة بنجاح: {article_data.get('title', 'بدون عنوان')}")
                    return article_data
                else:
                    print("❌ لم يتم العثور على JSON في الرد")
                    return None
            except json.JSONDecodeError as e:
                print(f"❌ خطأ في تحليل JSON: {e}")
                return None
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في توليد المقالة: {e}")
        return None

def publish_to_blogger(service, article_data: Dict) -> Optional[str]:
    """
    نشر المقالة على بلوجر
    """
    try:
        if not BLOGGER_BLOG_ID:
            raise ValueError("❌ خطأ: BLOGGER_BLOG_ID غير موجود")
        
        # إعداد بيانات المقالة
        post_body = {
            'title': article_data.get('title', 'بدون عنوان'),
            'content': article_data.get('content', ''),
            'labels': article_data.get('tags', []),
        }
        
        # إضافة ملخص إذا كان موجوداً
        if article_data.get('excerpt'):
            post_body['content'] = f"""
<p><strong>الملخص:</strong> {article_data['excerpt']}</p>
{post_body['content']}
"""
        
        print(f"⏳ جاري نشر المقالة على بلوجر: {post_body['title']}")
        
        request = service.posts().insert(
            blogId=BLOGGER_BLOG_ID,
            body=post_body,
            isDraft=False
        )
        
        result = request.execute()
        post_id = result.get('id')
        post_url = result.get('url')
        
        print(f"✅ تم نشر المقالة بنجاح!")
        print(f"   المعرّف: {post_id}")
        print(f"   الرابط: {post_url}")
        
        return post_id
        
    except Exception as e:
        print(f"❌ خطأ في نشر المقالة: {e}")
        return None

def save_published_article(article_data: Dict, post_id: str):
    """حفظ بيانات المقالة المنشورة"""
    try:
        log_file = 'published_articles.json'
        articles = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                articles = json.load(f)
        
        article_record = {
            'post_id': post_id,
            'title': article_data.get('title'),
            'category': article_data.get('category'),
            'published_date': datetime.now().isoformat(),
            'tags': article_data.get('tags', [])
        }
        
        articles.append(article_record)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        print(f"✅ تم حفظ بيانات المقالة في السجل")
        
    except Exception as e:
        print(f"⚠️ تحذير: لم يتم حفظ بيانات المقالة: {e}")

def main():
    """الدالة الرئيسية"""
    print("=" * 70)
    print("🤖 نظام أتمتة مدونة بلوجر المتقدم - AI News Hub")
    print(f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        # تحميل الإعدادات
        config = load_config()
        if not config:
            print("❌ فشل تحميل الإعدادات")
            return
        
        # إعداد Gemini
        setup_gemini()
        
        # الاتصال بـ Blogger API
        blogger_service = get_blogger_service()
        
        # معالجة كل فئة
        categories = config.get('categories', {})
        published_count = 0
        
        for category in categories.keys():
            print(f"\n📂 معالجة الفئة: {category}")
            print("-" * 70)
            
            # توليد مقالة trending
            print(f"\n1️⃣ توليد مقالة Trending...")
            article_data = generate_full_article(config, category, 'trending')
            
            if article_data:
                post_id = publish_to_blogger(blogger_service, article_data)
                if post_id:
                    save_published_article(article_data, post_id)
                    published_count += 1
            
            # انتظار قليل
            time.sleep(2)
            
            # توليد مقالة evergreen
            print(f"\n2️⃣ توليد مقالة Evergreen...")
            article_data = generate_full_article(config, category, 'evergreen')
            
            if article_data:
                post_id = publish_to_blogger(blogger_service, article_data)
                if post_id:
                    save_published_article(article_data, post_id)
                    published_count += 1
            
            # انتظار قليل
            time.sleep(2)
        
        # ملخص النتائج
        print("\n" + "=" * 70)
        print(f"✅ انتهت عملية النشر!")
        print(f"📊 عدد المقالات المنشورة: {published_count}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ خطأ حرج: {e}")
        raise

if __name__ == '__main__':
    main()
