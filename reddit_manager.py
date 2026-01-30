import requests
import urllib.parse
import logging
import feedparser
import time
import re
from bs4 import BeautifulSoup

# ==============================================================================
# CONFIGURATION & LOGGING
# ==============================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REDDIT-INTEL] - %(message)s')
logger = logging.getLogger("RedditIntel")

def search_reddit_threads(keyword):
    """
    يبحث عن نقاشات حقيقية باستخدام 3 مستويات من البحث لضمان عدم العودة بنتائج صفرية.
    """
    # المستوى 1: البحث الذكي (مشاكل تقنية محددة)
    query_v1 = f"site:reddit.com {keyword} (review OR 'problem with' OR bug OR crash OR slow OR issue) -giveaway"
    
    # المستوى 2: البحث الأصلي (تجارب عامة)
    query_v2 = f"site:reddit.com {keyword} (review OR 'after using' OR 'my thoughts' OR 'demo') -giveaway"
    
    # المستوى 3: البحث الشامل (الكلمة المفتاحية فقط داخل ريديت - بدون قيود)
    query_v3 = f"site:reddit.com {keyword}"

    search_attempts = [
        {"name": "Improved Search", "query": query_v1},
        {"name": "Original Fallback", "query": query_v2},
        {"name": "Ultra-Broad Search", "query": query_v3} # شبكة الأمان الأخيرة
    ]

    for attempt in search_attempts:
        try:
            logger.info(f"🔍 Attempting {attempt['name']}: '{attempt['query'][:60]}...'")
            encoded_query = urllib.parse.quote(attempt['query'])
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(url)
            
            if feed.entries:
                threads = []
                for entry in feed.entries[:4]:
                    threads.append({
                        "title": entry.title,
                        "link": entry.link
                    })
                logger.info(f"✅ {attempt['name']} succeeded! Found {len(threads)} threads.")
                return threads
            else:
                logger.warning(f"⚠️ {attempt['name']} returned no results.")
                
        except Exception as e:
            logger.error(f"🚨 Error during {attempt['name']}: {e}")
            continue # جرب المستوى التالي

    logger.error(f"❌ All 3 search levels failed for: {keyword}")
    return []

