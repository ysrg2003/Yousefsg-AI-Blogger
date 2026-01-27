import time
import random
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import trafilatura
from bs4 import BeautifulSoup
from config import log, USER_AGENTS

# ==============================================================================
# 1. CONFIGURATION & BLACKLISTS
# ==============================================================================

# قائمة استبعاد للمواقع الإخبارية (نحن نريد المصدر الرسمي فقط عند البحث عن الوسائط)
NEWS_DOMAINS_BLACKLIST = [
    "techcrunch", "theverge", "engadget", "wired", "cnet", "forbes", 
    "businessinsider", "nytimes", "wsj", "bloomberg", "reuters", "cnn",
    "bbc", "medium", "reddit", "youtube", "wikipedia", "latestai", "techradar"
]

# ==============================================================================
# 2. HELPER FUNCTIONS (SMART CONTEXT)
# ==============================================================================

def get_smart_query_by_category(keyword, category):
    """
    توليد استعلام بحث ذكي بناءً على الفئة للعثور على 'الصفحة العميقة' الصحيحة.
    """
    base = f"{keyword} official"
    
    if "Video" in category or "Media" in category:
        return f"{base} demo showcase video"
    elif "Code" in category or "Dev" in category or "Tools" in category:
        return f"{base} documentation features blog"
    elif "Robotics" in category or "Hardware" in category:
        return f"{base} reveal video demonstration"
    elif "Business" in category or "Income" in category:
        return f"{base} pricing case study press release"
    else:
        return f"{base} announcement blog"

def is_official_looking_url(url, keyword):
    """
    تحقق ذكي: هل هذا الرابط يبدو كمصدر رسمي؟
    """
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        # استبعاد مواقع الأخبار المعروفة
        if any(news in domain for news in NEWS_DOMAINS_BLACKLIST):
            return False
        return True
    except: return False

def extract_element_context(element):
    """
    يستخرج وصفاً نصياً للوسيط (صورة/فيديو) لمساعدة الذكاء الاصطناعي في الاختيار.
    """
    context = []
    
    # 1. النص البديل والعناوين
    if element.get('alt'): context.append(element['alt'])
    if element.get('title'): context.append(element['title'])
    if element.get('aria-label'): context.append(element['aria-label'])
    
    # 2. النص المحيط (الأب أو الأخ السابق)
    parent = element.parent
    if parent:
        text = parent.get_text(strip=True)[:150] # أول 150 حرف من النص المحيط
        if text: context.append(text)
        
    return " | ".join(context) if context else "No description available"

# ==============================================================================
# 3. CORE FUNCTION: SMART MEDIA HUNT (THE VISUAL DETECTIVE)
# ==============================================================================

