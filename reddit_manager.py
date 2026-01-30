# FILE: reddit_manager.py
# ROLE: Reddit Intelligence Gatherer (No-API / JSON Trick Edition)
# DESCRIPTION: Finds threads via DuckDuckGo and fetches data using Reddit's public JSON endpoints.
#              Bypasses the need for API Keys and Selenium bloat.

import requests
import re
import time
import random
from duckduckgo_search import DDGS
from config import log

class RedditManager:
    def __init__(self):
        # نستخدم User-Agent يبدو كمتصفح حقيقي جداً لتجنب الحظر
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_threads(self, keyword, limit=5):
        """
        يبحث عن روابط Reddit باستخدام DuckDuckGo (لأنه لا يحظر سيرفرات GitHub).
        """
        log(f"      🦆 DuckDuckGo: Hunting Reddit threads for '{keyword}'...")
        threads = []
        
        try:
            # استعلام بحث يركز على النقاشات والتجارب
            query = f'site:reddit.com "{keyword}" (review OR "is it worth" OR "my experience" OR guide)'
            
            with DDGS() as ddgs:
                # DuckDuckGo سريع جداً ولا يطلب Captcha عادةً
                results = list(ddgs.text(query, max_results=8))
                
                for r in results:
                    link = r.get('href')
                    title = r.get('title')
                    
                    # تأكد أنه رابط لمنشور وليس صفحة عامة
                    if "/comments/" in link:
                        threads.append({"title": title, "link": link})
                        if len(threads) >= limit: break
            
            return threads
        except Exception as e:
            log(f"      ❌ Search Error: {e}")
            return []

    def extract_thread_data(self, thread_url):
        """
        السحر هنا: نضيف .json لنهاية الرابط لنحصل على البيانات نظيفة تماماً
        بدون الحاجة لتحليل HTML أو استخدام Selenium.
        """
        try:
            # تنظيف الرابط وإضافة .json
            clean_url = thread_url.split('?')[0].rstrip('/')
            json_url = f"{clean_url}.json"
            
            # تأخير بسيط عشوائي لتجنب الشك
            time.sleep(random.uniform(1, 2))
            
            resp = self.session.get(json_url, timeout=10)
            
            if resp.status_code == 429:
                log("      ⚠️ Reddit Rate Limit (429). Skipping this thread.")
                return None
                
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            # Reddit JSON returns a list: [PostData, CommentsData]
            if not isinstance(data, list) or len(data) < 2: return None

            post_info = data[0]['data']['children'][0]['data']
            comments_info = data[1]['data']['children']

            result = {
                "title": post_info.get('title'),
                "subreddit": post_info.get('subreddit'),
                "url": clean_url,
                "media": [],
                "codes": [],
                "insights": []
            }

            # 1. استخراج الميديا
            self._extract_media(post_info, result["media"])
            
            # 2. استخراج الأكواد من المنشور الرئيسي
            self._extract_codes(post_info.get('selftext', ''), result["codes"])

            # 3. استخراج التعليقات
            for comment in comments_info[:10]:
                c_data = comment.get('data', {})
                body = c_data.get('body')
                
                if not body or body in ["[deleted]", "[removed]"]: continue
                
                # استخراج أكواد من التعليقات
                self._extract_codes(body, result["codes"])

                # حفظ التعليقات المفيدة
                if len(body) > 50 and c_data.get('score', 0) > 2:
                    clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', body) # تنظيف الروابط
                    result["insights"].append({
                        "author": c_data.get('author', 'user'),
                        "text": clean_body.strip(),
                        "score": c_data.get('score', 0)
                    })

            # ترتيب التعليقات حسب الأهمية
            result["insights"].sort(key=lambda x: x['score'], reverse=True)
            result["insights"] = result["insights"][:5]

            return result

        except Exception as e:
            log(f"      ⚠️ Failed to parse thread JSON: {e}")
            return None

    def _extract_media(self, post_data, media_list):
        # صور
        if post_data.get('url', '').endswith(('.jpg', '.png', '.jpeg', '.gif')):
            media_list.append({"type": "image", "url": post_data.get('url'), "caption": post_data.get('title')})
        
        # فيديو
        if post_data.get('is_video') and post_data.get('media'):
            try:
                vid = post_data['media']['reddit_video']['fallback_url']
                media_list.append({"type": "video", "url": vid, "caption": post_data.get('title')})
            except: pass
            
        # معرض صور
        if post_data.get('is_gallery') and post_data.get('media_metadata'):
            for k, v in post_data['media_metadata'].items():
                if v['status'] == 'valid':
                    try:
                        u = v['s']['u'].replace('&amp;', '&')
                        media_list.append({"type": "image", "url": u, "caption": "Gallery"})
                    except: pass

    def _extract_codes(self, text, code_list):
        if not text: return
        matches = re.findall(r'```(?:[a-z]*\n)?(.*?)```', text, re.DOTALL)
        for m in matches:
            c = m.strip()
            if c and c not in code_list: code_list.append(c)

# --- Main Entry Point ---
def get_community_intel(keyword):
    log(f"🧠 [Reddit JSON] Mining discussions for: '{keyword}'...")
    manager = RedditManager()
    
    threads = manager.search_threads(keyword, limit=4)
    if not threads:
        log("   - No threads found via DuckDuckGo.")
        return "", []

    all_data = []
    for t in threads:
        d = manager.extract_thread_data(t['link'])
        if d: all_data.append(d)

    if not all_data: return "", []

    report = "\n\n=== 📢 REAL HUMAN EXPERIENCES (REDDIT) ===\n"
    all_media = []
    
    for post in all_data:
        report += f"--- r/{post['subreddit']}: {post['title']} ---\n"
        report += f"URL: {post['url']}\n"
        if post['insights']:
            report += "TOP COMMENTS:\n"
            for c in post['insights']:
                report += f"- u/{c['author']}: \"{c['text'][:300]}...\"\n"
        if post['codes']:
            report += "CODE SNIPPETS FOUND.\n"
        report += "\n"
        all_media.extend(post['media'])

    unique_media = []
    seen = set()
    for m in all_media:
        if m['url'] not in seen:
            unique_media.append(m)
            seen.add(m['url'])

    log(f"   ✅ Gathered intel from {len(all_data)} threads. Found {len(unique_media)} media items.")
    return report, unique_media
