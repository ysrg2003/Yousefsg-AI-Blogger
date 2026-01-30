# FILE: reddit_manager.py (UPGRADED: Visual Evidence Hunter V2.0)
# ROLE: Extracts authentic user experiences, including text, images, videos, and code snippets.
# DESCRIPTION: This is the complete, unabridged, and enhanced version with no shortcuts.

import requests
import urllib.parse
import logging
import feedparser
import time
import re
from bs4 import BeautifulSoup

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REDDIT-INTEL] - %(message)s')
logger = logging.getLogger("RedditIntel")

# --- CORE FUNCTIONS ---

def search_reddit_threads(keyword):
    """
    Searches for real discussion threads (not news) using smart Google filters.
    The query is enhanced to find more problem-oriented discussions.
    """
    # Enhanced query to find more specific user experiences and problems
    search_query = f'site:reddit.com intitle:("{keyword}") (review OR problem OR bug OR crash OR slow OR experience OR "hands on" OR "my thoughts") -giveaway'
    encoded_query = urllib.parse.quote(search_query)
    
    # Using Google News RSS as a search interface for Reddit
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(url)
        threads = []
        if feed.entries:
            for entry in feed.entries[:4]:  # Limit to the top 4 most relevant threads
                threads.append({
                    "title": entry.title,
                    "link": entry.link
                })
        return threads
    except Exception as e:
        logger.error(f"Failed to search Reddit threads via Google RSS: {e}")
        return []

def extract_evidence(reddit_url):
    """
    Performs a deep extraction of a single Reddit thread.
    Returns both textual insights and a comprehensive list of visual evidence (images, videos, code).
    """
    try:
        clean_url = reddit_url.split("?")
        json_url = f"{clean_url}.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(json_url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch Reddit JSON for {clean_url}, Status: {response.status_code}")
            return [], []

        data = response.json()
        
        # --- 1. Extract Evidence from the Main Post ---
        main_post = data['data']['children']['data']
        post_title = main_post.get('title', 'Reddit Post')
        media_found = []

        # a) Direct image/gif/video links
        if 'url_overridden_by_dest' in main_post:
            url = main_post['url_overridden_by_dest']
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4']):
                media_type = "video" if url.endswith('.mp4') else "image"
                media_found.append({"type": media_type, "url": url, "description": f"Evidence from Reddit post: {post_title[:50]}"})

        # b) Reddit native video player
        if main_post.get('is_video') and main_post.get('media', {}).get('reddit_video'):
            try:
                vid_url = main_post['media']['reddit_video']['fallback_url']
                media_found.append({"type": "video", "url": vid_url, "description": f"Video evidence from user: {post_title[:50]}"})
            except (KeyError, TypeError):
                pass # Ignore if structure is unexpected

        # c) Reddit image galleries (CRITICAL ADDITION)
        if main_post.get('is_gallery') and 'gallery_data' in main_post:
            for item in main_post.get('gallery_data', {}).get('items', []):
                media_id = item.get('media_id')
                if media_id and media_id in main_post.get('media_metadata', {}):
                    try:
                        # Find the highest resolution image available
                        img_data = main_post['media_metadata'][media_id]
                        source_img = img_data['s']
                        img_url = source_img.get('u', source_img.get('gif')) # Get URL for PNG/JPG or GIF
                        if img_url:
                             media_found.append({"type": "image", "url": img_url.replace('&amp;', '&'), "description": f"Image from gallery in post: {post_title[:40]}"})
                    except (KeyError, TypeError):
                        continue

        # --- 2. Extract Text Insights & Code from Comments ---
        comments_data = data['data']['children']
        insights = []
        
        for comment_item in comments_data:
            comment_data = comment_item.get('data', {})
            body = comment_data.get('body', '')
            score = comment_data.get('score', 0)
            
            if len(body) > 50 and body not in ["[deleted]", "[removed]"]:
                
                # a) Extract Code Snippets first (CRITICAL ADDITION)
                code_blocks = re.findall(r'```(.*?)```', body, re.DOTALL)
                for code in code_blocks:
                    if len(code.strip()) > 10: # Ignore empty code blocks
                        media_found.append({"type": "code", "content": code.strip(), "description": "Code snippet shared by a user in comments"})
                
                # b) Extract Text Insights (after cleaning code)
                if score > 5: # Only consider comments with some community validation
                    # Clean the body text by removing code blocks and markdown links for clarity
                    clean_body = re.sub(r'```.*?```', '[Code Snippet Provided]', body, flags=re.DOTALL)
                    clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_body) # Markdown links -> text
                    
                    insights.append({
                        "source_name": main_post.get('subreddit_name_prefixed', 'Reddit'),
                        "text": clean_body.replace("\n", " ").strip()[:500],
                        "url": f"https://www.reddit.com{comment_data.get('permalink', '')}"
                    })
        
        # Sort insights by length to prioritize more detailed comments
        insights.sort(key=lambda x: len(x['text']), reverse=True)
        return insights[:5], media_found # Return top 5 insights and all found media

    except Exception as e:
        logger.error(f"Deep extraction failed for {reddit_url}: {e}")
        return [], []

def get_community_intel(keyword):
    """
    Main orchestrator for Reddit intelligence gathering.
    Returns a structured text report AND a list of all unique visual evidence found.
    """
    logger.info(f"🧠 Mining Reddit for insights & visual evidence on: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads:
        logger.warning("No relevant Reddit threads found.")
        return "", []
    
    all_insights = []
    all_media = []
    
    for thread in threads:
        if "reddit.com" in thread['link']:
            insights, media = extract_evidence(thread['link'])
            all_insights.extend(insights)
            all_media.extend(media)
            time.sleep(0.5) # Be respectful to Reddit's API
            
    # De-duplicate media to avoid showing the same image/video multiple times
    # This now handles code snippets correctly by using 'content' as a fallback key
    unique_media = list({(v.get('url') or v.get('content')): v for v in all_media}.values())
    
    if not all_insights:
        logger.warning("Found threads but could not extract any high-quality insights.")
        return "", unique_media
    
    # Build the final structured text report for the AI writer
    report = "\n=== 📢 REAL COMMUNITY FEEDBACK (TEXTUAL INSIGHTS) ===\n"
    report += "INSTRUCTIONS: Use these real user quotes to build the 'First-Hand Experience' section. Highlight any conflicts with official news.\n\n"
    
    # De-duplicate insights to avoid repetitive quotes
    unique_insights = list({v['text']: v for v in all_insights}.values())[:4]
    
    for i, item in enumerate(unique_insights):
        report += f"--- INSIGHT {i+1} ---\n"
        report += f"SOURCE: {item['source_name']} (Use this specific name)\n"
        report += f"LINK: {item['url']} (Link to this for citation)\n"
        report += f"USER SAID: \"{item['text']}\"\n\n"
        
    return report, unique_media
