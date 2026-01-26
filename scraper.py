# FILE: scraper.py
# DESCRIPTION: Advanced web scraper using Selenium with Eager Loading, User-Agent rotation,
#              and a junk-text validation layer.

import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import trafilatura
from bs4 import BeautifulSoup
from config import log, USER_AGENTS

def is_valid_article_text(text):
    """
    Validation Layer 2.0: Checks if scraped text is high quality or junk.
    """
    if not text or len(text) < 800:
        return False
    
    # FIX: Removed 'robot' from this list to allow Robotics articles
    junk_indicators = [
        "JavaScript is required", "enable cookies", "access denied", 
        "security check", "please verify you are a human", "403 forbidden",
        "captcha", "cloudflare", "Incapsula"
    ]
    
    text_lower = text.lower()[:500] # Check first 500 chars usually contains these messages
    for junk in junk_indicators:
        if junk in text_lower:
            log(f"      🗑️ Junk detected: '{junk}'. Skipping source.")
            return False
            
    return True

def resolve_and_scrape(google_url):
    """
    Opens a URL using Selenium with Eager Strategy, resolves redirects,
    and scrapes clean, validated article text.
    """
    log(f"      🕵️‍♂️ Selenium: Resolving Link with Eager Strategy...")
    
    random_ua = random.choice(USER_AGENTS)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Fix 1: Block images to save bandwidth
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
    # Fix 2: Eager loading strategy (DOM only, skips ads/heavy scripts)
    chrome_options.page_load_strategy = 'eager' 
    chrome_options.add_argument(f'user-agent={random_ua}')
    chrome_options.add_argument("--mute-audio") 

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # Fix 3: Increased timeout to 45s to avoid renderer timeout errors
        driver.set_page_load_timeout(45) 
        
        driver.get(google_url)
        time.sleep(2) # Allow JS redirects to settle
        final_url = driver.current_url
        page_source = driver.page_source

        # Try Trafilatura first for high-quality extraction
        text = trafilatura.extract(page_source, include_comments=False, favor_precision=True)
        if is_valid_article_text(text):
            return final_url, driver.title, text
            
        # Fallback to BeautifulSoup if Trafilatura fails
        soup = BeautifulSoup(page_source, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form", "iframe"]): 
            tag.extract()
        bs_text = soup.get_text(" ", strip=True)
        if is_valid_article_text(bs_text):
            return final_url, driver.title, bs_text
        
        return None, None, None
    except Exception as e:
        log(f"      ❌ Scraper Error: {str(e)[:100]}")
        return None, None, None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
