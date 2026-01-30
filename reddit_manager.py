# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Advanced Reddit Scraper with Stealth Mode & Anti-Bot Evasion.
#              Integrates directly with the AI-Blogger-Automation pipeline.
# =================================/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko=============================================

import requests
import json
import time
import re
import random
import os
from typing import List, Dict, Any, Optional
from config import log

# ------------------------------------------------------------------------------
# STEALTH CONFIGURATION
# ------------------------------------------------------------------------------
# قائمة وكلاء مستخدمين حديثة ومتنوعة لخداع نظام الحماية في Reddit
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
    "Mozilla/5.0 (iPhone; CPU iPhone OS/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/2010010 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

class RedditManager:
    """
    Manages Reddit interactions with stealth capabilities.
    Fetches posts, comments, media, and code snippets while handling rate limits and blocks.
    """
    
    BASE_URL =1 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/60 "https://www.reddit.com"

    def __init__(self):
        self.session = requests4.1"
]

class RedditManager:
    """
    مدير Reddit متطور لجلب البيانات وتصديرها بصيغة JSON.
    يركز على الروابط العميقة، الأدلة الب.Session()
        self._rotate_headers()

    def _rotate_headers(self):
        """
        Updates the session headers with a random User-Agent and browser-like headers.
        Crucial for bypassing 403 Forbidden errors.
        """
        ua = random.choice(USER_AGENTS)
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,applicationصرية، والأكواد.
    مزود بنظام إعادة المحاولة وتدوير الهوية لتجنب الحظر (403/429).
    """
    
    BASE_URL = "https://www.reddit.com"

    def __init__(self):
        self.session = requests.Session()
        /xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-self._rotate_identity()

    def _rotate_identity(self):
        """تغيير هوية المتصفح (User-Agent) لتجنب الكشف."""
        agent = random.choice(USER_AGENTS)
        self.session.headers.update({
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        })

    def _get_json(self, url: str) -> Optional[Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control":Dict[str, Any]]:
        """دالة الاتصال الأساسية مع معالجة الأخطاء وإعادة المحاولة.""" "max-age=0",
        })

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetches JSON data from a URL with robust error handling and retry logic.
        """
        try:
            # Ensure the URL ends with .json and preserve query parameters
            if ".json" not in url:
                if "?" in url:
                    base, params = url.split("?", 1)
                    url = f"{base.rstrip('/')}.json?{params}"
                else:
                    url = f"{url.rstrip('/')}.json"
            
            # Attempt 1
            response = self.session.get(url, timeout=20)
            
            # Handle Rate Limiting (429) or Forbidden (403)
            if response.status_code in [429, 403]:
                log(f"      ⚠️ Reddit returned {response.status_code}. Rotating
        try:
            # التأكد من وجود الامتداد .json
            if ".json" not in url:
                if "?" in url:
                    base, params = url.split("?", 1)
                    url = f"{base.rstrip('/')}.json?{params}"
                else:
                    url = f"{url.rstrip('/')}.json"
            
            # المحاولة الأولى
            response = self.session.get(url, timeout=15)
            
            # معالجة الحظر (403) أو كثرة الطلبات (429)
            if response.status_code in [403,  headers and retrying...")
                time.sleep(random.uniform(2, 4)) # Random delay
                self._rotate_headers() # Switch identity
                response = self.session.get(url, timeout=20) # Retry429]:
                log(f"   ⚠️ Reddit blocked ({response.status_code}). Rotating identity and retrying...")
                time.sleep(3)
                self._rotate_identity()
                response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                log(f"   ⚠️ Reddit Error {response.status_code} for URL: {url}")
                return None
            
            return response.json()
        except Exception as e:
            log(
            
            if response.status_code != 200:
                log(f"      ⚠️ Failed to fetch {url}. Status: {response.status_code}")
                return None
            
            return response.json()
        except Exception as e:
            log(f"      ⚠️ Reddit Request Exception: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) ->f"   ❌ Reddit Network Error: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        """استخراج روابط الصور والوسائط من بيانات المنشور."""
        media = []
        url = data.get("url", "")
        
        # تصفية الام List[str]:
        """
        Extracts image URLs from post data using direct links, selftext regex, and metadata.
        """
        media = []
        url = data.get("url", "")
        
        #تدادات المعروفة للصور
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "imgur.com", "gallery"]):
            media.append(url 1. Direct URL check (excluding video pages that require complex parsing)
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "imgur.com", "gallery"]):
            media.append(url)
        
        # 2. Regex extraction from text body
        text = data.get("selftext", "") or data.get("body", "")
        if text:
            )
        
        text = data.get("selftext", "") or data.get("body", "")
        # البحث عن روابط صور داخل النص
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif))', text, re.IGNORECASE)
        media.extend(urls)
        
        # استخراج الصور من الميتاداتا الخاصة بـ Reddit Gallery
        if "media_metadata" in data:
            for item in data["media_metadata"].values():
                if "urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif))', text, re.IGNORECASE)
            media.extend(urls)
        
        # 3. Media Metadata (Reddit's internal gallery format)
        if "media_metadata" in data:
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    # Decode HTML entities (e.g., &amp; -> &)
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(s" in item and "u" in item["s"]:
                    # إصلاح ترميز الرابط (&amp;)
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        """استخراج الأكواد البرمجية من النص."""
        if not text: return []
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def get_all_data(self, query: str, subreddit: Optional[str] = None, limit: int =media)) # Return unique URLs

    def _extract_codes(self, text: str) -> List[str]:
        """
        Extracts code blocks and inline code from markdown text.
        """
        if not text: return []
        # Extract triple backtick blocks
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        # Extract inline backticks
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        
        # Clean and combine
        cleaned_codes = [c.strip() for c in codes + inline_codes if c.strip()]
        return list(set(cleaned_codes))

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
        """
        Fetches detailed data for a single post, including comments.
        """
        data = self._get_json(post_url)
        if not data or not 3) -> Dict[str, Any]:
        """
        جلب كافة البيانات الخام والمنظمة بصيغة قاموس.
        يدعم البحث العام أو داخل Subreddit معين.
        """
        # استخدام t=month لضمان حداثة المحتوى
        if subreddit:
            search_url = f"{self. isinstance(data, list) or len(data) < 2:
            return {"post": {}, "comments": []}

        try:
            # Parse Post Data (Index 0)
            p_data = data[0]["data"]["children"][0]["data"]
            post_details = {
                "title": p_data.get("title"),
                "text": p_data.get("selftext"),
                "author": p_data.get("author"),
                "url": f"{self.BASE_URL}{p_BASE_URL}/r/{subreddit}/search.json?q={query}&limit={limit}&restrict_sr=1&sort=relevance&t=month"
        else:
            search_url = f"{self.BASE_URL}/search.json?q={query}&limit={limit}&sort=relevance&t=month"
            
        search_data = self._get_json(search_url)
        results = {
            "query": query,
            "timestamp": time.time(),
            "posts": []
        }

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                try:
                    data.get('permalink')}",
                "media": self._extract_media(p_data),
                "codes": self._extract_codes(p_data.get("selftext", "")),
                "score": p_data.get("score", 0),
                "subreddit": p_data.get("subreddit_name_prefixed")
            }
            
            # Parse Comments (Index 1) - Taking top 3 root comments
            comments = []
            if len(data) > 1 and "data" in data[1permalink = post_item['data'].get('permalink')
                    if not permalink: continue
                    
                    post_url = f"{self.BASE_URL}{permalink}"
                    details = self.get_post_details(post_url)
                    
                    # التحقق من أن المنشور يحتوي على بيانات صالحة
                    if details and details.get("post"):
                        results["posts"].append(details)
                except Exception as e:
                    log(f"   ⚠️ Error processing post item: {e}")
                    continue
        
        return results

    def get_post_details(self, post_url: str) -> Dict[str, Any]:] and "children" in data[1]["data"]:
                children = data[1]["data"]["children"]
                for child in children[:3]: # Limit to top 3 for efficiency
                    if child["kind"] == "t1":
                        comments.append(self._parse_single_comment(child["data"]))

            return {"post": post_details, "comments": comments}
        except Exception as e:
            log(f"      ⚠️ Error parsing post details: {e}")
            return {"post": {}, "comments": []}

    def _parse_single_comment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper to parse a single comment object.
        """
        body = data.get("body", "")
        return {
            "author": data.get("author"),
            "body": body,
            "
        """جلب تفاصيل منشور معين مع التعليقات."""
        data = self._get_json(post_url)
        if not data or not isinstance(data, list) or len(data) < 2:
            return {"post": {}, "comments": []}

        try:
            p_data = data[0]["data"]["children"][0]["data"]
            post_details = {
                "title": p_data.get("title"),
                "text": p_data.get("selftext"),
                "author": p_data.get("author"),
                "url": f"{self.BASE_URL}{p_data.get('permalink')}",
                "media": self._extract_media(p_data),
                "codes": self._extract_codes(p_data.get("selftext", "")),
                "score": p_data.get("score", 0),
                "subreddit": p_data.get("score": data.get("score"),
            "media": self._extract_media(data),
            "codes": self._extract_codes(body)
        }

    def get_all_data(self, query: str, limit: int = 3) -> Dict[str, Any]:
        """
        Mainsubreddit_name_prefixed")
            }
            
            # تحليل التعليقات من الجزء الثاني من الاستجابة
            comments = self._parse_comments(data[1]["data"]["children"], post_details["url"])
            return {"post": post_details, "comments": comments}
        except Exception as e:
            log(f"   ⚠️ Error extracting post details: {e}")
            return {"post": {}, "comments": []}

    def _parse_comments(self, children: List[Dict[str, Any]], post_ entry point: Searches for a query and retrieves full details for top results.
        """
        # Encode query and set sort to relevance with monthly timeframe for recency
        encoded_query = requests.utils.quote(query)
        search_url = f"{self.BASE_URL}/search.json?q={encoded_query}&limit={limit}&sort=relevance&t=month"
            
        search_data = self._get_url: str) -> List[Dict[str, Any]]:
        """تحليل شجرة التعليقات (بشكل متكرر إذا لزم الأمر)."""
        parsed = []
        for child in children:
            if child["kind"] == "t1":
                d = child["data"]
                body = d.get("body", "")
                comment_id = d.get("id")
                comment_link = f"{post_url.rstrip('/')}/{comment_id}/"
                
                parsed.append({
                    "comment_id": comment_id,
                    "author": d.get("author"),
                    "body": bodyjson(search_url)
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
                        details = self.get_post_details(post,
                    "url": comment_link,
                    "score": d.get("score"),
                    "media": self._extract_media(d),
                    "codes": self._extract_codes(body),
                    # يمكن تفعيل هذا السطر إذا أردت الردود المتداخلة (Nested Comments)
                    # "replies": self._parse_comments(d["replies"]["data"]["children"], post_url) if d.get("replies") and isinstance(d["replies"], dict) else []
                })
        # إرجاع أفضل 3 تعليقات فقط لتقليل حجم البيانات
        return sorted(parsed, key=lambda x_url)
                        if details["post"]:
                            results["posts"].append(details)
                except Exception as e:
                    continue
        
        return results

    def generate_writer_brief(self, data: Dict[str, Any]) -> str:
        """
        Converts the structured JSON data into a readable Markdown brief for the AI Writer.
        """
        if not data["posts"]: return ""

        brief = f"--- 🧠 REAL REDDIT COMMUNITY INTEL FOR: '{data['query']}' ---\n\n"
        
        for i, item in enumerate(data["posts"], 1):
            post = item["post"]
            brief += f"## 🧵 THREAD {i}: {post.get('title', 'No Title')}\n"
            brief += f"**Subreddit:** {post.get('subreddit')}\n"
            brief += f"**Source:** {post.get('url')}\n"
            brief += f"**Score:** {post.get('score')} Upvotes\n"
            
            # Add Post Content (Truncated if too long)
: x.get("score", 0), reverse=True)[:3]

    def generate_writer_brief(self, data: Dict[str, Any]) -> str:
        """توليد ملخص نصي (Context) ليستخدمه الكاتب الآلي."""
        if not data or not data.get("posts"): return ""

        brief = f"\n--- REDDIT COMMUNITY INSIGHTS (Query: {data['query']}) --            content = str(post.get('text', ''))
            if len(content) > 1000:
                content = content[:1000] + "... [Read More in Source]"
            brief += f"**Content:**\n{content}\n"
            
            # Add Code Snippets if any
            if post.get('codes'):
                brief += "**💻 Code Snippets Found:**\n"
                for code in post['codes'][:2]: # Limit to 2 snippets
                    brief += f"```\n{code[:300]}\n```\n"

            # Add Top Comments
            if item["comments"]:
                brief +=-\n"
        for i, item in enumerate(data["posts"], 1):
            post = item["post"]
            brief += f"\n📌 DISCUSSION {i}: {post.get('title', 'No Title')}\n"
            brief += f"   - Subreddit: {post.get('subreddit')}\n"
            brief += f"   - Upvotes: {post.get('score')}\n"
            brief += f"   - Link: {post.get('url')}\n"
            
            # تنظيف النص واختصاره
            text_preview = str(post.get('text', '')).replace('\n', ' ').strip()
            if len(text_preview) > 600:
                text_preview = text_preview "\n**💬 Top Community Reactions:**\n"
                for c in item["comments"]:
                    brief += f"- **u/{c.get('author')}** ({c.get('score')} pts): \"{c.get('body', '')[:600] + "..."
            if text_preview:
                brief += f"   - Post Content: {text_preview}\n"
            
            if item["comments"]:
                brief += "   - 💬 Top User Opinions:\n"
                for c in item["comments"]:
                    brief += f"     * u/{c['author']} ({c['score']} pts): \"{c['body'][:200]}...\"\n"
            
            if item["post"].get("codes"):
                brief += "   - 💻 Code Snippets Found: Yes\n"
            
            brief += "-"*30 + "\n"
        return brief

# =================================[:300]}...\"\n"
            
            brief += "\n" + ("=" * 40) + "\n\n"
            
        return brief

# ==============================================================================
# ADAPTER FUNCTION (REQUIRED FOR main.py INTEGRATION)
# ==============================================================================

def get_community_=============================================
# ADAPTER FUNCTION (REQUIRED FOR MAIN.PY INTEGRATION)
# =================================================================intel(keyword: str):
    """
    Bridge function to integrate RedditManager with the main pipeline.
    
    Args:
        keyword (str): The search topic.
        
    Returns:
        tuple: (=============

def get_community_intel(keyword):
    """
    الدالة الوسيطة التي يستدعيها ملف main.py.
    تقوم بتهيئة الكلاس، جلب البيانات، وتنسيقها بالشكل المطلوب.
    
    Returns:
        tuple: (text_context_string, media_assets_list)
    """
    log(f"🧠 [Reddit Manager] Mining deep intelligence for: '{keyword}'...")
    
    try:
        # تهيئة المدير (سيقوم باختيار User-Agent عشوائي تلقائياً)
        manager = RedditManager()
        
        # 1. جلب البيانات (أفضل 3 منشورات خلال الشهر)
        data = manager.get_all_data(keyword, limit=3)
        
        # 2. تحويل البيانات إلى نص سياقي للكاتب
        text_context = manager.generate_writer_brief(data)
        
        # 3. استخراج وتنسيق الوسائط للقالب
text_context, media_list)
            - text_context (str): Formatted string of discussions for the AI.
            - media_list (list): List of dictionaries containing image data.
    """
    log(f"🧠 [Reddit Manager] Mining deep intelligence for: '{keyword}'...")
    
    try:
        # Initialize Manager
        manager = RedditManager()
        
        # 1. Fetch Deep Data
        data = manager.get_all_data(keyword, limit=3)
        
        # 2. Generate Text Context for AI Writer
        text_context = manager.generate_writer_brief(data)
        
        # 3. Extract and Format Media Assets for Visual Pipeline
        media_assets = []
        for item in data["posts"]:
            # Process Post Media
            for img_url in item["post"].get("media", []):
                media_assets.append({
                    "type": "image",
                    "url": img_url,
                    "description": f"Reddit Source: {item['post']['title']} (u/{item['post']['author']})",
                    "score": item['        media_assets = []
        if data and "posts" in data:
            for item in data["post'].get("score", 0)
                })
            
            # Process Comment Media (Often valuable in tech threads)
            for comment in item["comments"]:
                for img_url in comment.get("media", []):posts"]:
                post_title = item["post"].get("title", "Reddit Image")
                post_score = item["post"].get("score", 0)
                
                # وسائط المنشور نفسه
                for img_url in item["post"].get("media", []):
                    media_assets.append({
                        "type": "image",
                        "url": img_url,
                        "description": f"Reddit Source: {post_title}",
                        "score": post_score
                    })
                
                # وسائط التعليقات (إن وجدت)
                for comment in item["comments"]:
                    for img_url in comment.get("media", []):
                        media_assets.append({
                            "type": "image",
                            "url": img_url,
                            "description": f"Reddit Comment by u/{comment['author']}",
                            "score":
                    media_assets.append({
                        "type": "image",
                        "url": img_url,
                        "description": f"Reddit Comment by u/{comment['author']} on {item['post']['title']}",
                        "score": comment.get("score", 0)
                    })
        
        log(f"   ✅ Reddit Intel: Found {len(data['posts'])} threads and {len(media_assets)} visual assets.")
        return text_context, media_assets

    except Exception as e:
        log(f"   ⚠️ Reddit Adapter Error: {e}")
        return "", []

# ==============================================================================
# SELF-TEST BLOCK
# ==============================================================================
if __name__ == "__main__":
    print("--- TESTING comment.get("score", 0)
                        })

        log(f"   ✅ Reddit Intel: Found {len(data.get('posts', []))} threads and {len(media_assets)} media assets.")
        return text_context, media_assets

    except Exception as e:
        log(f"   ⚠️ Reddit Manager Adapter Failed: {e}")
        # في حالة الفشل، نعيد قيماً فارغة حتى لا يت REDDIT MANAGER ---")
    k = "AutoGen vs CrewAI"
    context, media = get_community_intel(k)
    
    print(f"\n[RESULT] Context Length: {len(context)} characters")
    print(f"[RESULT] Media Found: {len(media)} items")
    
    if len(context) > 0:
        print("\n--- PREVIEW CONTEXT ---")
        print(context[:500])
    
    if len(media) > 0:
        print("\n---وقف البرنامج
        return "", []

# ==============================================================================
# TEST BLOCK (FOR DIRECT EXECUTION)
# ==============================================================================
if __name__ == "__main__":
    print("--- TESTING REDDIT MANAGER ---")
    test_query = "OpenAI Sora"
    
    # اختبار الدالة الوسيطة مباشرة
    context, media = get_community_intel(test_query)
    
    print("\n--- GENER PREVIEW MEDIA ---")
        print(media[0])
