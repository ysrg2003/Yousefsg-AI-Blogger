# FILE: scraper.py
# ROLE: Advanced Web Scraper & Visual Hunter (Scroll & Capture Edition).
# FEATURES: AI-Guided Media Hunt, Selenium Fallback, Smart Anti-Detection, Lazy-Load Scrolling.

import re
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

# Domains to avoid for visual hunting (Low quality or paywalled)
NEWS_DOMAINS_BLACKLIST = [
    "techcrunch", "theverge", "engadget", "wired", "cnet", "forbes", 
    "businessinsider", "nytimes", "wsj", "bloomberg", "reuters", "cnn",
    "bbc", "medium", "reddit", "wikipedia", "latestai", "techradar",
    "vocal.media", "aol.com", "msn.com", "yahoo.com", "marketwatch.com", 
    "indiacsr.in", "officechai.com"
]

# Technical links that should never be considered media
MEDIA_LINK_BLACKLIST = [
    "googletagmanager", "google-analytics", "doubleclick", "pixel", 
    "adsystem", "adnxs", "script", "tracker", "analytics", "fb.com/tr",
    "1x1", "spacer", "blank", "tracking", "icon", "logo", "avatar", "profile",
    "footer", "header", "button"
]

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================

def get_smart_query_by_category(keyword, category, directive, content_type):
    """
    Generates specific queries based on the visual directive AND the content type.
    """
    base = f"{keyword}"
    
    # --- المنطق الموحد والأقوى: طلب صور سياقية عالية الصلة ---
    if content_type in ["Guide", "Review"] or directive == "hunt_for_screenshot":
        # هذا هو الطلب الأقوى والوحيد الذي نحتاجه الآن
        return f'{base} "UI screenshot" "step-by-step" "workflow diagram" "configuration panel" guide'
        
    # --- المنطق القديم للفيديو (للحفاظ على التغطية إن لم يتم تفعيل المنطق أعلاه) ---
    if directive == "hunt_for_video":
        if "Robotics" in category or "Hardware" in category:
            return f"{base} official reveal video demonstration"
        return f"{base} official demo walkthrough"
    
    # المنطق الافتراضي
    return f"{base} official visual evidence"

def is_official_looking_url(url, keyword):
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if any(news in domain for news in NEWS_DOMAINS_BLACKLIST): return False
        # Simple heuristic: shorter domains often main product sites
        return True
    except: return False

def extract_element_context(element):
    """Extracts text context around an image/video to validate relevance."""
    context = []
    for attr in ['alt', 'title', 'aria-label']:
        if element.get(attr): context.append(element[attr])
    parent = element.parent
    if parent:
        text = parent.get_text(strip=True)[:150]
        if text: context.append(text)
    return " | ".join(context) if context else "No description available"

def scroll_page(driver):
    """
    Scrolls down the page slowly to trigger lazy-loaded images.
    """
    log("      📜 Scrolling down to trigger lazy-loading...")
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        # نقسم الصفحة إلى 4 أجزاء وننزل تدريجياً
        for i in range(1, 5):
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {i/4});")
            time.sleep(1.5) # انتظار تحميل الصور
            
        # العودة للأعلى قليلاً لضمان الثبات
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception as e:
        log(f"      ⚠️ Scroll failed: {e}")

