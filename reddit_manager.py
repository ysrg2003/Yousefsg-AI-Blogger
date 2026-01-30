# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Advanced Reddit Scraper & Intelligence Manager.
#              Integrates Stealth Mode (Anti-403) and Deep Content Extraction.
#              Fully compatible with AI-Blogger-Automation Pipeline.
# ==============================================================================

import requests
import json
import time
import re
import random
import urllib.parse
from typing import List, Dict, Any, Optional

# استيراد وظيفة التسجيل من المشروع لضمان توحيد السجلات
try:
    from config import log
except ImportError:
    # دالة بديلة في حالة تشغيل الملف بشكل منفصل للاختبار
    def log(msg): print(f"[LOG] {msg}")

# ------------------------------------------------------------------------------
# STEALTH CONFIGURATION
# ------------------------------------------------------------------------------
# قائمة متنوعة من وكلاء المستخدم لخداع أنظمة الحماية في Reddit
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

class RedditManager:
    """
    مدير Reddit متطور لجلب البيانات وتصديرها.
    يستخدم تدوير الوكلاء (User-Agent Rotation) ومعالجة الأخطاء الذكية.
    """
    
    BASE_URL = "https://www.reddit.com"

    def __init__(self):
        self.session = requests.Session()
        self._rotate_identity()

    def _rotate_identity(self):
        """تحديث ترويسات الجلسة لتبدو كمتصفح جديد."""
        agent = random.choice(USER_AGENTS)
        self.session.headers.update({
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """جلب البيانات بصيغة JSON مع إعادة المحاولة في حالة الحظر."""
        try:
            # التأكد من أن الرابط ينتهي بـ .json
            if ".json" not in url:
                if "?" in url:
                    base, params = url.split("?", 1)
                    url = f"{base.rstrip('/')}.json?{params}"
                else:
                    url = f"{url.rstrip('/')}.json"
            
            # محاولة الطلب (Retry Logic)
            attempts = 0
            max_attempts = 3
            
            while attempts < max_attempts:
                try:
                    response = self.session.get(url, timeout=15)
                    
                    # إذا نجح الطلب
                    if response.status_code == 200:
                        return response.json()
                    
                    # إذا تم الحظر (403/429)
                    elif response.status_code in [403, 429]:
                        log(f"   ⚠️ Reddit blocked request ({response.status_code}). Rotating identity and retrying...")
                        self._rotate_identity()
                        time.sleep(3 + attempts) # انتظار تصاعدي
                        attempts += 1
                        continue
                    
                    # أخطاء أخرى
                    else:
                        log(f"   ⚠️ Reddit Error {response.status_code} for {url}")
                        return None

                except requests.exceptions.RequestException as re_err:
                    log(f"   ⚠️ Connection Error: {re_err}")
                    attempts += 1
                    time.sleep(2)
            
            return None

        except Exception as e:
            log(f"   ⚠️ Reddit General Exception: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        """استخراج روابط الصور والوسائط من بيانات المنشور."""
        media = []
        url = data.get("url", "")
        
        # التحقق من الرابط الرئيسي
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "imgur.com", "gallery"]):
            media.append(url)
        
        # البحث داخل النص
        text = data.get("selftext", "") or data.get("body", "")
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif))', text, re.IGNORECASE)
        media.extend(urls)
        
        # البحث في بيانات الميتا (Gallery Metadata)
        if "media_metadata" in data and isinstance(data["media_metadata"], dict):
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    # فك ترميز الرابط (&amp; -> &)
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        """استخراج الأكواد البرمجية من النص."""
        if not text: return []
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
        """جلب تفاصيل منشور معين والتعليقات."""
        data = self._get_json(post_url)
        
        # التحقق من صحة هيكل البيانات
        if not data or not isinstance(data, list) or len(data) < 2:
            return {"post": {}, "comments": []}

        try:
            # تحليل المنشور الرئيسي
            p_data = data[0]["data"]["children"][0]["data"]
            post_details = {
                "title": p_data.get("title"),
                "text": p_data.get("selftext"),
                "author": p_data.get("author"),
                "url": f"{self.BASE_URL}{p_data.get('permalink')}",
                "media": self._extract_media(p_data),
                "score": p_data.get("score", 0),
                "codes": self._extract_codes(p_data.get("selftext", ""))
            }
            
            # تحليل التعليقات (أفضل 3 تعليقات)
            comments = []
            if len(data) > 1 and "data" in data[1] and "children" in data[1]["data"]:
                children = data[1]["data"]["children"]
                for child in children:
                    if len(comments) >= 3: break # اكتفي بأفضل 3 تعليقات
                    if child["kind"] == "t1":
                        d = child["data"]
                        # تجاهل التعليقات المحذوفة أو تعليقات البوتات
                        if d.get("body") in ["[deleted]", "[removed]"] or "bot" in str(d.get("author")).lower():
                            continue
                            
                        comments.append({
                            "author": d.get("author"),
                            "body": d.get("body", ""),
                            "score": d.get("score", 0),
                            "media": self._extract_media(d),
                            "codes": self._extract_codes(d.get("body", ""))
                        })

            return {"post": post_details, "comments": comments}
        except Exception as e:
            log(f"   ⚠️ Error parsing details for {post_url}: {e}")
            return {"post": {}, "comments": []}

    def get_all_data(self, query: str, limit: int = 3) -> Dict[str, Any]:
        """البحث وجلب البيانات الكاملة لعدة منشورات."""
        # استخدام البحث المتقدم: الفرز حسب الصلة والوقت (شهر)
        encoded_query = urllib.parse.quote(query)
        search_url = f"{self.BASE_URL}/search.json?q={encoded_query}&limit={limit}&sort=relevance&t=month"
            
        search_data = self._get_json(search_url)
        results = {
            "query": query,
            "posts": []
        }

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                try:
                    permalink = post_item['data'].get('permalink')
                    if permalink:
                        post_url = f"{self.BASE_URL}{permalink}"
                        details = self.get_post_details(post_url)
                        if details["post"]: # إضافة المنشور فقط إذا تم جلبه بنجاح
                            results["posts"].append(details)
                except Exception as e:
                    continue
        
        return results

    def generate_writer_brief(self, data: Dict[str, Any]) -> str:
        """تحويل البيانات الخام إلى نص منسق (Context) ليفهمه كاتب الذكاء الاصطناعي."""
        if not data["posts"]: return ""

        brief = f"--- REAL USER DISCUSSIONS & INSIGHTS (REDDIT) ---\n"
        brief += f"Query Focus: {data['query']}\n\n"
        
        for i, item in enumerate(data["posts"], 1):
            post = item["post"]
            brief += f"THREAD #{i}: {post['title']}\n"
            brief += f"Source URL: {post['url']}\n"
            brief += f"Upvotes: {post['score']}\n"
            
            # تنظيف النص وعرض مقتطف منه
            content = str(post['text']).replace('\n', ' ').strip()
            if len(content) > 600: content = content[:600] + "..."
            brief += f"Content Summary: {content}\n"
            
            if item["comments"]:
                brief += "TOP COMMUNITY COMMENTS:\n"
                for c in item["comments"]:
                    c_body = str(c['body']).replace('\n', ' ').strip()
                    if len(c_body) > 300: c_body = c_body[:300] + "..."
                    brief += f"   - u/{c['author']} ({c['score']} pts): {c_body}\n"
            
            brief += "-"*30 + "\n"
            
        return brief


# ==============================================================================
# ADAPTER FUNCTION (THE BRIDGE TO MAIN.PY)
# ==============================================================================

def get_community_intel(keyword: str):
    """
    الدالة الرئيسية التي يستدعيها ملف main.py.
    
    المدخلات:
        keyword (str): الكلمة المفتاحية للبحث.
        
    المخرجات:
        tuple: (text_context, media_list)
        - text_context (str): نص ملخص للمناقشات ليستخدمه الكاتب.
        - media_list (list): قائمة بالقواميس تحتوي على الصور.
    """
    log(f"🧠 [Reddit Manager] Mining deep intelligence for: '{keyword}'...")
    
    try:
        # 1. تهيئة المدير وتشغيل البحث
        manager = RedditManager()
        raw_data = manager.get_all_data(keyword, limit=3)
        
        # 2. التحقق من وجود نتائج
        if not raw_data["posts"]:
            log("   ⚠️ No Reddit discussions found for this topic.")
            return "", []

        # 3. توليد سياق النص (Text Context)
        text_context = manager.generate_writer_brief(raw_data)
        
        # 4. استخراج وتنسيق الوسائط (Media Formatting)
        # نحول الصور إلى الشكل الذي يتوقعه main.py
        media_assets = []
        for item in raw_data["posts"]:
            # صور المنشور
            for img_url in item["post"].get("media", []):
                media_assets.append({
                    "type": "image",
                    "url": img_url,
                    "description": f"Community Image: {item['post']['title']}",
                    "score": item['post'].get("score", 0),
                    "source": "Reddit"
                })
            # صور التعليقات (إن وجدت)
            for comment in item["comments"]:
                for img_url in comment.get("media", []):
                    media_assets.append({
                        "type": "image",
                        "url": img_url,
                        "description": f"Comment Image by u/{comment['author']}",
                        "score": comment.get("score", 0),
                        "source": "Reddit"
                    })

        log(f"   ✅ Reddit Intel: Found {len(raw_data['posts'])} threads and {len(media_assets)} media assets.")
        return text_context, media_assets

    except Exception as e:
        log(f"   ⚠️ Reddit Manager Critical Error: {e}")
        # إرجاع قيم فارغة آمنة لمنع توقف البرنامج
        return "", []

# ------------------------------------------------------------------------------
# TESTING BLOCK (Run this file directly to verify)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("--- STARTING REDDIT MANAGER TEST ---")
    test_keyword = "AutoGPT Agents"
    
    context, media = get_community_intel(test_keyword)
    
    print("\n\n=== GENERATED CONTEXT ===")
    print(context[:1000]) # طباعة أول 1000 حرف
    
    print("\n=== EXTRACTED MEDIA ===")
    for m in media:
        print(m)
    
    print("\n--- TEST COMPLETE ---")
