
import requests
import json
import time
import re
import os
from typing import List, Dict, Any, Optional

# ==============================================================================
# SECTION 1: THE ADVANCED CORE CLASS (YOUR EXACT CODE, UNTOUCHED)
# هذا هو الكود الذي قدمته، منسوخ حرفياً 1:1 بدون أي تغيير أو حذف.
# ==============================================================================

class RedditManager:
    """
    مدير Reddit متطور لجلب البيانات وتصديرها بصيغة JSON أو Markdown.
    يركز على الروابط العميقة، الأدلة البصرية، والأكواد.
    """
    
    BASE_URL = "https://www.reddit.com"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            if ".json" not in url:
                if "?" in url:
                    base, params = url.split("?", 1)
                    url = f"{base.rstrip('/')}.json?{params}"
                else:
                    url = f"{url.rstrip('/')}.json"
            
            response = self.session.get(url, timeout=15)
            if response.status_code == 429:
                time.sleep(2)
                response = self.session.get(url, timeout=15)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        media = []
        url = data.get("url", "")
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "v.redd.it", "imgur.com", "gallery"]):
            media.append(url)
        
        text = data.get("selftext", "") or data.get("body", "")
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif|mp4))', text, re.IGNORECASE)
        media.extend(urls)
        
        if "media_metadata" in data:
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        if not text: return []
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def get_all_data(self, query: str, subreddit: Optional[str] = None, limit: int = 3) -> Dict[str, Any]:
        """جلب كافة البيانات الخام والمنظمة بصيغة قاموس (Dictionary) جاهز للتحويل لـ JSON."""
        if subreddit:
            search_url = f"{self.BASE_URL}/r/{subreddit}/search.json?q={query}&limit={limit}&restrict_sr=1&sort=relevance"
        else:
            search_url = f"{self.BASE_URL}/search.json?q={query}&limit={limit}&sort=relevance"
            
        search_data = self._get_json(search_url)
        results = {
            "query": query,
            "timestamp": time.time(),
            "posts": []
        }

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                post_url = f"{self.BASE_URL}{post_item['data'].get('permalink')}"
                details = self.get_post_details(post_url)
                results["posts"].append(details)
        
        return results

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
        data = self._get_json(post_url)
        if not data or not isinstance(data, list) or len(data) < 2:
            return {"post": {}, "comments": []}

        p_data = data[0]["data"]["children"][0]["data"]
        post_details = {
            "title": p_data.get("title"),
            "text": p_data.get("selftext"),
            "author": p_data.get("author"),
            "url": f"{self.BASE_URL}{p_data.get('permalink')}",
            "media": self._extract_media(p_data),
            "codes": self._extract_codes(p_data.get("selftext", ""))
        }
        
        comments = self._parse_comments(data[1]["data"]["children"], post_details["url"])
        return {"post": post_details, "comments": comments}

    def _parse_comments(self, children: List[Dict[str, Any]], post_url: str) -> List[Dict[str, Any]]:
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
                    "body": body,
                    "url": comment_link,
                    "score": d.get("score"),
                    "media": self._extract_media(d),
                    "codes": self._extract_codes(body),
                    "replies": self._parse_comments(d["replies"]["data"]["children"], post_url) if d.get("replies") and isinstance(d["replies"], dict) else []
                })
        return parsed

    def generate_writer_brief(self, query: str, subreddit: Optional[str] = None) -> str:
        """توليد ملخص Markdown (للقراءة البشرية)."""
        data = self.get_all_data(query, subreddit)
        if not data["posts"]: return "لم يتم العثور على نتائج."

        brief = f"# تقرير الأدلة البشرية من Reddit: {query}\n\n"
        for i, item in enumerate(data["posts"], 1):
            post = item["post"]
            brief += f"## {i}. المنشور: {post['title']}\n"
            brief += f"- **الرابط:** {post['url']}\n"
            if post['media']:
                brief += "\n**🖼️ وسائط المنشور:**\n"
                for m in post['media']: brief += f"- [رابط]({m})\n"
            
            brief += "\n### 💬 أبرز التعليقات:\n"
            top_comments = sorted(item["comments"], key=lambda x: x["score"], reverse=True)[:3]
            for c in top_comments:
                brief += f"#### u/{c['author']} ({c['score']})\n"
                brief += f"- **رابط التعليق:** {c['url']}\n"
                brief += f"> {c['body'][:300]}...\n"
                if c['media']:
                    for cm in c['media']: brief += f"- [وسائط بالتعليق]({cm})\n"
                if c['codes']:
                    for cc in c['codes']: brief += f"```\n{cc}\n```\n"
            brief += "\n---\n"
        return brief

