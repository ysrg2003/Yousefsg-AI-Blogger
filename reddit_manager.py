import requests
import urllib.parse
import logging
import feedparser
import time
import re
import html

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REDDIT-INTEL] - %(message)s')
logger = logging.getLogger("RedditIntel")

# --- PRIVATE HELPER FUNCTIONS ---

def _execute_search(query: str) -> list:
    """
    ينفذ بحثاً واحداً عبر Google News RSS
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        return [{"title": entry.title, "link": entry.link} for entry in feed.entries] if feed.entries else []
    except Exception as e:
        logger.error(f"Search execution failed: {e}")
        return []

# --- CORE PUBLIC FUNCTIONS ---

def search_reddit_threads(keyword: str) -> list:
    """
    يبحث عن النقاشات باستخدام استراتيجية الطبقات (دقيق -> عام)
    """
    logger.info(f"🔍 Searching Reddit for: {keyword}")
    
    # تنظيف الكلمة المفتاحية
    clean_keyword = keyword.replace('"', '').strip()
    
    queries = [
        # الطبقة 1: بحث دقيق جداً في العناوين
        f'site:reddit.com intitle:"{clean_keyword}" (review OR problem OR "hands on" OR guide)',
        # الطبقة 2: بحث عام في العناوين
        f'site:reddit.com intitle:{clean_keyword}',
        # الطبقة 3: بحث واسع في المحتوى
        f'site:reddit.com "{clean_keyword}" (review OR solved OR code OR example)'
    ]

    all_threads = []
    seen_links = set()

    for q in queries:
        if len(all_threads) >= 4: break
        results = _execute_search(q)
        for item in results:
            if item['link'] not in seen_links:
                seen_links.add(item['link'])
                all_threads.append(item)
    
    return all_threads[:5]

def extract_evidence(reddit_url: str) -> tuple[list, list]:
    """
    يستخرج النصوص + الوسائط (صور/فيديو/أكواد) بشكل آمن وصحيح.
    """
    try:
        # 1. تصحيح رابط JSON (الخطأ كان هنا سابقاً)
        # نقوم بإزالة أي باراميترات ونضيف .json للنهاية
        base_url = reddit_url.split("?")[0].rstrip("/")
        json_url = f"{base_url}.json"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(json_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return [], []

        data = response.json()
        
        # التأكد من أن البيانات عبارة عن قائمة (هيكل Reddit الصحيح)
        if not isinstance(data, list) or len(data) < 2:
            return [], []

        media_found = []
        insights = []

        # --- تحليل المنشور الرئيسي (Main Post) ---
        main_post = data[0]['data']['children'][0]['data']
        post_title = main_post.get('title', 'Reddit Post')
        subreddit = main_post.get('subreddit_name_prefixed', 'Reddit')

        # أ) استخراج الصور المباشرة أو الروابط الخارجية
        if 'url_overridden_by_dest' in main_post:
            url = main_post['url_overridden_by_dest']
            ext = url.split('?')[0].lower()
            if any(x in ext for x in ['.jpg', '.png', '.gif', '.jpeg']):
                media_found.append({"type": "image", "url": url, "description": f"Post Image: {post_title[:50]}"})
            elif '.mp4' in ext:
                media_found.append({"type": "video", "url": url, "description": f"Post Video: {post_title[:50]}"})

        # ب) استخراج فيديو Reddit الأصلي (Hosted Video)
        if main_post.get('is_video') and main_post.get('media'):
            try:
                vid_url = main_post['media']['reddit_video']['fallback_url']
                media_found.append({"type": "video", "url": vid_url, "description": f"Reddit Video: {post_title[:50]}"})
            except: pass

        # ج) استخراج معارض الصور (Galleries) - جزء معقد تم إصلاحه
        if main_post.get('is_gallery') and main_post.get('media_metadata'):
            gallery_items = main_post.get('gallery_data', {}).get('items', [])
            for item in gallery_items:
                media_id = item['media_id']
                meta = main_post['media_metadata'].get(media_id, {})
                if 's' in meta and 'u' in meta['s']:
                    # فك تشفير الرابط (Reddit يستخدم &amp;)
                    img_url = html.unescape(meta['s']['u'])
                    media_found.append({"type": "image", "url": img_url, "description": "Gallery Image"})

        # --- تحليل التعليقات (Comments) ---
        comments_data = data[1]['data']['children']
        
        for comm in comments_data:
            c_data = comm.get('data', {})
            body = c_data.get('body', '')
            score = c_data.get('score', 0)
            permalink = c_data.get('permalink', '')
            
            if body and body not in ["[deleted]", "[removed]"]:
                
                # 1. البحث عن أكواد برمجية داخل التعليقات
                code_blocks = re.findall(r'```(.*?)```', body, re.DOTALL)
                for code in code_blocks:
                    if len(code.strip()) > 10: # تجاهل الأكواد القصيرة جداً
                        media_found.append({
                            "type": "code", 
                            "content": code.strip(), 
                            "description": "Code Snippet from comments"
                        })

                # 2. استخراج النصوص المفيدة
                # تنظيف النص من الأكواد لعدم تكرارها في التقرير النصي
                clean_body = re.sub(r'```.*?```', '[Code Block]', body, flags=re.DOTALL)
                
                if len(clean_body) > 40 and (score > 2 or any(w in clean_body.lower() for w in ['tried', 'worked', 'failed', 'bug', 'fix'])):
                    insights.append({
                        "source_name": subreddit,
                        "text": clean_body.replace("\n", " ").strip()[:600],
                        "url": f"https://www.reddit.com{permalink}",
                        "score": score
                    })

        # ترتيب النتائج حسب الأهمية (Score)
        insights.sort(key=lambda x: x['score'], reverse=True)
        return insights[:4], media_found

    except Exception as e:
        logger.error(f"Extraction error for {reddit_url}: {e}")
        return [], []

def get_community_intel(keyword: str) -> tuple[str, list]:
    """
    المحرك الرئيسي: يعيد التقرير النصي + قائمة الأدلة البصرية
    """
    logger.info(f"🚀 Starting Intel Gathering for: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads:
        return "No relevant discussions found.", []
    
    all_insights = []
    all_media = []
    
    for thread in threads:
        if "reddit.com" in thread['link']:
            ops, media = extract_evidence(thread['link'])
            all_insights.extend(ops)
            all_media.extend(media)
            time.sleep(0.5) # احتراماً لسيرفرات ريديت
            
    # إزالة التكرار من الوسائط
    unique_media = []
    seen_urls = set()
    for m in all_media:
        identifier = m.get('url') or m.get('content')[:20] # استخدام الرابط أو جزء من الكود كبصمة
        if identifier not in seen_urls:
            seen_urls.add(identifier)
            unique_media.append(m)
    
    if not all_insights:
        return "Found threads but no significant insights.", unique_media
    
    # بناء التقرير
    report = "\n=== 🛡️ COMMUNITY INTEL REPORT ===\n"
    report += f"STATS: Analyzed {len(threads)} threads, found {len(unique_media)} visual proofs (Images/Code/Video).\n\n"
    
    unique_insights = list({v['text']:v for v in all_insights}.values())[:5]
    
    for i, item in enumerate(unique_insights):
        report += f"--- OPINION {i+1} ({item['source_name']}) ---\n"
        report += f"💬 \"{item['text']}\"\n"
        report += f"🔗 Source: {item['url']}\n\n"
        
    return report, unique_media
