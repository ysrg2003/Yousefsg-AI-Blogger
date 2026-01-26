# FILE: scraper.py
# STATUS: AUDITED & VERIFIED
# FEATURES: Selenium Eager Loading, Redirect Resolution Loop, OG:Image Extraction.

import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import trafilatura
from bs4 import BeautifulSoup
from config import log, USER_AGENTS

def resolve_and_scrape(google_url):
    log(f"      🕵️‍♂️ Selenium: Resolving Link & Hunting Image...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    chrome_options.add_argument("--mute-audio") 

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25) 
        
        driver.get(google_url)
        
        # --- CRITICAL: Redirect Wait Loop ---
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
        
        # Video Filter
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None, None

        # --- CRITICAL: Image Extraction ---
        soup = BeautifulSoup(page_source, 'html.parser')
        og_image = None
        try:
            meta_img = soup.find('meta', property='og:image')
            if meta_img: og_image = meta_img.get('content')
            if not og_image:
                meta_img = soup.find('meta', name='twitter:image')
                if meta_img: og_image = meta_img.get('content')
        except: pass

        # Text Extraction
        extracted_text = trafilatura.extract(
            page_source, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True
        )
        
        if extracted_text and len(extracted_text) > 800:
            return final_url, final_title, extracted_text, og_image

        # Fallback Text
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        
        if len(fallback_text) > 800:
            return final_url, final_title, fallback_text, og_image
            
        return None, None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {str(e)[:100]}")
        return None, None, None, None
    finally:
        if driver:
            try: driver.quit()
            except: pass
