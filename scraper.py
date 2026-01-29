# FILE: scraper.py
# ROLE: Advanced Web Scraper & Visual Hunter.
# UPDATED: Strict filtering for broken media & Google Images Fallback.

import time
import random
import urllib.parse
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import trafilatura
from bs4 import BeautifulSoup
from config import log, USER_AGENTS

# --- CONFIGURATION ---
NEWS_DOMAINS_BLACKLIST = [
    "techcrunch", "theverge", "engadget", "wired", "cnet", "forbes", 
    "businessinsider", "nytimes", "wsj", "bloomberg", "reuters", "cnn",
    "bbc", "medium", "reddit", "wikipedia", "latestai", "techradar"
]

MEDIA_LINK_BLACKLIST = [
    "googletagmanager", "google-analytics", "doubleclick", "pixel", 
    "adsystem", "adnxs", "script", "tracker", "analytics", "fb.com/tr",
    "1x1", "spacer", "blank", "tracking", "blob:", "data:", "advertisement"
]

def is_valid_image_url(url):
    """Checks if image URL is valid and accessible."""
    if not url or any(x in url.lower() for x in MEDIA_LINK_BLACKLIST): return False
    if not url.startswith('http'): return False
    
    # Filter out tiny icons or tracking pixels based on keywords
    if any(x in url.lower() for x in ['icon', 'logo', 'avatar', 'profile', 'button', 'svg']):
        return False
        
    return True

def is_valid_video_url(url):
    """Strictly allows only playable video formats."""
    if not url: return False
    url_lower = url.lower()
    
    # Must be a real protocol
    if not url.startswith('http'): return False
    if any(x in url_lower for x in MEDIA_LINK_BLACKLIST): return False
    
    # Allowed types
    if "youtube.com/embed" in url_lower: return True
    if "player.vimeo.com" in url_lower: return True
    if url_lower.endswith(".mp4") or url_lower.endswith(".webm"): return True
    
    return False

def extract_media_from_soup(soup, base_url, directive):
    candidates = []
    
    # 1. Search for Videos (Strict)
    for video in soup.find_all(['iframe', 'video', 'embed']):
        src = video.get('src') or (video.find('source') and video.find('source').get('src'))
        if not src: continue
        
        if src.startswith('//'): src = 'https:' + src
        if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        
        if is_valid_video_url(src):
            m_type = "embed" if "youtube" in src or "vimeo" in src else "video"
            candidates.append({"type": m_type, "url": src, "description": "Video Source", "score": 10})

    # 2. Search for Images
    for img in soup.find_all('img', src=True):
        src = img['src']
        if not src: continue
        
        if src.startswith('//'): src = 'https:' + src
        if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        
        if is_valid_image_url(src):
            # Basic size check (skip small images based on URL hints)
            if "1x1" in src or "32x32" in src: continue
            
            candidates.append({"type": "image", "url": src, "description": img.get('alt', 'Article Image'), "score": 5})

    return candidates

def google_image_fallback(keyword):
    """Fallback: Hunts for images on Google Images if source images are broken."""
    log(f"      📸 [Fallback] Hunting Google Images for: {keyword}...")
    images = []
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&tbm=isch"
        driver.get(search_url)
        time.sleep(2)
        
        # Click a few images to get real URLs
        thumbnails = driver.find_elements(By.CSS_SELECTOR, "img.YQ4gaf")
        for i, thumb in enumerate(thumbnails[:5]):
            try:
                src = thumb.get_attribute('src')
                if src and src.startswith('http') and not "encrypted" in src:
                    images.append({"type": "image", "url": src, "description": f"Google Search: {keyword}", "score": 4})
            except: continue
            
    except Exception as e:
        log(f"      ⚠️ Google Image Fallback Error: {e}")
    finally:
        if driver: driver.quit()
        
    return images

def smart_media_hunt(target_keyword, category, directive):
    """
    Hybrid Hunt with Google Fallback.
    """
    log(f"      🎯 Sniper Hunt: Searching for Visual Proofs ('{directive}')...")
    all_media = []

    # 1. Try AI Researcher first (High Quality)
    try:
        import ai_researcher
        ai_visuals = ai_researcher.smart_hunt(target_keyword, {}, mode="visual")
        for item in ai_visuals:
            url = item.get('url') or item.get('link')
            if is_valid_video_url(url):
                all_media.append({"type": "embed", "url": url, "description": "AI Found Video", "score": 10})
            elif is_valid_image_url(url):
                all_media.append({"type": "image", "url": url, "description": "AI Found Image", "score": 8})
    except: pass

    # 2. If not enough, try Google Image Fallback
    if len([m for m in all_media if m['type'] == 'image']) < 3:
        google_imgs = google_image_fallback(target_keyword)
        all_media.extend(google_imgs)

    return all_media

def resolve_and_scrape(google_url):
    log(f"      📰 Omni-Scraper: Extracting content from {google_url[:50]}...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        
        driver.get(google_url)
        time.sleep(3) # Wait for JS
        
        final_url = driver.current_url
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        found_media = extract_media_from_soup(soup, final_url, "hunt_for_video")
        
        # Get OG Image
        og_image = None
        meta_og = soup.find('meta', property='og:image')
        if meta_og: og_image = meta_og.get('content')
        
        extracted_text = trafilatura.extract(page_source, include_comments=False, favor_precision=True)
        
        if extracted_text and len(extracted_text) > 600:
            return final_url, driver.title, extracted_text, og_image, found_media

        return None, None, None, None, []
        
    except Exception as e:
        log(f"      ❌ Scraper Error: {e}")
        return None, None, None, None, []
    finally:
        if driver: driver.quit()
