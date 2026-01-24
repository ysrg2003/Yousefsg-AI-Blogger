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
    # البحث عن كلمات تدل على تجربة حقيقية
    # نستخدم -giveaway لاستبعاد المسابقات
    search_query = f"site:reddit.com {keyword} (review OR 'after using' OR 'problem with' OR 'my thoughts') -giveaway"
    encoded = urllib.parse.quote(search_query)
    
    # نستخدم بحث جوجل العام بصيغة RSS لأنه أدق وأسرع من API ريديت ولا يحتاج مفاتيح
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(url)
        threads = []
        if feed.entries:
            for entry in feed.entries[:4]: 
                # تنظيف الرابط
                real_link = entry.link
                threads.append({
                    "title": entry.title,
                    "link": real_link
                })
        return threads
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def extract_smart_opinions(reddit_url):
    """
    يسحب التعليقات ويحلل محتواها لاستخراج 'الذهب' فقط (JSON Trick).
    """
    try:
        clean_url = reddit_url.split("?")[0]
        if not clean_url.endswith(".json"):
            json_url = f"{clean_url}.json"
        else:
            json_url = clean_url

        # User-Agent ضروري جداً لتجنب خطأ 429
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'
        }
        
        r = requests.get(json_url, headers=headers, timeout=10)
        if r.status_code != 200: return []

        data = r.json()
        
        # محاولة استخراج اسم المجتمع (Subreddit) لإعطاء مصداقية
        try:
            subreddit = data[0]['data']['children'][0]['data']['subreddit_name_prefixed'] # ex: r/Android
        except:
            subreddit = "Reddit Discussion"

        comments_data = data[1]['data']['children']
        insights = []
        
        for comm in comments_data:
            c_data = comm.get('data', {})
            body = c_data.get('body', '')
            score = c_data.get('score', 0)
            permalink = c_data.get('permalink', '')
            author = c_data.get('author', 'User')
            
            # فلتر الجودة:
            # 1. الطول مناسب (ليس كلمة واحدة وليس مقالاً طويلاً جداً)
            # 2. يحتوي على كلمات تدل على التجربة
            if len(body) > 60 and body not in ["[deleted]", "[removed]"]:
                markers = ["i noticed", "in my experience", "battery", "bug", "glitch", "crash", "actually", "worth it", "slow", "fast", "update"]
                if any(m in body.lower() for m in markers) or score > 5:
                    
                    # بناء رابط دقيق للتعليق نفسه
                    full_link = f"https://www.reddit.com{permalink}"
                    
                    insights.append({
                        "source_name": subreddit,
                        "author": author,
                        "text": body[:500].replace("\n", " "), # تنظيف
                        "url": full_link,
                        "score": score
                    })
        
        # نرتب حسب الأهمية (Score)
        insights.sort(key=lambda x: x['score'], reverse=True)
        return insights[:3] # نأخذ أفضل 3 من كل خيط

    except Exception as e:
        # logger.error(f"Extraction error: {e}")
        return []

def get_community_intel(keyword):
    """
    المحرك الرئيسي: يعيد تقريراً نصياً مهيكلاً للـ AI
    """
    logger.info(f"🧠 Mining Reddit intelligence for: '{keyword}'...")
    threads = search_reddit_threads(keyword)
    
    if not threads: return ""
    
    all_insights = []
    for thread in threads:
        if "reddit.com" in thread['link']:
            ops = extract_smart_opinions(thread['link'])
            all_insights.extend(ops)
            time.sleep(0.5)
            
    if not all_insights: return ""
    
    # تنسيق البيانات بشكل صارم للـ Prompt
    # هذا التنسيق يجبر الـ AI على فهم الرابط والمصدر
    report = "\n=== 📢 REAL COMMUNITY FEEDBACK (INTEGRATE THIS) ===\n"
    report += "INSTRUCTIONS: Use these real user quotes to validate or criticize the news. \n"
    report += "CRITICAL: When citing, you MUST hyperlink the text 'community discussion' or the Subreddit name (e.g., r/Gadgets) to the provided URL.\n\n"
    
    # نختار أفضل 4 آراء متنوعة وفريدة
    unique_insights = list({v['text']:v for v in all_insights}.values())[:4]
    
    for i, item in enumerate(unique_insights):
        report += f"--- INSIGHT {i+1} ---\n"
        report += f"SOURCE: {item['source_name']} (Use this specific name)\n"
        report += f"LINK: {item['url']} (Link strictly to this)\n"
        report += f"USER SAID: \"{item['text']}\"\n"
        
    return report
