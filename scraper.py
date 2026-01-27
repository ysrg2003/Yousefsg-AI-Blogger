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

NEWS_DOMAINS_BLACKLIST = [
    "techcrunch", "theverge", "engadget", "wired", "cnet", "forbes", 
    "businessinsider", "nytimes", "wsj", "bloomberg", "reuters", "cnn",
    "bbc", "medium", "reddit", "wikipedia", "latestai", "techradar"
]

# ==============================================================================
# 2. HELPER FUNCTIONS (SMART CONTEXT & EXTRACTION)
# ==============================================================================

def get_smart_query_by_category(keyword, category):
    base = f"{keyword} official"
    if "Video" in category or "Media" in category: return f"{base} demo showcase video"
    if "Robotics" in category or "Hardware" in category: return f"{base} reveal video demonstration"
    return f"{base} announcement blog"

def is_official_looking_url(url, keyword):
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if any(news in domain for news in NEWS_DOMAINS_BLACKLIST): return False
        return True
    except: return False

def extract_element_context(element):
    context = []
    for attr in ['alt', 'title', 'aria-label']:
        if element.get(attr): context.append(element[attr])
    parent = element.parent
    if parent:
        text = parent.get_text(strip=True)[:150]
        if text: context.append(text)
    return " | ".join(context) if context else "No description available"

def extract_media_from_soup(soup, base_url):
    candidates = []
    positive_signals = ["demo", "showcase", "tutorial", "interface", "example", "generated", "result", "how to", "workflow", "reveal", "trailer", "robot", "prototype"]
    negative_signals = ["logo", "icon", "background", "banner", "loader", "spinner", "avatar", "profile", "footer", "ad", "advertisement"]

    for video in soup.find_all(['video', 'iframe']):
        src = video.get('src') or (video.find('source') and video.find('source').get('src'))
        if not src: continue
        if src.startswith('//'): src = 'https:' + src
        if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        
        context = extract_element_context(video).lower()
        if any(bad in context or bad in src for bad in negative_signals): continue
        
        m_type = "embed" if 'youtube' in src or 'vimeo' in src else "video"
        candidates.append({"type": m_type, "url": src, "description": context, "score": sum(1 for sig in positive_signals if sig in context) + (2 if m_type == "video" else 1)})

    for img in soup.find_all('img', src=True):
        src = img['src']
        if src.endswith('.gif'):
            if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
            context = extract_element_context(img).lower()
            if any(bad in context or bad in src for bad in negative_signals): continue
            candidates.append({"type": "gif", "url": src, "description": context, "score": sum(1 for sig in positive_signals if sig in context)})
    
    return candidates

# ==============================================================================
# 3. THE DUAL-HUNT WEAPONS
# ==============================================================================

# --- WEAPON 1: THE SNIPER (TARGETED GOOGLE SEARCH) ---
def smart_media_hunt(target_keyword, category):
    search_query = get_smart_query_by_category(target_keyword, category)
    log(f"      🎯 Sniper Hunt: Searching Google for '{search_query}'...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    driver = None
    all_media = []

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.get(f"https://www.google.com/search?q={urllib.parse.quote(search_query)}")
        time.sleep(2)
        
        links = driver.find_elements(By.CSS_SELECTOR, 'div.g a')
        
        for link in links[:4]: # Check top 4 results
            url = link.get_attribute('href')
            if not url: continue

            if "youtube.com/watch" in url:
                try:
                    vid_id = url.split('v=')[1].split('&')[0]
                    embed_url = f"https://www.youtube.com/embed/{vid_id}"
                    all_media.append({"type": "embed", "url": embed_url, "description": f"Official YouTube Reveal: {target_keyword}", "score": 10})
                    log(f"         🎯 Sniper Found YouTube Video: {vid_id}")
                except: pass
                continue

            if is_official_looking_url(url, target_keyword):
                log(f"         🎯 Sniper Target Acquired: {url}")
                driver.get(url)
                time.sleep(4)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                media_in_page = extract_media_from_soup(soup, url)
                if media_in_page:
                    all_media.extend(media_in_page)
                break 
    except Exception as e:
        log(f"      ⚠️ Sniper Hunt Error: {e}")
    finally:
        if driver: driver.quit()
    
    return all_media

# --- WEAPON 2: THE OMNIVORE (TEXT & VISUALS FROM NEWS ARTICLES) ---
def resolve_and_scrape(google_url):
    log(f"      📰 Omni-Scraper: Hunting Text & Visuals in {google_url[:50]}...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    # --- CRITICAL FIX: Images are NO LONGER blocked ---
    # This allows BeautifulSoup to "see" the media on the page.
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        driver.get(google_url)
        
        final_url = google_url
        start_wait = time.time()
        while time.time() - start_wait < 15: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                final_url = current
                break
            time.sleep(1)

        final_title = driver.title
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # --- NEW: Extract visuals from the current news article ---
        found_media = extract_media_from_soup(soup, final_url)
        if found_media: log(f"         📸 Found {len(found_media)} visual asset(s) in this source.")

        og_image = (soup.find('meta', property='og:image') or {}).get('content')
        
        extracted_text = trafilatura.extract(page_source, include_comments=False, favor_precision=True)
        
        if extracted_text and len(extracted_text) > 600:
            # CRITICAL FIX: Now returns 5 values, including the media found
            return final_url, final_title, extracted_text, og_image, found_media

        return None, None, None, None, []
    except Exception as e:
        log(f"      ❌ Scraper Error: {e}")
        return None, None, None, None, []
    finally:
        if driver:
            try: driver.quit()
            except: pass```
