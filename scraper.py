# FILE: scraper.py
# DESCRIPTION: Advanced web scraper using Selenium with Eager Loading.
# RESTORED: Original redirect resolution logic and Chrome options.

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
    """
    Opens a URL using Selenium, resolves redirects (crucial for Google News links),
    and scrapes content using the original robust logic.
    """
    log(f"      🕵️‍♂️ Selenium: Resolving Link with Eager Strategy...")
    
    # --- ORIGINAL CHROME OPTIONS RESTORED ---
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Randomize User-Agent from config
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    chrome_options.add_argument("--mute-audio") 

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(25) 
        
        driver.get(google_url)
        
        # --- ORIGINAL REDIRECT LOGIC RESTORED ---
        # This loop waits for the URL to change from "google.com" to the actual site
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
        
        # Filter out video/gallery pages (Original Logic)
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None

        # Try Trafilatura (Best quality)
        extracted_text = trafilatura.extract(
            page_source, 
            include_comments=False, 
            include_tables=True, # Restored
            favor_precision=True
        )
        
        if extracted_text and len(extracted_text) > 800:
            return final_url, final_title, extracted_text

        # Fallback: BeautifulSoup (Original Logic)
        soup = BeautifulSoup(page_source, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        
        if len(fallback_text) > 800:
            return final_url, final_title, fallback_text
            
        return None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {str(e)[:100]}")
        return None, None, None
    finally:
        if driver:
            try: driver.quit()
            except: pass
