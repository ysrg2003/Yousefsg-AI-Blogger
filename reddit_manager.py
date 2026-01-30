# FILE: reddit_manager.py
# ROLE: Advanced Reddit Intelligence & Visual Evidence Gatherer.
# DESCRIPTION: Mines Reddit for genuine user opinions, discussions, visual proofs (images/videos), and code snippets
#              to inject authentic human experience (E-E-A-T) into the articles.

import requests
import urllib.parse
import feedparser
import time
import re
from bs4 import BeautifulSoup
from config import log  # استخدام دالة اللوجر الموحدة من المشروع

class RedditManager:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_reddit_threads(self, keyword, limit=4):
        """
        Searches for real discussions on Reddit using DuckDuckGo HTML as a primary gateway,
        with Google News RSS as a fallback.
        """
        threads = []
        # تحسين كلمات البحث لتشمل مشاكل وحلول
        search_query = f"site:reddit.com {keyword} (review OR experience OR opinion OR problem OR bug OR solution)"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
        
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.select('a.result__a')
                for a in links:
                    link = a.get('href', '')
                    if "reddit.com/r/" in link:
                        if "uddg=" in link:
                            link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                        # التأكد من عدم وجود روابط مكررة
                        if not any(t['link'] == link for t in threads):
                            threads.append({"title": a.text.strip() or "Reddit Post", "link": link})
                    if len(threads) >= limit: break
        except Exception as e:
            log(f"      ⚠️ DuckDuckGo search failed: {e}. Trying fallback.")
        
        # Fallback to Google RSS if DuckDuckGo fails or returns no results
        if not threads:
            try:
                rss_url = f"https://news.google.com/rss/search?q=site%3Areddit.com+{urllib.parse.quote(keyword)}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:limit]:
                    threads.append({"title": entry.title, "link": entry.link})
            except Exception as e:
                log(f"      ❌ Google RSS fallback also failed: {e}")
            
        return threads[:limit]

    def extract_post_data(self, reddit_url):
        """
        Extracts deep data from a Reddit post: top comments, codes, and media.
        """
        try:
            # Handle Google News redirect links
            if "news.google.com" in reddit_url:
                r = self.session.head(reddit_url, allow_redirects=True, timeout=10)
                reddit_url = r.url

            if "reddit.com" not in reddit_url: return None

            clean_url = reddit_url.split("?")[0].rstrip('/')
            json_url = f"{clean_url}.json"
            
            resp = self.session.get(json_url, timeout=12)
            if resp.status_code != 200: return None
            
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2: return None

            post_info = data[0]['data']['children'][0]['data']
            comments_info = data[1]['data']['children']

            result = {
                "title": post_info.get('title'),
                "subreddit": post_info.get('subreddit_name_prefixed'),
                "url": reddit_url,
                "media": [],
                "codes": [],
                "insights": []
            }

            self._extract_media(post_info, result["media"])
            self._extract_codes(post_info.get('selftext', ''), result["codes"])

            for comment in comments_info:
                c_data = comment.get('data', {})
                body = c_data.get('body')
                if not body or body in ["[deleted]", "[removed]"]: continue
                
                self._extract_codes(body, result["codes"])

                # فلترة التعليقات القيمة فقط
                if len(body) > 60 and c_data.get('score', 0) > 2:
                    clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', body) # إزالة روابط الماركدوان
                    result["insights"].append({
                        "author": c_data.get('author', 'user'),
                        "text": clean_body.strip(),
                        "score": c_data.get('score', 0),
                        "permalink": f"https://www.reddit.com{c_data.get('permalink')}"
                    })

            result["insights"].sort(key=lambda x: x['score'], reverse=True)
            result["insights"] = result["insights"][:5] # أخذ أفضل 5 تعليقات
            
            return result
        except Exception:
            # log(f"      ❌ Failed to parse Reddit URL: {reddit_url} - {e}")
            return None

    def _extract_media(self, post_data, media_list):
        # Direct image/gif link
        if post_data.get('post_hint') == 'image' or post_data.get('url', '').endswith(('.jpg', '.png', '.jpeg', '.gif')):
            media_list.append({"type": "image", "url": post_data.get('url'), "caption": post_data.get('title')})
        
        # Hosted video
        if post_data.get('is_video') and post_data.get('media', {}).get('reddit_video'):
            vid_url = post_data['media']['reddit_video'].get('fallback_url')
            if vid_url:
                media_list.append({"type": "video", "url": vid_url, "caption": post_data.get('title')})
        
        # Gallery
        if post_data.get('is_gallery') and 'media_metadata' in post_data:
            for item_data in post_data['media_metadata'].values():
                if item_data.get('status') == 'valid':
                    img_url = item_data.get('s', {}).get('u', '').replace('&amp;', '&')
                    if img_url:
                        media_list.append({"type": "image", "url": img_url, "caption": "Gallery image"})

    def _extract_codes(self, text, code_list):
        if not text: return
        # Regex for markdown code blocks (```...```)
        matches = re.findall(r'```(?:[a-z]*\n)?(.*?)```', text, re.DOTALL)
        for m in matches:
            code = m.strip()
            if code and code not in code_list: code_list.append(code)
        
        # Fallback for indented code blocks (4 spaces)
        lines = text.split('\n')
        current_block = []
        in_block = False
        for line in lines:
            if line.startswith('    '):
                current_block.append(line[4:])
                in_block = True
            else:
                if in_block:
                    code = '\n'.join(current_block).strip()
                    if code and code not in code_list: code_list.append(code)
                    current_block = []
                    in_block = False
        if in_block and current_block:
             code = '\n'.join(current_block).strip()
             if code and code not in code_list: code_list.append(code)


def get_community_intel(keyword):
    """
    Main function to be called from the pipeline.
    It orchestrates the search and data extraction from Reddit.
    Returns a formatted text report and a list of media URLs.
    """
    log(f"🧠 [Reddit Intel] Mining discussions & visual evidence for: '{keyword}'...")
    manager = RedditManager()
    threads = manager.search_reddit_threads(keyword)
    
    if not threads:
        log("   - No relevant Reddit threads found.")
        return "", []

    all_data = [manager.extract_post_data(thread['link']) for thread in threads]
    all_data = [data for data in all_data if data] # إزالة أي نتائج فاشلة
    
    if not all_data: 
        log("   - Threads found, but failed to parse data.")
        return "", []

    report = "\n\n=== 📢 REAL HUMAN EXPERIENCES & REDDIT DISCUSSIONS ===\n"
    report += "INSTRUCTIONS FOR WRITER: Integrate these real-world perspectives. Cite the Subreddit and link to the discussion.\n\n"

    all_media = []
    for post in all_data:
        report += f"--- SOURCE: {post['subreddit']} ---\n"
        report += f"POST TITLE: {post['title']}\n"
        report += f"LINK: {post['url']}\n"
        if post['insights']:
            report += "TOP USER COMMENTS:\n"
            for comment in post['insights']:
                report += f"- User u/{comment['author']} (Score: {comment['score']}): \"{comment['text'][:400]}\"\n"
        if post['codes']:
            report += "CODE SNIPPETS FOUND:\n"
            for code in post['codes'][:1]: # أخذ أول كود فقط لتقليل الحجم
                report += f"```\n{code[:500]}\n```\n"
        report += "\n"
        all_media.extend(post['media'])

    # إزالة الوسائط المكررة
    unique_media = list({m['url']: m for m in all_media}.values())

    log(f"   ✅ Gathered intel from {len(all_data)} Reddit threads. Found {len(unique_media)} unique media items.")
    return report, unique_media
