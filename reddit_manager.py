# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Deep Intelligence & Evidence Gathering Module (V8 - Hybrid Engine)
# STRATEGY: 
#   1. HYBRID FETCHING: Attempts lightweight 'requests' first. If blocked (403/429),
#      it automatically fails over to 'Selenium' (Headless Browser) to bypass protections.
#   2. SMART SEARCH: Integrates with 'ai_strategy' for Graduated Search Plans.
#   3. ROBUST PARSING: Handles raw text extraction from body to solve 'pre' tag errors.
#   4. DEEP EXTRACTION: Recursively fetches media, code, and permalinks from comments.
# ==============================================================================

import json
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Requests for primary (fast) fetching
import requests

# Selenium Imports for backup (robust) fetching
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# Project imports
from config import log
import ai_strategy  # Central brain for keyword optimization

class RedditManager:
    """
    A hybrid Reddit evidence gatherer. 
    Primary Mode: Requests (Fast).
    Backup Mode: Selenium (Anti-Bot Bypass).
    """
    BASE_URL = "https://www.reddit.com"
    
    # Standard User-Agent to mimic a real browser in requests
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def _get_page_with_selenium(self, url: str) -> Optional[dict]:
        """
        BACKUP METHOD: Fetches content using a headless Chrome browser.
        Used when standard requests are blocked (403/429).
        """
        log(f"      🛡️ [Anti-Bot] Activating Selenium Shield for: {url[:60]}...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"user-agent={self.USER_AGENT}")
        
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(45)
            
            driver.get(url)
            # Wait for content to load (handling potential JS redirects)
            time.sleep(3) 
            
            # Robust JSON Extraction Strategy:
            # 1. Try fetching text from the <body> (Browsers often render raw JSON as text in body)
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                # Attempt to parse immediately
                return json.loads(body_text)
            except json.JSONDecodeError:
                # 2. If body isn't valid JSON, Chrome might have wrapped it in a <pre> tag
                try:
                    pre_text = driver.find_element(By.TAG_NAME, "pre").text
                    return json.loads(pre_text)
                except:
                    log(f"      ❌ Selenium: Page loaded but content is not JSON (Likely HTML Block Page).")
                    return None
            except Exception as e:
                log(f"      ⚠️ Selenium Element Error: {e}")
                return None

        except Exception as e:
            log(f"      ❌ Selenium Critical Failure: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """
        HYBRID FETCHER: Tries 'requests' first. Falls back to 'Selenium' on failure.
        """
        # Ensure URL points to JSON endpoint
        if ".json" not in url:
            if "?" in url:
                base, params = url.split("?", 1)
                url = f"{base.rstrip('/')}.json?{params}"
            else:
                url = f"{url.rstrip('/')}.json"

        # --- ATTEMPT 1: Requests (Fast) ---
        try:
            # Short timeout for requests to fail fast if hanging
            response = self.session.get(url, timeout=10)
            
            # Check for blocking status codes
            if response.status_code in [403, 429]:
                log(f"   ⚠️ Requests blocked ({response.status_code}). Switching to Selenium...")
                return self._get_page_with_selenium(url)
            
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            # On connection errors or timeouts, also try Selenium as a last resort
            log(f"   ⚠️ Requests failed ({e}). Switching to Selenium...")
            return self._get_page_with_selenium(url)
        except Exception as e:
            log(f"   ❌ Unexpected Error in fetch: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        """
        Extracts visual media links (images, videos, gifs) from post or comment data.
        """
        media = []
        url = data.get("url", "")
        
        # 1. Check direct link
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "v.redd.it", "imgur.com", "gallery"]):
            media.append(url)
        
        # 2. Check text body for embedded links via Regex
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
            # Parse Main Post (Index 0)
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
            
            # Parse Comments (Index 1)
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

def get_community_intel(long_keyword: str):
    """
    Main adapter function called by main.py.
    Implements a GRADUATED SEARCH STRATEGY using 'ai_strategy' + Hybrid Fetching.
    """
    log(f"🧠 [Reddit Manager] Initiating Graduated Search for: '{long_keyword}'")
    
    # 1. Get the graduated plan from AI Strategy
    search_plan = ai_strategy.generate_graduated_search_plan(long_keyword)
    
    manager = RedditManager()
    final_data = None
    successful_query = ""

    # 2. Iterate through the plan (Specific -> Contextual -> Broad)
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
        """Helper to recursively collect media from comments."""
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
        
        # Collect media from the main post
        for media_url in post.get("media", []):
            media_assets.append({
                "type": "image", 
                "url": media_url, 
                "description": f"Community evidence for: {post_title_short}",
                "score": post.get("score", 0), 
                "source": "Reddit Post"
            })
            
        # Collect media from comments
        if item.get("comments"):
            collect_media(item["comments"], post_title_short)
            
    log(f"   ✅ Reddit Intel Complete. Used query: '{successful_query}'. Found {len(media_assets)} assets.")
    return text_context, media_assets
