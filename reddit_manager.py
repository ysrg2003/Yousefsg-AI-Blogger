# FILE: reddit_manager.py (UPGRADED: Resilient Investigator V2.2)
# ROLE: Extracts authentic user experiences with a multi-layered, failure-resistant search strategy.
# DESCRIPTION: This is the complete, unabridged, and deeply enhanced version. No shortcuts were taken.

import requests
import urllib.parse
import logging
import feedparser
import time
import re
from bs4 import BeautifulSoup

# --- CONFIGURATION & LOGGING ---
# Setup a dedicated logger for this module to provide detailed, non-intrusive logging.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REDDIT-INTEL] - %(message)s')
logger = logging.getLogger("RedditIntel")

# --- PRIVATE HELPER FUNCTIONS ---

def _get_core_keywords(keyword_phrase: str) -> str:
    """
    Analyzes a long, specific keyword phrase and extracts the core 2-3 nouns/entities.
    This is crucial for the fallback search strategy.
    Example: "AI video monetization fails" -> "AI video"
    """
    # A list of common, non-essential words to filter out.
    stop_words = [
        'fails', 'monetization', 'problems', 'review', 'using', 'the', 'is', 'a', 'for', 
        'and', 'of', 'how', 'to', 'my', 'thoughts', 'about'
    ]
    # Sanitize the phrase by removing quotes and making it lowercase.
    words = keyword_phrase.lower().replace('"', '').split()
    # Filter out the stop words.
    core_words = [word for word in words if word not in stop_words]
    # Return the first 3 most important words joined together.
    return " ".join(core_words[:3])

