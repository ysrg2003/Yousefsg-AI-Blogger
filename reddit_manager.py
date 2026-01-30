import requests
import urllib.parse
import logging
import feedparser
import time
import re

# إعداد اللوجر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REDDIT-INTEL] - %(message)s')
logger = logging.getLogger("RedditIntel")

def search_reddit_threads(keyword):
    """
    يبحث عن نقاشات حقيقية (ليست أخباراً) باستخدام فلاتر جوجل الذكية.
    """
    search_query = f"site:reddit.com {keyword} (review OR 'after using' OR 'problem with' OR 'my thoughts' OR 'demo') -giveaway"
    encoded = urllib.parse.quote(search_query)
    
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(url)
        threads = []
        if feed.entries:
            for entry in feed.entries[:4]: 
                threads.append({
                    "title": entry.title,
                    "link": entry.link
                })
        return threads
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def extract_smart_opinions(reddit_url):
    """
    يسحب التعليقات + الوسائط البصرية (فيديو/GIF) من المنشور.
    """
    try:
        clean_url = reddit_url.split("?")[0]
        json_url = f"{clean_url}.json" if not clean_url.endswith(".json") else clean_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'
        }
        
        r = requests.get(json_url, headers=headers, timeout=10)
        if r.status_code != 200: return [], []

        data = r.json()
        
        # 1. استخراج بيانات المنشور الرئيسي (للبحث عن الوسائط)
        main_post = data[0]['data']['children'][0]['data']
        subreddit = main_post.get('subreddit_name_prefixed', "Reddit")
        post_title = main_post.get('title', 'Reddit Post')
        
        media_found = []

        # أ) البحث عن روابط مباشرة (صور/GIFs)
        if 'url_overridden_by_dest' in main_post:
            url = main_post['url_overridden_by_dest']
            if any(ext in url.lower() for ext in ['.jpg', '.png', '.gif', '.mp4']):
                m_type = "video" if url.endswith('.mp4') else "gif" if url.endswith('.gif') else "image"
                media_found.append({
                    "type": m_type,
                    "url": url,
                    "description": f"Community Demo: {post_title[:60]}"
                })

        # ب) البحث عن فيديوهات Reddit المرفوعة مباشرة
        if main_post.get('is_video') and main_post.get('media'):
            try:
                vid_url = main_post['media']['reddit_video']['fallback_url']
                media_found.append({
                    "type": "video",
                    "url": vid_url,
                    "description": f"User Video Review: {post_title[:60]}"
                })
            except: pass

        # 2. استخراج التعليقات (النصوص)
        comments_data = data[1]['data']['children']
        insights = []
        
        for comm in comments_data:
            c_data = comm.get('data', {})
            body = c_data.get('body', '')
            score = c_data.get('score', 0)
            
            if len(body) > 60 and body not in ["[deleted]", "[removed]"]:
                markers = ["i noticed", "in my experience", "battery", "bug", "glitch", "crash", "actually", "worth it", "slow", "fast", "update"]
                if any(m in body.lower() for m in markers) or score > 5:
                    insights.append({
                        "source_name": subreddit,
                        "author": c_data.get('author', 'User'),
                        "text": body[:500].replace("\n", " "),
                        "url": f"https://www.reddit.com{c_data.get('permalink', '')}",
                        "score": score
                    })
        
        insights.sort(key=lambda x: x['score'], reverse=True)
        return insights[:3], media_found # نعيد (التعليقات، الوسائط)

    except Exception as e:
        return [], []

def get_community_intel(keyword):
    """
    المحرك الرئيسي: يعيد تقريراً نصياً + قائمة بالوسائط البصرية.
    """
    logger.info(f"🧠 Mining Reddit intelligence & visuals for: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads: return "", []
    
    all_insights = []
    all_media = [] # قائمة جديدة لتجميع الوسائط
    
    for thread in threads:
        if "reddit.com" in thread['link']:
            ops, media = extract_smart_opinions(thread['link'])
            all_insights.extend(ops)
            all_media.extend(media) # إضافة الوسائط المكتشفة
            time.sleep(0.5)
            
    # إزالة الوسائط المكررة
    unique_media = list({v['url']:v for v in all_media}.values())
    
    if not all_insights: return "", unique_media
    
    # بناء التقرير النصي
    report = "\n=== 📢 REAL COMMUNITY FEEDBACK (INTEGRATE THIS) ===\n"
    report += "INSTRUCTIONS: Use these real user quotes to validate or criticize the news. \n"
    report += "CRITICAL: When citing, you MUST hyperlink the text 'community discussion' or the Subreddit name (e.g., r/Gadgets) to the provided URL.\n\n"
    
    unique_insights = list({v['text']:v for v in all_insights}.values())[:4]
    
    for i, item in enumerate(unique_insights):
        report += f"--- INSIGHT {i+1} ---\n"
        report += f"SOURCE: {item['source_name']} (Use this specific name)\n"
        report += f"LINK: {item['url']} (Link strictly to this)\n"
        report += f"USER SAID: \"{item['text']}\"\n"
        
    # نعيد التقرير النصي + قائمة الوسائط
    return report, unique_media
