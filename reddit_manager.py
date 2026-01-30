# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Deep Intelligence & Evidence Gathering Module (V5 - Selenium Powered)
# STRATEGY: 
#   1. Uses Selenium to emulate a real browser, bypassing Reddit's 403 Forbidden 
#      blocks on data center IPs (GitHub Actions).
#   2. Integrates with 'ai_strategy' to use smart, AI-optimized search queries.
#   3. Implements a Tiered Search Fallback (Smart Query -> Original Query).
#   4. Deeply extracts media, code blocks, and permalinks from posts AND comments.
# ==============================================================================

import json
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Selenium Imports for robust, browser-based scraping (Bypassing 403s)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# Project imports
from config import log
import ai_strategy  # Links to the central brain for keyword optimization

class RedditManager:
    """
    A robust Reddit evidence gatherer that uses Selenium to bypass advanced bot detection.
    It fetches deep thread details, including recursive comments and visual evidence.
    """
    BASE_URL = "https://www.reddit.com"

    def _get_page_with_selenium(self, url: str) -> Optional[dict]:
        """
        Fetches the content of a URL using a headless Chrome browser.
        This is the core function to avoid getting blocked by Reddit filters.
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        # Using a standard user-agent to look like a regular user
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(45)
            
            driver.get(url)
            # Wait for the JSON content to be displayed (browser renders JSON inside a 'pre' tag)
            time.sleep(2) 
            
            # Find the element containing the JSON text
            pre_element = driver.find_element(By.TAG_NAME, "pre")
            json_text = pre_element.text
            
            return json.loads(json_text)

        except Exception as e:
            log(f"   ❌ Selenium failed to fetch {url}: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Ensures the URL is correctly formatted for JSON access and fetches it via Selenium.
        """
        if ".json" not in url:
            # Handle query parameters correctly
            if "?" in url:
                base, params = url.split("?", 1)
                url = f"{base.rstrip('/')}.json?{params}"
            else:
                url = f"{url.rstrip('/')}.json"
        
        return self._get_page_with_selenium(url)

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        """
        Extracts visual media links (images, videos, gifs) from post or comment data.
        """
        media = []
        url = data.get("url", "")
        
        # 1. Check direct link
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "v.redd.it", "imgur.com", "gallery"]):
            media.append(url)
        
        # 2. Check text body for embedded links
        text = data.get("selftext", "") or data.get("body", "")
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif|mp4))', text, re.IGNORECASE)
        media.extend(urls)
        
        # 3. Check Reddit's internal media metadata (Galleries)
        if "media_metadata" in data and isinstance(data.get("media_metadata"), dict):
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    # Decode URL entities (e.g., &amp; -> &)
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        """
        Extracts code snippets (both blocks and inline) from text.
        """
        if not text: return []
        # Multi-line code blocks
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        # Inline code snippets
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def _parse_comments(self, children: List[Dict[str, Any]], post_url: str) -> List[Dict[str, Any]]:
        """
        Recursively parses comments to extract details, media, code, and direct permalinks.
        """
        parsed = []
        for child in children:
            if child.get("kind") != "t1": continue # Ensure it's a comment
            
            d = child["data"]
            body = d.get("body", "")
            comment_id = d.get("id")
            
            # Skip deleted/removed comments or bots
            if body in ["[deleted]", "[removed]"] or "bot" in str(d.get("author", "")).lower():
                continue

            parsed.append({
                "comment_id": comment_id,
                "author": d.get("author"),
                "body": body,
                "url": f"{post_url.rstrip('/')}/{comment_id}/", # Direct link to this specific comment
                "score": d.get("score"),
                "media": self._extract_media(d),
                "codes": self._extract_codes(body),
                # Recursively parse replies if they exist
                "replies": self._parse_comments(d.get("replies", {}).get("data", {}).get("children", []), post_url)
            })
        return parsed

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
        """
        Gets full details for a single post including a deep parse of its comments.
        """
        data = self._get_json(post_url)
        
        # Validate data structure
        if not data or not isinstance(data, list) or len(data) < 2:
            return {"post": {}, "comments": []}

        try:
            # Parse Main Post
            p_data = data[0]["data"]["children"][0]["data"]
            post_details = {
                "title": p_data.get("title"),
                "text": p_data.get("selftext"),
                "author": p_data.get("author"),
                "url": f"{self.BASE_URL}{p_data.get('permalink')}",
                "score": p_data.get("score", 0),
                "media": self._extract_media(p_data),
                "codes": self._extract_codes(p_data.get("selftext", ""))
            }
            
            # Parse Comments
            comments = self._parse_comments(data[1].get("data", {}).get("children", []), post_details["url"])
            return {"post": post_details, "comments": comments}
            
        except (IndexError, KeyError) as e:
            log(f"   ⚠️ Could not parse post details for {post_url}: {e}")
            return {"post": {}, "comments": []}

    def get_all_data(self, query: str, limit: int = 3) -> Dict[str, Any]:
        """
        Searches Reddit and gets deep details for the top relevant posts.
        """
        encoded_query = urllib.parse.quote(query)
        # Search for the query, sorted by relevance, limited to the last month for freshness
        search_url = f"{self.BASE_URL}/search.json?q={encoded_query}&limit={limit}&sort=relevance&t=month"
        
        search_data = self._get_json(search_url)
        results = {"query": query, "posts": []}

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                permalink = post_item.get('data', {}).get('permalink')
                if permalink:
                    post_url = f"{self.BASE_URL}{permalink}"
                    details = self.get_post_details(post_url)
                    if details.get("post"):
                        results["posts"].append(details)
        return results

