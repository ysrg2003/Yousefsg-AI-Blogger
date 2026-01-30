# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Deep Intelligence & Evidence Gathering Module (V9.1 - Simplified & Integrated)
# STRATEGY: 
#   1. RELIABLE FETCHING: Uses a proven 'requests'-based approach to avoid Selenium blocks.
#   2. SMART SEARCH: Integrates with 'ai_strategy' for Graduated Search Plans.
#   3. FULL INTEGRATION: Returns data in the exact format required by main.py.
# ==============================================================================

import requests
import json
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Project imports for full integration
from config import log
import ai_strategy

class RedditManager:
    """
    A robust Reddit evidence gatherer using a simple and effective requests-based approach.
    This version is based on the user-provided successful script and fully integrated
    into the main project's workflow.
    """
    BASE_URL = "https://www.reddit.com"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetches JSON data from a given Reddit URL with retry logic for rate limiting.
        """
        try:
            if ".json" not in url:
                if "?" in url:
                    base, params = url.split("?", 1)
                    url = f"{base.rstrip('/')}.json?{params}"
                else:
                    url = f"{url.rstrip('/')}.json"
            
            response = self.session.get(url, timeout=15)
            if response.status_code == 429:
                log("   ⚠️ Reddit rate limit hit. Waiting for 2 seconds...")
                time.sleep(2)
                response = self.session.get(url, timeout=15)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log(f"   ❌ Reddit request failed for {url}: {e}")
            return None
        except json.JSONDecodeError:
            log(f"   ❌ Failed to parse JSON from Reddit. The response was likely an HTML block page.")
            return None

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

    def get_all_data(self, query: str, limit: int = 3) -> Dict[str, Any]:
        """Fetches all raw and structured data into a dictionary ready for JSON conversion."""
        search_url = f"{self.BASE_URL}/search.json?q={urllib.parse.quote(query)}&limit={limit}&sort=relevance&t=month"
            
        search_data = self._get_json(search_url)
        results = { "query": query, "posts": [] }

        if search_data and "data" in search_data and "children" in search_data["data"]:
            for post_item in search_data["data"]["children"]:
                permalink = post_item.get('data', {}).get('permalink')
                if permalink:
                    post_url = f"{self.BASE_URL}{permalink}"
                    details = self.get_post_details(post_url)
                    if details and details.get("post"):
                         results["posts"].append(details)
        return results

    def get_post_details(self, post_url: str) -> Optional[Dict[str, Any]]:
        data = self._get_json(post_url)
        if not data or not isinstance(data, list) or len(data) < 2:
            return None

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
        except (IndexError, KeyError, TypeError):
             return None

    def _parse_comments(self, children: List[Dict[str, Any]], post_url: str) -> List[Dict[str, Any]]:
        parsed = []
        if not children: return parsed
        for child in children:
            if child.get("kind") == "t1":
                d = child.get("data", {})
                body = d.get("body", "")
                if body in ["[deleted]", "[removed]"] or "bot" in str(d.get("author", "")).lower():
                    continue
                
                replies_data = d.get("replies", {})
                nested_children = []
                if replies_data and isinstance(replies_data, dict):
                    nested_children = replies_data.get("data", {}).get("children", [])

                parsed.append({
                    "comment_id": d.get("id"),
                    "author": d.get("author"),
                    "body": body,
                    "url": f"{post_url.rstrip('/')}/{d.get('id')}/",
                    "score": d.get("score"),
                    "media": self._extract_media(d),
                    "codes": self._extract_codes(body),
                    "replies": self._parse_comments(nested_children, post_url)
                })
        return parsed

def generate_writer_brief(data: Dict[str, Any]) -> str:
    """Converts the rich data into a detailed text brief for the AI writer."""
    if not data.get("posts"): return ""
    brief = f"--- REDDIT EVIDENCE FILE ---\nPrimary Topic: {data['query']}\n\n"
    for i, item in enumerate(data["posts"], 1):
        post = item["post"]
        brief += f"== THREAD #{i}: {post.get('title', 'N/A')} ==\n"
        brief += f"URL: {post.get('url', 'N/A')}\nUpvotes: {post.get('score', 0)}\n"
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
                if c.get('media'): brief += f"{indent}  Media Found: {', '.join(c['media'])}\n"
                if c.get('replies'): format_comments_brief(c['replies'], level + 1)
        if item.get("comments"):
            brief += "Community Discussion:\n"
            format_comments_brief(item["comments"])
        brief += "\n"
    return brief

def get_community_intel(long_keyword: str):
    """
    Main adapter function called by main.py. Implements the graduated search strategy.
    """
    log(f"🧠 [Reddit Manager] Initiating Graduated Search for: '{long_keyword}'")
    
    search_plan = ai_strategy.generate_graduated_search_plan(long_keyword)
    manager = RedditManager()
    final_data = None
    successful_query = ""

    for attempt_idx, query in enumerate(search_plan):
        log(f"   🔎 Attempt {attempt_idx + 1}/{len(search_plan)}: Searching for '{query}'...")
        raw_data = manager.get_all_data(query, limit=3)
        if raw_data and raw_data.get("posts"):
            log(f"      ✅ Success! Found {len(raw_data['posts'])} threads with query: '{query}'")
            final_data = raw_data
            successful_query = query
            break
        else:
            log(f"      ⚠️ No results for '{query}'. Moving to next tier...")
            
    if not final_data or not final_data.get("posts"):
        log("   ❌ All search attempts failed. No Reddit intelligence available.")
        return "", []

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
            if c.get("replies"): collect_media(c["replies"], post_title)

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
        if item.get("comments"): collect_media(item["comments"], post_title_short)
            
    log(f"   ✅ Reddit Intel Complete. Used query: '{successful_query}'. Found {len(media_assets)} assets.")
    return text_context, media_assets
