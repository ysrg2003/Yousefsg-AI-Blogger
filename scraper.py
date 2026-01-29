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
    "1x1", "spacer", "blank", "tracking", "blob:", "data:", "advertisement"
]

# ==============================================================================
# 2. HELPER FUNCTIONS (VALIDATION)
# ==============================================================================

def is_valid_image_url(url):
    """Checks if image URL is valid and accessible."""
    if not url: return False
    url_lower = url.lower()
    
    # Must be http/https
    if not url.startswith('http'): return False
    
    # Check Blacklist
    if any(x in url_lower for x in MEDIA_LINK_BLACKLIST): return False
    
    # Filter out tiny icons or tracking pixels based on keywords
    if any(x in url_lower for x in ['icon', 'logo', 'avatar', 'profile', 'button', 'svg', 'loader', 'spinner']):
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
    if "youtube.com/watch" in url_lower: return True
    if "youtu.be" in url_lower: return True
    if "player.vimeo.com" in url_lower: return True
    if url_lower.endswith(".mp4") or url_lower.endswith(".webm"): return True
    
    return False

def extract_element_context(element):
    """Extracts text context around an image/video to validate relevance."""
    context = []
    for attr in ['alt', 'title', 'aria-label']:
        if element.get(attr): context.append(element[attr])
    parent = element.parent
    if parent:
        text = parent.get_text(strip=True)[:150]
        if text: context.append(text)
    return " | ".join(context) if context else "Visual Evidence"

def extract_media_from_soup(soup, base_url, directive):
    """
    Parses HTML to find high-value media (Videos, GIFs, Screenshots).
    """
    candidates = []
    
    # 1. Search for Videos (Strict)
    for video in soup.find_all(['iframe', 'video', 'embed']):
        src = video.get('src') or (video.find('source') and video.find('source').get('src'))
        if not src: continue
        
        # Normalize URL
        if src.startswith('//'): src = 'https:' + src
        if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        
        if is_valid_video_url(src):
            # Convert YouTube watch links to embed
            if "watch?v=" in src:
                vid_id = src.split("v=")[1].split("&")[0]
                src = f"https://www.youtube.com/embed/{vid_id}"
            elif "youtu.be/" in src:
                vid_id = src.split("youtu.be/")[1].split("?")[0]
                src = f"https://www.youtube.com/embed/{vid_id}"

            m_type = "embed" if "youtube" in src or "vimeo" in src else "video"
            context = extract_element_context(video)
            candidates.append({"type": m_type, "url": src, "description": context, "score": 10})

    # 2. Search for Images
    for img in soup.find_all('img', src=True):
        src = img['src']
        if not src: continue
        
        # Normalize
        if src.startswith('//'): src = 'https:' + src
        if src.startswith('/'): src = urllib.parse.urljoin(base_url, src)
        
        if is_valid_image_url(src):
            # Basic size check (skip small images based on URL hints)
            if "1x1" in src or "32x32" in src: continue
            
            context = extract_element_context(img)
            candidates.append({"type": "image", "url": src, "description": context, "score": 5})

    return candidates

# ==============================================================================
# 3. GOOGLE IMAGE FALLBACK
# ==============================================================================

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
        
        # Click a few images to get real URLs (Google thumbnails are base64 often)
        # We try to grab the source from the result
        thumbnails = driver.find_elements(By.CSS_SELECTOR, "img")
        
        count = 0
        for thumb in thumbnails:
            if count >= 4: break
            try:
                src = thumb.get_attribute('src')
                if src and src.startswith('http') and "encrypted" not in src and "favicon" not in src:
                    images.append({"type": "image", "url": src, "description": f"Google Search: {keyword}", "score": 4})
                    count += 1
            except: continue
            
    except Exception as e:
        log(f"      ⚠️ Google Image Fallback Error: {e}")
    finally:
        if driver: driver.quit()
        
    return images

# ==============================================================================
# 4. THE SMART HUNTER
# ==============================================================================

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

    # 2. If not enough images, try Google Image Fallback
    current_images = [m for m in all_media if m['type'] == 'image']
    if len(current_images) < 3:
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
        
        # Handle Redirects
        start_wait = time.time()
        while time.time() - start_wait < 10: 
            current = driver.current_url
            if "news.google.com" not in current and "google.com" not in current:
                break
            time.sleep(1)
            
        final_url = driver.current_url
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Hunt for media inside the page
        found_media = extract_media_from_soup(soup, final_url, "hunt_for_video")
        
        # Get OG Image (High Quality usually)
        og_image = None
        meta_og = soup.find('meta', property='og:image')
        if meta_og: 
            og_image = meta_og.get('content')
            if is_valid_image_url(og_image):
                found_media.insert(0, {"type": "image", "url": og_image, "description": "Featured Image", "score": 9})
        
        extracted_text = trafilatura.extract(page_source, include_comments=False, favor_precision=True)
        
        if extracted_text and len(extracted_text) > 600:
            return final_url, driver.title, extracted_text, og_image, found_media

        return None, None, None, None, []
        
    except Exception as e:
        log(f"      ❌ Scraper Error: {e}")
        return None, None, None, None, []
    finally:
        if driver: driver.quit()