def generate_writer_brief(data: Dict[str, Any]) -> str:
    """
    Converts the rich data into a detailed text brief for the AI writer.
    Includes threads, content summary, and nested comments.
    """
    if not data.get("posts"): return ""

    brief = f"--- REDDIT EVIDENCE FILE ---\n"
    brief += f"Primary Topic: {data['query']}\n\n"
    
    for i, item in enumerate(data["posts"], 1):
        post = item["post"]
        brief += f"== THREAD #{i}: {post.get('title', 'N/A')} ==\n"
        brief += f"URL: {post.get('url', 'N/A')}\n"
        brief += f"Upvotes: {post.get('score', 0)}\n"
        
        content = str(post.get('text', '')).strip()
        if content:
            brief += f"Post Content: {content[:800]}{'...' if len(content) > 800 else ''}\n"
        
        # Helper to format comments recursively
        def format_comments_brief(comments, level=0):
            nonlocal brief
            indent = "  " * level
            for c in comments[:3]: # Limit to top 3 comments/replies per level to avoid context overflow
                brief += f"{indent}- COMMENT by u/{c.get('author', 'N/A')} (Score: {c.get('score', 0)}):\n"
                brief += f"{indent}  URL: {c.get('url', 'N/A')}\n"
                brief += f"{indent}  Text: {str(c.get('body', ''))[:300].replace(chr(10), ' ')}{'...' if len(c.get('body','')) > 300 else ''}\n"
                
                if c.get('media'):
                    brief += f"{indent}  Media Found: {', '.join(c['media'])}\n"
                if c.get('codes'):
                    brief += f"{indent}  Code Snippets Found: {len(c['codes'])}\n"
                
                if c.get('replies'):
                    format_comments_brief(c['replies'], level + 1)

        if item.get("comments"):
            brief += "Community Discussion:\n"
            format_comments_brief(item["comments"])
        brief += "\n"
    return brief

# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Deep Intelligence & Evidence Gathering Module (V6 - Graduated Search)
# STRATEGY: 
#   1. Uses Selenium to emulate a real browser (Anti-403).
#   2. Uses a GRADUATED SEARCH STRATEGY (Specific -> Contextual -> Broad).
#   3. Iterates through the search plan until valid results are found.
#   4. Deeply extracts media, code, and comments.
# ==============================================================================

