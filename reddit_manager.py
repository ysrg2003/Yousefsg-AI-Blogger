# FILE: reddit_manager.py
# ROLE: Advanced Reddit Intelligence & Visual Evidence Gatherer (V3 - Selenium Powered)
# DESCRIPTION: Uses a primary Selenium-based Google search to aggressively find relevant discussions,
#              mimicking human search patterns for maximum accuracy.

import requests
import urllib.parse
import feedparser
import time
import re
from bs4 import BeautifulSoup
from config import log

# استيراد مكتبات Selenium الضرورية
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

class RedditManager:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _search_with_selenium(self, keyword, limit=5):
        """
        Primary search method: Uses Selenium to perform a smart Google search for Reddit threads.
        This is far more reliable for finding conversational topics.
        """
        log(f"      - [Selenium Search] Actively hunting Google for Reddit threads...")
        threads = []
        
        # استعلام بحث ذكي جداً مصمم للنقاشات وليس فقط للمراجعات
        search_query = f'site:reddit.com "{keyword}" ("my experience" OR "is it worth it" OR "how I" OR "a warning" OR "the truth about" OR "guide")'
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            
            driver.get(f"https://www.google.com/search?q={urllib.parse.quote(search_query)}")
            time.sleep(2) # انتظار تحميل النتائج
            
            # استهداف روابط نتائج البحث في جوجل
            links = driver.find_elements(By.CSS_SELECTOR, 'div.g a')
            for link in links:
                href = link.get_attribute('href')
                if href and "reddit.com/r/" in href:
                    title_element = link.find_element(By.CSS_SELECTOR, 'h3')
                    title = title_element.text if title_element else "Reddit Thread"
                    if not any(t['link'] == href for t in threads):
                         threads.append({"title": title, "link": href})
                if len(threads) >= limit:
                    break
            
            return threads
        except Exception as e:
            log(f"      ⚠️ Selenium search for Reddit failed: {str(e)[:100]}")
            return []
        finally:
            if driver:
                driver.quit()

    def search_reddit_threads(self, keyword, limit=4):
        """
        Orchestrates the search for Reddit threads using a waterfall strategy:
        1. Selenium-Google (Primary, most powerful)
        2. DuckDuckGo HTML (Fallback, lightweight)
        """
        # --- المرحلة الأولى: البحث بقوة Selenium (الأفضل) ---
        selenium_threads = self._search_with_selenium(keyword, limit)
        if selenium_threads:
            log(f"      ✅ Selenium found {len(selenium_threads)} relevant threads.")
            return selenium_threads

        # --- المرحلة الثانية: الخطة البديلة (DuckDuckGo) ---
        log("      - Selenium search yielded no results. Falling back to DuckDuckGo.")
        threads = []
        try:
            search_query = f"site:reddit.com {keyword} (review OR experience OR opinion OR problem)"
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.select('a.result__a')
                for a in links:
                    link = a.get('href', '')
                    if "reddit.com/r/" in link:
                        if "uddg=" in link:
                            link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                        if not any(t['link'] == link for t in threads):
                            threads.append({"title": a.text.strip() or "Reddit Post", "link": link})
                    if len(threads) >= limit: break
        except Exception as e:
            log(f"      ❌ DuckDuckGo search also failed: {e}")
            
        return threads

    # باقي دوال الكلاس (extract_post_data, _extract_media, _extract_codes) تبقى كما هي بدون تغيير
    def extract_post_data(self, reddit_url):
        """
        Extracts deep data from a Reddit post: top comments, codes, and media.
        """
        try:
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

                if len(body) > 60 and c_data.get('score', 0) > 2:
                    clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', body)
                    result["insights"].append({
                        "author": c_data.get('author', 'user'),
                        "text": clean_body.strip(),
                        "score": c_data.get('score', 0),
                        "permalink": f"https://www.reddit.com{c_data.get('permalink')}"
                    })

            result["insights"].sort(key=lambda x: x['score'], reverse=True)
            result["insights"] = result["insights"][:5]
            
            return result
        except Exception:
            return None

    def _extract_media(self, post_data, media_list):
        if post_data.get('post_hint') == 'image' or post_data.get('url', '').endswith(('.jpg', '.png', '.jpeg', '.gif')):
            media_list.append({"type": "image", "url": post_data.get('url'), "caption": post_data.get('title')})
        
        if post_data.get('is_video') and post_data.get('media', {}).get('reddit_video'):
            vid_url = post_data['media']['reddit_video'].get('fallback_url')
            if vid_url:
                media_list.append({"type": "video", "url": vid_url, "caption": post_data.get('title')})
        
        if post_data.get('is_gallery') and 'media_metadata' in post_data:
            for item_data in post_data['media_metadata'].values():
                if item_data.get('status') == 'valid':
                    img_url = item_data.get('s', {}).get('u', '').replace('&amp;', '&')
                    if img_url:
                        media_list.append({"type": "image", "url": img_url, "caption": "Gallery image"})

    def _extract_codes(self, text, code_list):
        if not text: return
        matches = re.findall(r'```(?:[a-z]*\n)?(.*?)```', text, re.DOTALL)
        for m in matches:
            code = m.strip()
            if code and code not in code_list: code_list.append(code)
        
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


# دالة get_community_intel تبقى كما هي
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
            for code in post['codes'][:1]:
                report += f"```\n{code[:500]}\n```\n"
        report += "\n"
        all_media.extend(post['media'])

    unique_media = list({m['url']: m for m in all_media}.values())

    log(f"   ✅ Gathered intel from {len(all_data)} Reddit threads. Found {len(unique_media)} unique media items.")
    return report, unique_media