# ==============================================================================
# SECTION 2: SYSTEM COMPATIBILITY ADAPTER (CODE TO INTEGRATE WITH MAIN.PY)
# هذا الجزء هو "مترجم" يستخدم الكلاس أعلاه ليتحدث مع باقي أجزاء النظام.
# هذا هو الجزء الذي يضمن أن الكود القوي الخاص بك يعمل داخل المشروع.
# ==============================================================================

def get_community_intel(keyword):
    """
    هذه الدالة هي حلقة الوصل التي يستدعيها main.py.
    تقوم بإنشاء نسخة من الكلاس القوي الخاص بك (RedditManager)، وتستخدمه لجلب البيانات العميقة،
    ثم تعيد صياغة هذه البيانات الغنية بالشكل الذي يتوقعه النظام (تقرير نصي + قائمة وسائط).
    """
    # 1. إنشاء نسخة من الكلاس الخاص بك واستخدامه
    manager = RedditManager()
    print(f"   🧠 [Reddit Manager] Mining deep intelligence for: '{keyword}'...")
    
    try:
        # 2. استدعاء دالة `get_all_data` من الكلاس الخاص بك لجلب البيانات المفصلة
        data = manager.get_all_data(keyword, limit=3)
        
        if not data["posts"]:
            return "", []

        # 3. تحويل قائمة الوسائط المفصلة إلى الصيغة البسيطة التي يحتاجها main.py
        # main.py يتوقع قائمة من القواميس تحتوي على type, url, description, score
        system_media_list = []
        for post_data in data["posts"]:
            post = post_data["post"]
            # وسائط المنشور الأصلي
            for m_url in post.get("media", []):
                m_type = "video" if any(x in m_url for x in ["mp4", "v.redd.it"]) else "image"
                system_media_list.append({
                    "type": m_type, "url": m_url,
                    "description": f"Reddit Demo: {post.get('title', '')[:50]}", "score": 8
                })
            # وسائط من داخل التعليقات (الميزة الأهم في الكود الجديد)
            for comment in post_data.get("comments", [])[:5]:
                for cm_url in comment.get("media", []):
                    system_media_list.append({
                        "type": "image", "url": cm_url,
                        "description": f"User Evidence in Comments: {comment.get('body', '')[:40]}", "score": 7
                    })

        unique_media = list({v['url']:v for v in system_media_list}.values())

        # 4. تحويل البيانات النصية المفصلة إلى تقرير نصي للذكاء الاصطناعي الكاتب
        # هنا نضمن تضمين الروابط العميقة للتعليقات والأكواد
        report = "\n=== 📢 REAL COMMUNITY FEEDBACK (DEEP DIVE) ===\n"
        report += "INSTRUCTIONS: Use these real user quotes and code snippets to validate the news.\n"
        report += "CRITICAL: Link directly to the specific comments provided below.\n\n"
        
        for i, item in enumerate(data["posts"], 1):
            post = item["post"]
            report += f"--- THREAD {i}: {post['title']} ---\nPOST LINK: {post['url']}\n"
            
            if post.get('codes'):
                report += "   💻 CODE SNIPPET FOUND:\n"
                for code in post['codes'][:1]: report += f"   ```\n{code[:200]}...\n   ```\n"

            top_comments = sorted(item["comments"], key=lambda x: x.get("score", 0), reverse=True)[:3]
            for c in top_comments:
                if len(c['body']) > 10:
                    report += f"   💬 USER ({c['author']}) SAID:\n"
                    report += f"      \"{c['body'][:400]}...\"\n"
                    report += f"      🔗 DIRECT COMMENT LINK: {c['url']}\n" # الرابط العميق
                    if c.get('codes'): report += f"      💻 USER CODE: `{c['codes'][0][:100]}...`\n"
            report += "\n"

        # 5. إرجاع المخرجات النهائية بالصيغة التي يفهمها main.py
        return report, unique_media

    except Exception as e:
        print(f"   ❌ Reddit Manager Error: {e}")
        return "", []

if __name__ == "__main__":
    # هذا الجزء (الذي طلبته) يعمل عند تشغيل الملف مباشرة للاختبار
    manager = RedditManager()
    query = "chatgpt 5.2"
    print(f"--- Running Standalone Test for: {query} ---")
    results = manager.get_all_data(query)
    
    # حفظ النتائج في ملف JSON كما في test_reddit.py
    with open("reddit_data_direct_test.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print("✅ Standalone test complete. Data saved to reddit_data_direct_test.json")