import json
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# Project imports
from config import log
import ai_strategy  # Updated to support graduated plans

class RedditManager:
    """
    A robust Reddit evidence gatherer using Selenium and Tiered Search.
    """
    BASE_URL = "https://www.reddit.com"

    def _get_page_with_selenium(self, url: str) -> Optional[dict]:
        """
        Fetches the content of a URL using a headless Chrome browser.
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(45)
            
            driver.get(url)
            time.sleep(2) 
            
            pre_element = driver.find_element(By.TAG_NAME, "pre")
            json_text = pre_element.text
            
            return json.loads(json_text)

        except Exception as e:
            log(f"   ❌ Selenium failed to fetch {url}: {e}")
            return None
        finally:
            if driver:
                try: driver.quit()
                except: pass

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        if ".json" not in url:
            if "?" in url:
                base, params = url.split("?", 1)
                url = f"{base.rstrip('/')}.json?{params}"
            else:
                url = f"{url.rstrip('/')}.json"
        return self._get_page_with_selenium(url)

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        media = []
        url = data.get("url", "")
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "v.redd.it", "imgur.com", "gallery"]):
            media.append(url)
        
        text = data.get("selftext", "") or data.get("body", "")
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif|mp4))', text, re.IGNORECASE)
        media.extend(urls)
        
        if "media_metadata" in data and isinstance(data.get("media_metadata"), dict):
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        if not text: return []
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def _parse_comments(self, children: List[Dict[str, Any]], post_url: str) -> List[Dict[str, Any]]:
        parsed = []
        for child in children:
            if child.get("kind") != "t1": continue
            d = child["data"]
            body = d.get("body", "")
            comment_id = d.get("id")
            
            if body in ["[deleted]", "[removed]"] or "bot" in str(d.get("author", "")).lower():
                continue

            parsed.append({
                "comment_id": comment_id,
                "author": d.get("author"),
                "body": body,
                "url": f"{post_url.rstrip('/')}/{comment_id}/",
                "score": d.get("score"),
                "media": self._extract_media(d),
                "codes": self._extract_codes(body),
                "replies": self._parse_comments(d.get("replies", {}).get("data", {}).get("children", []), post_url)
            })
        return parsed

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
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
                "score": p_data.get("score", 0),
                "media": self._extract_media(p_data),
                "codes": self._extract_codes(p_data.get("selftext", ""))
            }
            comments = self._parse_comments(data[1].get("data", {}).get("children", []), post_details["url"])
            return {"post": post_details, "comments": comments}
        except (IndexError, KeyError) as e:
            log(f"   ⚠️ Could not parse post details for {post_url}: {e}")
            return {"post": {}, "comments": []}

    def get_all_data(self, query: str, limit: int = 3) -> Dict[str, Any]:
        encoded_query = urllib.parse.quote(query)
        search_url = f"{self.BASE_URL}/search.json?q={encoded_query}&limit={limit}&sort=relevance&t=month"
        
        search_data = self._get_json(search_url)
        results = {"query": query, "posts": []}

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                permalink = post_item.get('data', {}).get('permalink')
                if permalink:
                    post_url = f"{self.BASE_URL}{permalink}"
                    details = self.get_post_details(post_url)
                    if details.get("post"):
                        results["posts"].append(details)
        return results

def generate_writer_brief(data: Dict[str, Any]) -> str:
    if not data.get("posts"): return ""

    brief = f"--- REDDIT EVIDENCE FILE ---\n"
    brief += f"Primary Topic: {data['query']}\n\n"
    
    for i, item in enumerate(data["posts"], 1):
        post = item["post"]
        brief += f"== THREAD #{i}: {post.get('title', 'N/A')} ==\n"
        brief += f"URL: {post.get('url', 'N/A')}\n"
        brief += f"Upvotes: {post.get('score', 0)}\n"
        
        content = str(post.get('text', '')).strip()
        if content:
            brief += f"Post Content: {content[:800]}{'...' if len(content) > 800 else ''}\n"
        
        def format_comments_brief(comments, level=0):
            nonlocal brief
            indent = "  " * level
            for c in comments[:3]:
                brief += f"{indent}- COMMENT by u/{c.get('author', 'N/A')} (Score: {c.get('score', 0)}):\n"
                brief += f"{indent}  URL: {c.get('url', 'N/A')}\n"
                brief += f"{indent}  Text: {str(c.get('body', ''))[:300].replace(chr(10), ' ')}{'...' if len(c.get('body','')) > 300 else ''}\n"
                if c.get('media'):
                    brief += f"{indent}  Media Found: {', '.join(c['media'])}\n"
                if c.get('codes'):
                    brief += f"{indent}  Code Snippets Found: {len(c['codes'])}\n"
                if c.get('replies'):
                    format_comments_brief(c['replies'], level + 1)

        if item.get("comments"):
            brief += "Community Discussion:\n"
            format_comments_brief(item["comments"])
        brief += "\n"
    return brief

def get_community_intel(long_keyword: str):
    """
    Main adapter function utilizing the new GRADUATED SEARCH STRATEGY.
    It iterates through Specific -> Contextual -> Broad queries until it finds data.
    """
    log(f"🧠 [Reddit Manager] Initiating Graduated Search for: '{long_keyword}'")
    
    # 1. Get the graduated plan from AI Strategy
    search_plan = ai_strategy.generate_graduated_search_plan(long_keyword)
    
    manager = RedditManager()
    final_data = None
    successful_query = ""

    # 2. Iterate through the plan
    for attempt_idx, query in enumerate(search_plan):
        log(f"   🔎 Attempt {attempt_idx + 1}/{len(search_plan)}: Searching for '{query}'...")
        
        try:
            raw_data = manager.get_all_data(query, limit=3)
            
            # Check if we found valid posts
            if raw_data and raw_data.get("posts"):
                count = len(raw_data["posts"])
                log(f"      ✅ Success! Found {count} threads with query: '{query}'")
                final_data = raw_data
                successful_query = query
                break # Stop searching if we found good results
            else:
                log(f"      ⚠️ No results for '{query}'. Moving to next tier...")
                
        except Exception as e:
            log(f"      ❌ Search error for '{query}': {e}")
            continue
            
    # 3. Process the best results found (if any)
    if not final_data or not final_data.get("posts"):
        log("   ❌ All search attempts failed. No Reddit intelligence available.")
        return "", []

    # 4. Extract Intel & Media
    text_context = generate_writer_brief(final_data)
    media_assets = []
    
    def collect_media(comments, post_title):
        nonlocal media_assets
        for c in comments:
            for media_url in c.get("media", []):
                media_assets.append({
                    "type": "image", 
                    "url": media_url, 
                    "description": f"Evidence from comment by u/{c.get('author', 'N/A')} on '{post_title}'",
                    "score": c.get("score", 0), 
                    "source": "Reddit Comment"
                })
            if c.get("replies"):
                collect_media(c["replies"], post_title)

    for item in final_data["posts"]:
        post = item.get("post", {})
        post_title_short = post.get('title', 'Untitled')[:50]
        
        for media_url in post.get("media", []):
            media_assets.append({
                "type": "image", 
                "url": media_url, 
                "description": f"Community evidence for: {post_title_short}",
                "score": post.get("score", 0), 
                "source": "Reddit Post"
            })
            
        if item.get("comments"):
            collect_media(item["comments"], post_title_short)
            
    log(f"   ✅ Reddit Intel Complete. Used query: '{successful_query}'. Found {len(media_assets)} assets.")
    return text_context, media_assets