def extract_smart_opinions(reddit_url):
    """
    المستخرج العميق: يسحب التعليقات، الصور، الفيديوهات، المعارض، والأكواد البرمجية.
    """
    try:
        # تنظيف الرابط وتحويله إلى JSON
        clean_url = reddit_url.split("?")[0]
        json_url = f"{clean_url}.json" if not clean_url.endswith(".json") else clean_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        r = requests.get(json_url, headers=headers, timeout=15)
        if r.status_code != 200: 
            logger.warning(f"⚠️ Failed to access: {json_url} (Status: {r.status_code})")
            return [], []

        data = r.json()
        
        # 1. استخراج بيانات المنشور الرئيسي (Main Post)
        main_post = data[0]['data']['children'][0]['data']
        subreddit = main_post.get('subreddit_name_prefixed', "r/Reddit")
        post_title = main_post.get('title', 'Reddit Post')
        
        media_found = []

        # --- أ) استخراج معارض الصور (Galleries) بالكامل ---
        if main_post.get('is_gallery') and 'media_metadata' in main_post:
            for media_id, meta in main_post['media_metadata'].items():
                if meta.get('status') == 'valid' and meta.get('e') == 'Image':
                    # تحويل رابط المعاينة إلى رابط صورة مباشر
                    img_url = meta['s'].get('u', '').replace('preview.redd.it', 'i.redd.it')
                    if img_url:
                        media_found.append({
                            "type": "image",
                            "url": img_url,
                            "description": f"Gallery Evidence: {post_title[:60]}"
                        })

        # --- ب) استخراج فيديوهات Reddit المرفوعة مباشرة ---
        if main_post.get('is_video') and main_post.get('media'):
            try:
                vid_url = main_post['media']['reddit_video']['fallback_url']
                media_found.append({
                    "type": "video",
                    "url": vid_url,
                    "description": f"User Video Evidence: {post_title[:60]}"
                })
            except: pass

        # --- ج) استخراج الروابط المباشرة (URL Overridden) ---
        if 'url_overridden_by_dest' in main_post:
            dest_url = main_post['url_overridden_by_dest']
            if any(ext in dest_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4']):
                m_type = "video" if '.mp4' in dest_url.lower() else "image"
                media_found.append({
                    "type": m_type,
                    "url": dest_url,
                    "description": f"Direct Media Evidence: {post_title[:60]}"
                })

        # --- د) تحليل نص المنشور (Selftext) للبحث عن روابط مضمنة (BeautifulSoup) ---
        if 'selftext_html' in main_post and main_post['selftext_html']:
            # فك ترميز HTML وتحليله
            html_content = main_post['selftext_html']
            # Reddit يرسل HTML مرمزاً، نحتاج لفك ترميزه أحياناً
            soup = BeautifulSoup(html_content, 'html.parser')
            # البحث عن الروابط التي تشير لصور أو فيديوهات أو يوتيوب
            for a in soup.find_all('a', href=True):
                link = a['href']
                if re.search(r'\.(jpg|jpeg|png|gif|mp4)$', link.lower()):
                    m_type = "video" if '.mp4' in link.lower() else "image"
                    media_found.append({
                        "type": m_type,
                        "url": link,
                        "description": "Embedded Media Evidence"
                    })
                elif 'youtube.com/watch' in link or 'youtu.be/' in link:
                    media_found.append({
                        "type": "video",
                        "url": link,
                        "description": "Embedded YouTube Evidence"
                    })

        # 2. استخراج التعليقات (Comments) والآراء والأكواد
        comments_data = data[1]['data']['children']
        insights = []
        
        for comm in comments_data:
            c_data = comm.get('data', {})
            body = c_data.get('body', '')
            score = c_data.get('score', 0)
            author = c_data.get('author', 'User')
            
            if not body or len(body) < 50 or body in ["[deleted]", "[removed]"]:
                continue

            # --- استخراج الأكواد البرمجية (Code Blocks) ---
            # نبحث عن الكتل المحاطة بـ ```
            code_blocks = re.findall(r'```(.*?)```', body, re.DOTALL)
            for code in code_blocks:
                clean_code = code.strip()
                if len(clean_code) > 15:
                    media_found.append({
                        "type": "code",
                        "content": clean_code,
                        "description": f"Technical Evidence (Code) by {author}"
                    })
            
            # --- تنظيف النص من الأكواد قبل إرساله للـ AI ---
            # نقوم بحذف كتل الأكواد من النص ليبقى الرأي فقط
            body_cleaned = re.sub(r'```.*?```', '[Technical Code Block]', body, flags=re.DOTALL)
            body_cleaned = body_cleaned.replace("\n", " ").strip()

            # فلاتر الجودة
            markers = ["i noticed", "in my experience", "battery", "bug", "glitch", "crash", "actually", "worth it", "slow", "fast", "update", "the problem is"]
            if any(m in body_cleaned.lower() for m in markers) or score > 5:
                insights.append({
                    "source_name": subreddit,
                    "author": author,
                    "text": body_cleaned[:500], # نأخذ أول 500 حرف فقط
                    "url": f"https://www.reddit.com{c_data.get('permalink', '')}",
                    "score": score
                })
        
        # ترتيب الآراء حسب الأعلى تصويتاً
        insights.sort(key=lambda x: x['score'], reverse=True)
        return insights[:4], media_found

    except Exception as e:
        logger.error(f"❌ Extraction Error at {reddit_url}: {e}")
        return [], []

def get_community_intel(keyword):
    """
    المحرك الرئيسي: يعيد تقريراً نصياً مهيكلاً + قائمة وسائط فريدة.
    """
    logger.info(f"🧠 Starting Deep Intelligence Mining for: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads: 
        return "", []
    
    all_insights = []
    all_media = []
    
    for thread in threads:
        if "reddit.com" in thread['link']:
            ops, media = extract_smart_opinions(thread['link'])
            all_insights.extend(ops)
            all_media.extend(media)
            time.sleep(0.8) # تأخير بسيط لتجنب الحظر
            
    # --- إزالة التكرار في الوسائط (بناءً على الرابط أو محتوى الكود) ---
    unique_media_map = {}
    for item in all_media:
        # إذا كان كود، نستخدم المحتوى كمفتاح، وإذا كان ميديا نستخدم الرابط
        key = item.get('url') if item['type'] != 'code' else item.get('content')
        if key and key not in unique_evidence_map:
            unique_media_map[key] = item
    
    unique_media = list(unique_media_map.values())
    
    if not all_insights and not unique_media:
        return "", []
    
    # --- بناء التقرير النصي المهيكل للـ AI ---
    report = "\n=== 📢 REAL COMMUNITY FEEDBACK (TEXTUAL INSIGHTS) ===\n"
    report += "INSTRUCTIONS FOR AI WRITER: Use these real user quotes to add credibility, highlight bugs, or contrast marketing claims.\n"
    report += "CRITICAL: You MUST hyperlink the Subreddit name or the phrase 'community discussion' to the provided URL.\n\n"
    
    # إزالة تكرار النصوص
    seen_texts = set()
    final_insights = []
    for ins in all_insights:
        if ins['text'] not in seen_texts:
            final_insights.append(ins)
            seen_texts.add(ins['text'])
    
    for i, item in enumerate(final_insights[:4]):
        report += f"--- INSIGHT {i+1} ---\n"
        report += f"SOURCE: {item['source_name']}\n"
        report += f"LINK: {item['url']}\n"
        report += f"USER EXPERIENCE: \"{item['text']}\"\n"
        report += f"COMMUNITY SCORE: {item['score']} upvotes\n\n"

    # إضافة ملخص الأدلة البصرية للتقرير ليعرف الـ AI بوجودها
    if unique_media:
        report += "=== 🖼️ AVAILABLE VISUAL/TECHNICAL EVIDENCE ===\n"
        report += "INSTRUCTIONS: I have extracted the following evidence. Use the placeholders [[EVIDENCE_TYPE_ID]] in your draft where appropriate.\n"
        for i, m in enumerate(unique_media):
            report += f"- Evidence {i+1}: Type={m['type']}, Description={m['description']}\n"

    return report, unique_media