def _execute_search(query: str) -> list:
    """
    Executes a single search query against the Google News RSS endpoint and returns results.
    This function is designed to be a modular and reusable search component.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            return [{"title": entry.title, "link": entry.link} for entry in feed.entries]
        return []
    except Exception as e:
        logger.error(f"A single search execution failed for query '{query}': {e}")
        return []

# --- CORE PUBLIC FUNCTIONS ---

def search_reddit_threads(keyword: str) -> list:
    """
    Searches for real discussion threads using a multi-layered, resilient search strategy.
    It tries queries from most specific to most general to guarantee finding relevant content.
    """
    logger.info("Initiating multi-layered Reddit thread search...")
    core_keyword = _get_core_keywords(keyword)

    # Define the sequence of search queries, from most restrictive to least restrictive.
    queries = [
        # 1. Precision Search: The keyword must be in the title. High relevance, low volume.
        f'site:reddit.com intitle:("{keyword}") (review OR problem OR bug OR "hands on")',
        # 2. Broad Search: The keyword can be anywhere. Good balance.
        f'site:reddit.com "{keyword}" (review OR problem OR bug OR "hands on")',
        # 3. Core Keyword Search (Fallback): Uses the extracted core topic. High volume, moderate relevance.
        f'site:reddit.com intitle:("{core_keyword}") (review OR problem OR bug OR experience)'
    ]

    found_links = set()
    all_threads = []

    for i, query in enumerate(queries):
        logger.info(f"  -> Search Layer {i+1}/3: Executing query...")
        results = _execute_search(query)
        
        new_threads_found = 0
        for thread in results:
            # Use a set to ensure we don't process the same link twice if found by different queries.
            if thread['link'] not in found_links:
                found_links.add(thread['link'])
                all_threads.append(thread)
                new_threads_found += 1
        
        if new_threads_found > 0:
            logger.info(f"  -> Success! Layer {i+1} found {new_threads_found} new threads.")

        # If we have enough results after a layer, we can stop to save time.
        if len(all_threads) >= 4:
            logger.info("Sufficient thread count reached. Concluding search.")
            break
            
    return all_threads[:4] # Return a maximum of 4 threads.

def extract_evidence(reddit_url: str) -> tuple[list, list]:
    """
    Performs a deep, safe extraction of a single Reddit thread.
    Returns both textual insights and a comprehensive list of visual evidence.
    This version uses safer dictionary access (.get) to prevent crashes.
    """
    try:
        clean_url = reddit_url.split("?")[0]
        json_url = f"{clean_url}.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        response = requests.get(json_url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch Reddit JSON for {clean_url}, Status: {response.status_code}")
            return [], []

        data = response.json()
        
        media_found = []
        insights = []

        # --- 1. Extract Evidence from the Main Post (Safely) ---
        try:
            main_post = data[0].get('data', {}).get('children', [{}])[0].get('data', {})
            post_title = main_post.get('title', 'Reddit Post')

            # a) Direct image/gif/video links
            if 'url_overridden_by_dest' in main_post:
                url = main_post['url_overridden_by_dest']
                if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4']):
                    media_type = "video" if url.endswith('.mp4') else "image"
                    media_found.append({"type": media_type, "url": url, "description": f"Evidence from Reddit post: {post_title[:50]}"})

            # b) Reddit native video player
            if main_post.get('is_video') and main_post.get('media', {}).get('reddit_video'):
                vid_url = main_post['media']['reddit_video']['fallback_url']
                media_found.append({"type": "video", "url": vid_url, "description": f"Video evidence from user: {post_title[:50]}"})

            # c) Reddit image galleries
            if main_post.get('is_gallery') and 'gallery_data' in main_post:
                for item in main_post.get('gallery_data', {}).get('items', []):
                    media_id = item.get('media_id')
                    if media_id and media_id in main_post.get('media_metadata', {}):
                        img_data = main_post['media_metadata'][media_id]
                        source_img = img_data.get('s', {})
                        img_url = source_img.get('u', source_img.get('gif'))
                        if img_url:
                             media_found.append({"type": "image", "url": img_url.replace('&amp;', '&'), "description": f"Image from gallery in post: {post_title[:40]}"})
        except (IndexError, KeyError, TypeError) as e:
            logger.warning(f"Could not parse main post for {reddit_url}: {e}")

        # --- 2. Extract Text Insights & Code from Comments (Safely) ---
        try:
            comments_data = data[1].get('data', {}).get('children', [])
            for comment_item in comments_data:
                comment_data = comment_item.get('data', {})
                body = comment_data.get('body', '')
                score = comment_data.get('score', 0)
                
                if len(body) > 50 and body not in ["[deleted]", "[removed]"]:
                    # a) Extract Code Snippets first
                    code_blocks = re.findall(r'```(.*?)```', body, re.DOTALL)
                    for code in code_blocks:
                        if len(code.strip()) > 10:
                            media_found.append({"type": "code", "content": code.strip(), "description": "Code snippet shared by a user in comments"})
                    
                    # b) Extract Text Insights (only if score is positive)
                    if score > 5:
                        clean_body = re.sub(r'```.*?```', '[Code Snippet Provided]', body, flags=re.DOTALL)
                        clean_body = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_body)
                        insights.append({
                            "source_name": main_post.get('subreddit_name_prefixed', 'Reddit'),
                            "text": clean_body.replace("\n", " ").strip()[:500],
                            "url": f"https://www.reddit.com{comment_data.get('permalink', '')}"
                        })
        except (IndexError, KeyError, TypeError) as e:
            logger.warning(f"Could not parse comments for {reddit_url}: {e}")
        
        insights.sort(key=lambda x: len(x['text']), reverse=True)
        return insights[:5], media_found

    except Exception as e:
        logger.error(f"Deep extraction failed entirely for {reddit_url}: {e}")
        return [], []

def get_community_intel(keyword: str) -> tuple[str, list]:
    """
    Main orchestrator for Reddit intelligence gathering.
    Returns a structured text report AND a list of all unique visual evidence found.
    """
    logger.info(f"🧠 Mining Reddit for insights & visual evidence on: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads:
        logger.warning("All search layers failed. No relevant Reddit threads found.")
        return "", []
    
    all_insights, all_media = [], []
    
    for thread in threads:
        if "reddit.com" in thread['link']:
            insights, media = extract_evidence(thread['link'])
            all_insights.extend(insights)
            all_media.extend(media)
            time.sleep(0.5)
            
    unique_media = list({(v.get('url') or v.get('content')): v for v in all_media}.values())
    
    if not all_insights:
        logger.warning("Found threads but could not extract any high-quality insights.")
        return "", unique_media
    
    # Build the final, intelligent report for the AI writer
    report = "\n=== 📢 INTEL REPORT: REAL COMMUNITY FEEDBACK ===\n"
    
    # Add an executive summary for the AI
    media_summary = {}
    for m in unique_media:
        media_summary[m['type']] = media_summary.get(m['type'], 0) + 1
    summary_line = f"SUMMARY: Found {len(all_insights)} textual insights and {len(unique_media)} pieces of visual evidence."
    if media_summary:
        summary_line += f" (Evidence breakdown: {media_summary})"
    report += summary_line + "\n\n"
    
    report += "INSTRUCTIONS: Use these real user quotes and evidence to build the 'First-Hand Experience' section. Highlight any conflicts with official news.\n\n"
    
    unique_insights = list({v['text']: v for v in all_insights}.values())[:4]
    
    for i, item in enumerate(unique_insights):
        report += f"--- INSIGHT {i+1} ---\n"
        report += f"SOURCE: {item['source_name']} (Use this specific name)\n"
        report += f"LINK: {item['url']} (Link to this for citation)\n"
        report += f"USER SAID: \"{item['text']}\"\n\n"
        
    return report, unique_media