def extract_assets_from_soup(soup, base_url):
    """
    Extracts images AND code snippets with their surrounding text context.
    """
    assets = []
    positive_signals = ["demo", "step", "showcase", "tutorial", "interface", "dashboard", "generated", "result", "how to", "workflow", "reveal", "trailer", "robot", "prototype", "screenshot", "UI"]
    negative_signals = ["logo", "icon", "background", "banner", "loader", "spinner", "avatar", "profile", "footer", "ad", "advertisement", "promo", "pixel", "tracker"]
    
    # A. EXTRACT IMAGES
    for img in soup.find_all('img', src=True):
        src = img['src']
        if not src: continue
        
        # Resolve relative URLs
        if src.startswith('//'): src = 'https:' + src
        elif src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        elif not src.startswith('http'): continue
        
        # Blacklist Filtering
        if any(bad in src.lower() for bad in MEDIA_LINK_BLACKLIST): continue
        if src.endswith('.svg') or src.endswith('.ico'): continue
        
        # Context Extraction
        context = extract_element_context(img).lower()
        if any(bad in context or bad in src.lower() for bad in negative_signals): continue

        # Size Filtering (Skip small icons/trackers)
        try:
            if 'width' in img.attrs and int(img['width']) < 300: continue
            if 'height' in img.attrs and int(img['height']) < 200: continue
        except: pass
        
        # Score calculation
        score = sum(1 for sig in positive_signals if sig in context)
        
        # فقط الصور التي لها سياق مفيد أو درجة عالية
        if len(context) > 10 or score > 0: 
            assets.append({
                "type": "image",
                "url": src,
                "description": context[:300], # نختصر الوصف
                "source_url": base_url,
                "score": score
            })

    # B. EXTRACT CODE SNIPPETS
    for code_block in soup.find_all(['pre', 'code']):
        code_text = code_block.get_text(strip=True)
        # تجاهل الأكواد القصيرة جداً (كلمة واحدة) أو الطويلة جداً
        if len(code_text) < 50 or len(code_text) > 3000: continue
        
        # نحاول معرفة اللغة
        lang_class = code_block.get('class', [])
        language = "code"
        if isinstance(lang_class, list):
            for c in lang_class:
                if 'py' in c or 'python' in c: language = "python"
                elif 'js' in c or 'javascript' in c: language = "javascript"
                elif 'bash' in c or 'shell' in c: language = "bash"
                elif 'html' in c: language = "html"
                elif 'css' in c: language = "css"
        
        assets.append({
            "type": "code",
            "content": code_text,
            "language": language,
            "description": f"Code snippet from {base_url}",
            "source_url": base_url,
            "score": 5 # Base score for code
        })
        
    return assets

# ==============================================================================
# 3. THE SMART HUNTER (AI + SELENIUM)
# ==============================================================================

