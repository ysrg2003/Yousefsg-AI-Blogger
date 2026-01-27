
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

    # --- OPTIMIZATION: Block images and CSS for much faster loading ---
    # This tells Chrome not to waste time on visual elements we don't need.
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    # -----------------------------------------------------------------

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # --- FIX: Increased timeout from 25 to 59 seconds ---
        # This gives heavy, ad-filled news sites more time to load before failing.
        driver.set_page_load_timeout(59) 
        # ----------------------------------------------------
        
        driver.get(google_url)
        
        # Wait for the URL to redirect from Google to the actual news site
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
        
        # Skip video galleries and YouTube links which don't have good text content
        bad_segments = ["/video/", "/watch", "/gallery/", "/photos/", "youtube.com"]
        if any(seg in final_url.lower() for seg in bad_segments):
            log(f"      ⚠️ Skipped Video/Gallery URL: {final_url}")
            return None, None, None, None

        # Attempt to extract the main article image (og:image)
        soup = BeautifulSoup(page_source, 'html.parser')
        og_image = None
        try:
            meta_img = soup.find('meta', property='og:image')
            if meta_img: og_image = meta_img.get('content')
            if not og_image:
                meta_img = soup.find('meta', name='twitter:image')
                if meta_img: og_image = meta_img.get('content')
        except: pass

        # Primary extraction method using Trafilatura (very effective)
        extracted_text = trafilatura.extract(
            page_source, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True
        )
        
        if extracted_text and len(extracted_text) > 800:
            return final_url, final_title, extracted_text, og_image

        # Fallback method using BeautifulSoup if Trafilatura fails
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.extract()
        fallback_text = soup.get_text(" ", strip=True)
        
        if fallback_text and len(fallback_text) > 800:
            return final_url, final_title, fallback_text, og_image
            
        # If both methods fail, return nothing
        return None, None, None, None

    except Exception as e:
        log(f"      ❌ Selenium Error: {str(e)[:100]}")
        return None, None, None, None
    finally:
        if driver:
            try: 
                driver.quit()
            except: 
                pass