def smart_media_hunt(target_keyword, category):
    """
    المحرك الذكي: يبحث عن الصفحة الدقيقة ويسحب الوسائط المناسبة للفئة مع السياق.
    """
    search_query = get_smart_query_by_category(target_keyword, category)
    log(f"      🕵️‍♂️ Smart Sniper: Hunting for official media using query: '{search_query}'...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    # ملاحظة: هنا لا نحظر الصور تماماً لأننا نريد التأكد من وجودها في DOM، 
    # لكننا نعتمد على السرعة.
    
    driver = None
    found_media = []
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        
        # 1. البحث في جوجل
        driver.get(f"https://www.google.com/search?q={urllib.parse.quote(search_query)}")
        time.sleep(2)
        
        # 2. اختيار الرابط "العميق" المناسب
        links = driver.find_elements(By.CSS_SELECTOR, 'div.g a')
        target_url = None
        
        for link in links[:6]: # نفحص أول 6 نتائج
            url = link.get_attribute('href')
            if url and is_official_looking_url(url, target_keyword):
                target_url = url
                break
        
        if not target_url:
            log("      ⚠️ No official-looking source found via Smart Hunt.")
            return []

        log(f"      🎯 Locked on Target: {target_url}")
        driver.get(target_url)
        time.sleep(5) # انتظار تحميل المحتوى الديناميكي (JS)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # قوائم الإشارات
        positive_signals = ["demo", "showcase", "tutorial", "interface", "example", "generated", "result", "how to", "workflow", "reveal", "trailer"]
        negative_signals = ["logo", "icon", "background", "hero", "banner", "loader", "spinner", "team", "hiring", "avatar", "profile", "footer"]

        # 3. استخراج الوسائط بذكاء
        
        # أ) البحث عن فيديوهات (MP4/WebM)
        for video in soup.find_all('video'):
            src = video.get('src')
            if not src:
                src = video.find('source', src=True)
                if src: src = src['src']
            
            if src and (src.endswith('.mp4') or src.endswith('.webm')):
                if src.startswith('/'): src = urllib.parse.urljoin(target_url, src)
                
                context = extract_element_context(video).lower()
                if any(bad in context or bad in src for bad in negative_signals): continue
                
                found_media.append({
                    "type": "video", 
                    "url": src, 
                    "description": context,
                    "score": sum(1 for sig in positive_signals if sig in context) + 2 # Video gets bonus score
                })

        # ب) البحث عن YouTube/Vimeo Embeds
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube.com/embed' in src or 'player.vimeo.com' in src:
                context = extract_element_context(iframe).lower()
                found_media.append({
                    "type": "embed", 
                    "url": src, 
                    "description": context,
                    "score": sum(1 for sig in positive_signals if sig in context) + 1
                })

        # ج) البحث عن GIFs (للأدوات والشروحات)
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src.endswith('.gif'):
                if src.startswith('/'): src = urllib.parse.urljoin(target_url, src)
                
                context = extract_element_context(img).lower()
                if any(bad in context or bad in src for bad in negative_signals): continue
                if "loading" in src or "pixel" in src: continue

                found_media.append({
                    "type": "gif", 
                    "url": src, 
                    "description": context,
                    "score": sum(1 for sig in positive_signals if sig in context)
                })
                    
        # د) البحث عن صور عالية الجودة (فقط للروبوتات والهاردوير)
        if "Robotics" in category or "Hardware" in category:
            for img in soup.find_all('img', src=True):
                src = img['src']
                # نبحث عن صور كبيرة أو Hero Images
                if 'hero' in str(img.get('class', '')) or 'banner' in str(img.get('class', '')):
                     if src.startswith('/'): src = urllib.parse.urljoin(target_url, src)
                     found_media.append({"type": "image", "url": src, "description": "Hero Product Shot", "score": 1})

    except Exception as e:
        log(f"      ⚠️ Smart Hunt Error: {e}")
    finally:
        if driver: 
            try: driver.quit()
            except: pass
        
    # ترتيب النتائج حسب النقاط (Score)
    found_media.sort(key=lambda x: x['score'], reverse=True)
    
    # إزالة التكرار
    unique_media = list({v['url']:v for v in found_media}.values())
    
    log(f"      📸 Extracted {len(unique_media)} context-verified assets from official source.")
    return unique_media[:3] # نكتفي بأفضل 3

# ==============================================================================
# 4. EXISTING FUNCTION: NEWS SCRAPER (FOR TEXT)
# ==============================================================================

def resolve_and_scrape(google_url):
    log(f"      🕵️‍♂️ Selenium: Resolving Link & Hunting Image...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    chrome_options.add_argument("--mute-audio") 

    # Optimization: Block images/css for text scraping speed
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.popups": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90) 
        
        driver.get(google_url)
        
        start_wait = time.time()
        final_url = google_url
        while time.time() - start_wait < 15: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1) 
        
        final_title = driver.title
        page_source = driver.page_source
        
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None, None

        soup = BeautifulSoup(page_source, 'html.parser')
        og_image = None
        try:
            meta_img = soup.find('meta', property='og:image')
            if meta_img: og_image = meta_img.get('content')
            if not og_image:
                meta_img = soup.find('meta', name='twitter:image')
                if meta_img: og_image = meta_img.get('content')
        except: pass

        extracted_text = trafilatura.extract(
            page_source, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True
        )
        
        if extracted_text and len(extracted_text) > 800:
            return final_url, final_title, extracted_text, og_image

        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        
        if fallback_text and len(fallback_text) > 800:
            return final_url, final_title, fallback_text, og_image
            
        return None, None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {str(e)[:100]}")
        return None, None, None, None
    finally:
        if driver:
            try: driver.quit()
            except: pass
