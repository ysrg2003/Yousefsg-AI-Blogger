import requests
import urllib.parse
import logging
import feedparser
import time
import re
from bs4 import BeautifulSoup

# إعداد اللوجر بشكل متوافق مع المشروع
def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [REDDIT-INTEL] {msg}", flush=True)

class RedditManager:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_reddit_threads(self, keyword, limit=5):
        """
        يبحث عن نقاشات حقيقية في Reddit باستخدام DuckDuckGo HTML كبوابة بديلة.
        """
        threads = []
        search_query = f"site:reddit.com {keyword} (review OR experience OR opinion)"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
        
        for attempt in range(2):
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    links = soup.find_all('a')
                    for a in links:
                        link = a.get('href', '')
                        if "reddit.com/r/" in link:
                            if "uddg=" in link:
                                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                            if not any(t['link'] == link for t in threads):
                                threads.append({"title": a.text.strip() or "Reddit Post", "link": link})
                        if len(threads) >= limit: break
                    if threads: break
                elif resp.status_code == 202:
                    time.sleep(2)
                else:
                    break
            except:
                break
        
        # Fallback to Google RSS
        if not threads:
            try:
                rss_url = f"https://news.google.com/rss/search?q=site%3Areddit.com+{urllib.parse.quote(keyword)}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:limit]:
                    threads.append({"title": entry.title, "link": entry.link})
            except: pass
            
        return threads[:limit]

    def extract_post_data(self, reddit_url):
        """
        يستخرج البيانات العميقة من منشور Reddit: تعليقات، أكواد، وسائط.
        """
        try:
            # معالجة روابط جوجل نيوز إذا وجدت
            if "news.google.com" in reddit_url:
                r = self.session.get(reddit_url, allow_redirects=True, timeout=10)
                reddit_url = r.url

            if "reddit.com" not in reddit_url:
                return None

            # تنظيف الرابط وتحويله لـ JSON
            clean_url = reddit_url.split("?")[0].rstrip('/')
            json_url = f"{clean_url}.json"
            
            resp = self.session.get(json_url, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return None

            post_info = data[0]['data']['children'][0]['data']
            comments_info = data[1]['data']['children']

            result = {
                "title": post_info.get('title'),
                "subreddit": post_info.get('subreddit_name_prefixed'),
                "author": post_info.get('author'),
                "selftext": post_info.get('selftext', ''),
                "url": reddit_url,
                "media": [],
                "codes": [],
                "insights": []
            }

            self._extract_media(post_info, result["media"])
            self._extract_codes(post_info.get('selftext', ''), result["codes"])

            for comment in comments_info:
                c_data = comment.get('data', {})
                if not c_data or c_data.get('body') in ["[deleted]", "[removed]", None]:
                    continue
                
                body = c_data.get('body', '')
                score = c_data.get('score', 0)
                self._extract_codes(body, result["codes"])

                if len(body) > 50:
                    clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', body)
                    result["insights"].append({
                        "author": c_data.get('author'),
                        "text": clean_body,
                        "score": score,
                        "permalink": f"https://www.reddit.com{c_data.get('permalink')}"
                    })

            result["insights"].sort(key=lambda x: x['score'], reverse=True)
            result["insights"] = result["insights"][:5]
            
            return result
        except:
            return None

    def _extract_media(self, post_data, media_list):
        if post_data.get('post_hint') == 'image' or post_data.get('url', '').endswith(('.jpg', '.png', '.jpeg', '.gif')):
            media_list.append({"type": "image", "url": post_data.get('url'), "caption": post_data.get('title')})
        
        if post_data.get('is_video') and 'media' in post_data and post_data['media']:
            vid_url = post_data['media'].get('reddit_video', {}).get('fallback_url')
            if vid_url:
                media_list.append({"type": "video", "url": vid_url, "caption": post_data.get('title')})
        
        if 'is_gallery' in post_data and post_data['is_gallery'] and 'media_metadata' in post_data:
            for item_id, item_data in post_data['media_metadata'].items():
                if item_data['status'] == 'valid':
                    img_url = item_data['s'].get('u', '').replace('&amp;', '&')
                    if img_url:
                        media_list.append({"type": "image", "url": img_url, "caption": f"Gallery item"})

    def _extract_codes(self, text, code_list):
        if not text: return
        matches = re.findall(r'```(?:[a-z]*\n)?(.*?)```', text, re.DOTALL)
        for m in matches:
            code = m.strip()
            if code and code not in code_list: code_list.append(code)
        
        if not matches:
            lines = text.split('\n')
            current_block = []
            for line in lines:
                if line.startswith('    '): current_block.append(line[4:])
                else:
                    if current_block:
                        code_list.append('\n'.join(current_block))
                        current_block = []
            if current_block: code_list.append('\n'.join(current_block))

def get_community_intel(keyword):
    log(f"🧠 Mining Reddit intelligence for: '{keyword}'...")
    manager = RedditManager()
    threads = manager.search_reddit_threads(keyword)
    
    if not threads:
        return "", []

    all_data = []
    for thread in threads:
        data = manager.extract_post_data(thread['link'])
        if data: all_data.append(data)
        time.sleep(1)

    if not all_data: return "", []

    report = "\n\n=== 📢 REAL HUMAN EXPERIENCES & REDDIT DISCUSSIONS ===\n"
    report += "INSTRUCTIONS FOR WRITER: Integrate these real-world perspectives. Cite the Subreddit and link to the discussion.\n\n"

    all_media = []
    for idx, post in enumerate(all_data):
        report += f"--- SOURCE {idx+1}: {post['subreddit']} ---\n"
        report += f"POST TITLE: {post['title']}\n"
        report += f"LINK: {post['url']}\n"
        if post['insights']:
            report += "TOP USER COMMENTS:\n"
            for comment in post['insights'][:3]:
                report += f"- User u/{comment['author']}: \"{comment['text'][:400]}\"\n"
        if post['codes']:
            report += "CODE SNIPPETS:\n"
            for code in post['codes'][:1]: report += f"```\n{code[:500]}\n```\n"
        report += "\n"
        for m in post['media']:
            if m['url'] not in [x['url'] for x in all_media]: all_media.append(m)

    log(f"✅ Gathered intel from {len(all_data)} Reddit threads.")
    return report, all_media