def smart_media_hunt(target_keyword, category, directive, content_type="Review"):
    """
    Hybrid Hunt:
    1. Uses AI Researcher to find direct visual links (Fast/Smart).
    2. Falls back to Selenium Sniper (Google Images Direct) if AI fails.
    """
    log(f"      🎯 Sniper Hunt: Searching for Visual Proofs ('{directive}')...")
    
    all_media = []

    # --- STRATEGY A: AI RESEARCHER (The Smart Way - Now requests 15 sources) ---
    try:
        import ai_researcher
        # Ask AI to find specific visual evidence
        ai_visuals = ai_researcher.smart_hunt(target_keyword, {}, mode="visual")
        
        if ai_visuals:
            log(f"         ✨ AI found {len(ai_visuals)} candidate visuals.")
            for item in ai_visuals:
                url = item.get('url') or item.get('link')
                if not url: continue
                
                # Determine type
                m_type = "image"
                if "youtube" in url or "vimeo" in url: m_type = "embed"
                elif url.endswith(".mp4") or url.endswith(".webm"): m_type = "video"
                
                all_media.append({
                    "type": m_type,
                    "url": url,
                    "description": item.get('description', f"Visual evidence for {target_keyword}"),
                    "score": 10 # High trust for AI results
                })
    except Exception as e:
        log(f"         ⚠️ AI Visual Hunt failed: {e}")

    # If AI satisfied the hunt, return early (رفع الحد الأدنى إلى 5)
    if len(all_media) >= 5: 
        log(f"         ✅ Enough high-quality media found via AI. Skipping Selenium.")
        # نُزيل الروابط المكررة قبل الإرسال
        unique_media = list({m['url']: m for m in all_media}.values())
        return unique_media

    # --- STRATEGY B: SELENIUM SNIPER (Google Images Direct - The Robust Fallback) ---
    log("         🕵️‍♂️ Switching to Selenium Sniper (Google Images Direct) for deep visual search...")
    search_query = get_smart_query_by_category(target_keyword, category, directive, content_type)
    
    chrome_options = Options()
    chrome_options.page_load_strategy = 'eager'
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(45)
        
        # Search Google Images Directly (tbm=isch)
        driver.get(f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(search_query)}")
        time.sleep(3)
        
        # نمرر لأسفل الصفحة لتحميل المزيد من الصور (Deep Search)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2) 
        
        # نجمع كل الروابط الصغيرة للصور المصغرة التي يمكن أن نستخدمها كمرشح
        image_elements = driver.find_elements(By.CSS_SELECTOR, 'img.Q4LuWd')
        
        log(f"         📸 Sniper found {len(image_elements)} candidate thumbnails.")
        
        # نأخذ أول 10 عناصر ونحلل الروابط الأصلية المخفية بها
        for i, img_el in enumerate(image_elements[:10]):
            try:
                # الروابط الأصلية تكون غالباً في عنصر الأب (a) أو مخفية في (data-src)
                url = img_el.get_attribute('src') or img_el.get_attribute('data-src')

                if url and url.startswith("http"):
                    # نفلتر الروابط القصيرة جداً
                    if len(url) < 50: continue 
                    all_media.append({
                        "type": "image", 
                        "url": url, 
                        "description": img_el.get_attribute('alt') or f"Google Image Search result {i+1}",
                        "score": 5 # نعطيها درجة متوسطة
                    })
            except: continue
        
    except Exception as e:
        log(f"      ⚠️ Selenium Sniper Error: {e}")
    finally:
        if driver: driver.quit()
    
    # نُزيل الروابط المكررة قبل الإرسال
    unique_media = list({m['url']: m for m in all_media}.values())
    return unique_media

# ==============================================================================
# 4. RESOLVE AND SCRAPE (FULL PIPELINE)
# ==============================================================================

def resolve_and_scrape(target_url):
    """
    Full extraction pipeline: Scrolls, scrapes text, and gathers visual/code assets.
    Returns: final_url, final_title, extracted_text, og_image, assets_list
    """
    log(f"      🕵️‍♂️ Deep Scraping: {target_url[:60]}...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        
        driver.get(target_url)
        
        # 1. Handle Redirects (Wait for final URL) & Google Consent
        start_wait = time.time()
        final_url = target_url
        while time.time() - start_wait < 15: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1)
        
        # 2. Scroll to load images (Lazy Loading)
        scroll_page(driver)
        
        # 3. Get Content
        page_source = driver.page_source
        final_title = driver.title
        
        # 4. Extract Text (using Trafilatura for quality)
        extracted_text = trafilatura.extract(page_source, include_comments=False, favor_precision=True)
        
        # 5. Extract Assets (Images & Code) using BS4
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find OG Image (Hero Image Candidate)
        og_image = (soup.find('meta', property='og:image') or {}).get('content')
        
        # Extract all other assets
        assets = extract_assets_from_soup(soup, final_url)
        
        # Add OG Image to assets if unique and exists
        if og_image:
             # Check for relative URL in OG Image
             if og_image.startswith('/'):
                 og_image = urllib.parse.urljoin(final_url, og_image)
             
             if not any(a['url'] == og_image for a in assets if a['type'] == 'image'):
                assets.insert(0, {
                    "type": "image",
                    "url": og_image,
                    "description": "Main Featured Image / OpenGraph Image",
                    "source_url": final_url,
                    "is_hero": True,
                    "score": 15 # Highest score for Hero
                })

        return final_url, final_title, extracted_text, og_image, assets

    except Exception as e:
        log(f"      ❌ Scraper Error on {target_url}: {e}")
        return None, None, None, None, []
    finally:
        if driver: driver.quit()
