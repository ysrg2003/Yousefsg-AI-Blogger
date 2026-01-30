import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_page_html(target_url):
    """
    يفتح الصفحة، ينتظر التحويل، ويعيد الرابط النهائي + كود HTML الكامل
    """
    if "news.google.com" not in target_url:
        # لو الرابط مباشر، سنحتاج لفتحه أيضاً لجلبه عبر Selenium لتجنب الحظر
        pass 

    print(f"      🕵️‍♂️ Selenium: Opening & Resolving: {target_url[:50]}...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120) # زيادة المهلة للمواقع الثقيلة
        
        driver.get(target_url)
        
        # منطق الانتظار الذكي (لو كان رابط جوجل)
        is_google = "news.google.com" in target_url
        start_time = time.time()
        
        while time.time() - start_time < 45:
            current = driver.current_url
            
            # إذا كان الرابط جوجل، ننتظر حتى يتغير
            if is_google:
                if "news.google.com" not in current and "search?" not in current:
                     if "consent.google" not in current:
                        # وصلنا! ننتظر قليلاً ليتحمل المحتوى (JS)
                        time.sleep(30) 
                        html = driver.page_source
                        print(f"      ✅ Success: {current}")
                        return {"url": current, "html": html}
            else:
                # إذا لم يكن رابط جوجل (مباشر)، ننتظر قليلاً ثم نسحب
                time.sleep(60)
                html = driver.page_source
                print(f"      ✅ Direct Access: {current}")
                return {"url": current, "html": html}

            time.sleep(4)
            
        print("      ⚠️ Timeout: Could not resolve URL.")
        return None

    except Exception as e:
        print(f"      ❌ Selenium Error: {e}")
        return None
    finally:
        if driver:
            try: driver.quit()
            except: pass
