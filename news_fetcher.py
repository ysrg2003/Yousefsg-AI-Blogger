import requests
import urllib.parse
import feedparser
import random
import datetime
import os
import json
from config import log
from api_manager import generate_step_strict

# ==============================================================================
# 1. SMART REPUTATION SYSTEM (MEMORY)
# ==============================================================================

REPUTATION_FILE = "source_reputation.json"

# قائمة طوارئ للمواقع السيئة جداً (لتعليم الـ AI ماذا يكره)
SEED_BLACKLIST = [
    "vocal.media", "aol.com", "msn.com", "yahoo.com", "marketwatch.com", 
    "indiacsr.in", "officechai.com", "analyticsinsight.net", "prweb.com",
    "businesswire.com", "globenewswire.com", "medium.com", "linkedin.com",
    "quora.com", "reddit.com", "youtube.com" # نستبعد يوتيوب من الأخبار النصية
]

def get_domain_reputation():
    """تحميل ذاكرة المواقع (الجيدة والسيئة)."""
    default_rep = {"blacklist": SEED_BLACKLIST, "whitelist": []}
    if os.path.exists(REPUTATION_FILE):
        try:
            with open(REPUTATION_FILE, 'r') as f:
                data = json.load(f)
                # دمج القائمة الأولية مع المحفوظة لضمان الحماية
                data['blacklist'] = list(set(data.get('blacklist', []) + SEED_BLACKLIST))
                return data
        except: return default_rep
    return default_rep

def save_domain_reputation(data):
    """حفظ تحديثات الذاكرة."""
    try:
        with open(REPUTATION_FILE, 'w') as f: json.dump(data, f, indent=2)
    except: pass

def ai_vet_sources(items, model_name):
    """
    يقوم الـ AI بفحص الدومينات الجديدة وتصنيفها (صحافة حقيقية vs حشو).
    """
    reputation = get_domain_reputation()
    
    # استخراج الدومين من كل رابط
    item_domains = {}
    for item in items:
        try:
            domain = urllib.parse.urlparse(item['link']).netloc.replace('www.', '').lower()
            if domain not in item_domains: item_domains[domain] = []
            item_domains[domain].append(item)
        except: continue

    unique_domains = list(item_domains.keys())
    
    # تصفية ما هو معروف مسبقاً
    unknown_domains = [d for d in unique_domains if d not in reputation['blacklist'] and d not in reputation['whitelist']]
    
    # إذا كانت هناك دومينات جديدة، نسأل الـ AI
    if unknown_domains:
        log(f"   🕵️‍♂️ AI Auditor: Vetting {len(unknown_domains)} new domains...")
        
        prompt = f"""
        ROLE: Senior Tech Editor & Media Auditor.
        TASK: Evaluate these websites for credibility in covering AI & Tech news.
        
        CANDIDATE DOMAINS: {unknown_domains}
        
        CRITERIA FOR BLACKLIST (Reject):
        - User-Generated Content / Open Publishing (e.g., Vocal, Medium, LinkedIn).
        - Press Release Aggregators (PRWeb, BusinessWire).
        - General News Aggregators with low original tech reporting (MSN, AOL, Yahoo).
        - SEO Farms or Low-Quality Blogs.
        
        CRITERIA FOR WHITELIST (Accept):
        - Dedicated Tech Publications (The Verge, TechCrunch, Wired, Ars Technica).
        - Official Company Blogs (OpenAI, Google Blog, Microsoft).
        - Reputable News Outlets with Tech Desks (Reuters, Bloomberg, NYT).
        - Niche High-Quality AI Blogs.

        OUTPUT JSON ONLY:
        {{
          "blacklist": ["bad-site1.com", "spam-site2.com"],
          "whitelist": ["good-site1.com"]
        }}
        """
        try:
            decision = generate_step_strict(model_name, prompt, "Source Vetting")
            
            # تحديث القوائم
            new_black = decision.get('blacklist', [])
            new_white = decision.get('whitelist', [])
            
            if new_black: log(f"      ⛔ AI Blocked: {new_black}")
            if new_white: log(f"      ✅ AI Approved: {new_white}")

            reputation['blacklist'].extend(new_black)
            reputation['whitelist'].extend(new_white)
            
            # حفظ الذاكرة
            reputation['blacklist'] = list(set(reputation['blacklist']))
            reputation['whitelist'] = list(set(reputation['whitelist']))
            save_domain_reputation(reputation)
            
        except Exception as e:
            log(f"      ⚠️ Vetting skipped (Error). Assuming safe for now.")

    # التصفية النهائية
    approved_items = []
    reputation = get_domain_reputation() # إعادة تحميل للتأكد
    
    for domain, domain_items in item_domains.items():
        if domain in reputation['blacklist']:
            continue # تخطي هذا الدومين
        approved_items.extend(domain_items)
        
    return approved_items

# ==============================================================================
# 2. STANDARD FETCHERS (UPDATED TO USE NEGATIVE SEARCH)
# ==============================================================================

def get_gnews_api_sources(query, category):
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key: return []
    
    # تنظيف الاستعلام
    clean_query = query.replace(" when:2d", "").replace(" when:1d", "")
    
    # إضافة فلتر سلبي للمواقع السيئة المعروفة لتقليل الضوضاء قبل وصولها للـ AI
    # هذا يوفر الـ Quota
    hard_filters = " ".join([f"-site:{site}" for site in SEED_BLACKLIST[:5]]) # نستخدم أهم 5 فقط هنا لطول الرابط
    final_query = f"{clean_query} {hard_filters}"

    log(f"   📡 Querying GNews API for: '{clean_query}'...")
    url = f"https://gnews.io/api/v4/search?q={urllib.parse.quote(final_query)}&lang=en&country=us&max=5&apikey={api_key}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200 or 'articles' not in data: return []
        formatted = []
        for art in data.get('articles', []):
            formatted.append({
                "title": art.get('title'),
                "link": art.get('url'),
                "date": art.get('publishedAt', str(datetime.date.today())),
                "image": art.get('image')
            })
        return formatted
    except: return []

def get_real_news_rss(query_keywords, category=None):
    try:
        # تنظيف الاستعلام من التعقيدات الزائدة لزيادة فرص العثور على نتائج
        base_query = query_keywords.replace('"', '').strip()
        
        # إزالة when:2d إذا كانت تسبب مشاكل، أو تركها إذا كنت مصراً عليها
        # سنقوم بترميزها بشكل آمن
        if "when:" not in base_query:
            full_query = f"{base_query} when:7d" # وسعنا النطاق لـ 7 أيام لضمان النتائج
        else:
            full_query = base_query

        log(f"   📰 Querying Google News RSS for: '{full_query}'...")
        encoded = urllib.parse.quote(full_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        
        if feed.entries:
            for entry in feed.entries[:10]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        
        # --- التغيير الجذري هنا ---
        # ألغينا البحث العام عن القسم (Category Fallback)
        # لكي نسمح لـ GNews API بالعمل في main.py
            log(f"   ⚠️ RSS Empty for '{base_query}'. Returning empty list to trigger GNews.")
            return [] 
            
            except Exception as e:
                log(f"❌ RSS Error: {e}")
                return []
        
        elif category:
            log(f"   ⚠️ RSS Empty. Fallback to Category: {category}")
            fb = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fb)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({"title": entry.title, "link": entry.link, "date": "Today"})
            return items
            
        return []
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []
