# ==============================================================================
# FILE: reddit_manager.py
# DESCRIPTION: Deep Intelligence & Evidence Gathering Module (V3 - Final)
# STRATEGY: Combines a simplified stealth profile (to avoid 403 errors) with
#           deep data extraction, including permalinks for every comment, and
#           media/code extraction from both posts and comments.
# ==============================================================================

import requests
import json
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional

# Use the project's official logger
from config import log

class RedditManager:
    """
    A robust Reddit evidence gatherer that provides deep, linked, and verifiable
    community intelligence for the AI writing pipeline.
    """
    BASE_URL = "https://www.reddit.com"
    # A single, common User-Agent is less suspicious than constantly changing it,
    # which solves the 403 Forbidden errors on GitHub Actions.
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetches JSON data with a simple retry for rate limiting."""
        try:
            if ".json" not in url:
                url = f"{url.rstrip('/')}.json"

            response = self.session.get(url, timeout=20)
            if response.status_code == 429:
                log("   ⚠️ Reddit rate limit hit. Waiting and retrying...")
                time.sleep(5)
                response = self.session.get(url, timeout=20)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log(f"   ❌ Reddit request failed for {url}: {e}")
            return None

    def _extract_media(self, data: Dict[str, Any]) -> List[str]:
        """Extracts visual media (images, videos, gifs) from post or comment data."""
        media = []
        url = data.get("url", "")
        if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", "v.redd.it", "imgur.com", "gallery"]):
            media.append(url)
        
        text = data.get("selftext", "") or data.get("body", "")
        # Regex to find media links within the text body
        urls = re.findall(r'(https?://[^\s)\]]+\.(?:jpg|jpeg|png|gif|mp4))', text, re.IGNORECASE)
        media.extend(urls)
        
        # Check for Reddit's gallery metadata
        if "media_metadata" in data and isinstance(data.get("media_metadata"), dict):
            for item in data["media_metadata"].values():
                if "s" in item and "u" in item["s"]:
                    # Decode URL (e.g., &amp; -> &)
                    media.append(item["s"]["u"].replace("&amp;", "&"))
        
        return list(set(media))

    def _extract_codes(self, text: str) -> List[str]:
        """Extracts code snippets from text."""
        if not text: return []
        # Multi-line code blocks
        codes = re.findall(r'```(?:[a-zA-Z]*\n)?([\s\S]*?)```', text)
        # Inline code snippets
        inline_codes = re.findall(r'`([^`\n]+)`', text)
        return list(set([c.strip() for c in codes + inline_codes if c.strip()]))

    def _parse_comments(self, children: List[Dict[str, Any]], post_url: str) -> List[Dict[str, Any]]:
        """Recursively parses comments to extract details, media, code, and permalinks."""
        parsed = []
        for child in children:
            if child.get("kind") != "t1": continue # Ensure it's a comment
            
            d = child["data"]
            body = d.get("body", "")
            comment_id = d.get("id")
            
            # Skip deleted comments or bots
            if body in ["[deleted]", "[removed]"] or "bot" in str(d.get("author", "")).lower():
                continue

            parsed.append({
                "comment_id": comment_id,
                "author": d.get("author"),
                "body": body,
                "url": f"{post_url.rstrip('/')}/{comment_id}/", # Direct link to the comment
                "score": d.get("score"),
                "media": self._extract_media(d),
                "codes": self._extract_codes(body),
                # Recursively parse replies if they exist
                "replies": self._parse_comments(d.get("replies", {}).get("data", {}).get("children", []), post_url)
            })
        return parsed

    def get_post_details(self, post_url: str) -> Dict[str, Any]:
        """Gets full details for a single post including a deep parse of its comments."""
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
        """Searches Reddit and gets deep details for the top posts."""
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
    """Converts the rich data into a detailed text brief for the AI writer."""
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
            """Helper to format comments and their replies."""
            nonlocal brief
            indent = "  " * level
            for c in comments[:3]: # Limit to top 3 comments/replies per level
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

def get_community_intel(keyword: str):
    """
    Main adapter function called by main.py. It gathers deep intelligence and formats it.
    """
    log(f"🧠 [Reddit Manager] Mining deep evidence for: '{keyword}'...")
    
    try:
        manager = RedditManager()
        raw_data = manager.get_all_data(keyword, limit=3)
        
        if not raw_data.get("posts"):
            log("   ⚠️ No relevant Reddit discussions found.")
            return "", []

        # 1. Generate the text context for the AI writer
        text_context = generate_writer_brief(raw_data)
        
        # 2. Format all found media for the main pipeline
        media_assets = []
        
        def collect_media(comments, post_title):
            """Helper to recursively collect media from comments."""
            nonlocal media_assets
            for c in comments:
                for media_url in c.get("media", []):
                    media_assets.append({
                        "type": "image", # Assume image for now, can be refined
                        "url": media_url,
                        "description": f"Evidence from comment by u/{c.get('author', 'N/A')} on '{post_title}'",
                        "score": c.get("score", 0),
                        "source": "Reddit Comment"
                    })
                if c.get("replies"):
                    collect_media(c["replies"], post_title)

        for item in raw_data["posts"]:
            post = item.get("post", {})
            post_title_short = post.get('title', 'Untitled')[:50]
            # Media from the main post
            for media_url in post.get("media", []):
                media_assets.append({
                    "type": "image",
                    "url": media_url,
                    "description": f"Community evidence for: {post_title_short}",
                    "score": post.get("score", 0),
                    "source": "Reddit Post"
                })
            # Media from all comments and replies
            if item.get("comments"):
                collect_media(item["comments"], post_title_short)

        log(f"   ✅ Reddit Evidence Gathered: Found {len(raw_data['posts'])} threads and {len(media_assets)} visual assets.")
        return text_context, media_assets

    except Exception as e:
        log(f"   CRITICAL Reddit Manager Error: {e}")
        return "", []
