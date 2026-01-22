# url_resolver.py
import time
import sys
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# إعداد الـ Logging لهذا الملف
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_final_url(target_url):
    """
    يقوم بفتح متصفح خفي لتتبع الرابط حتى الوصول للرابط النهائي
    """
    if "news.google.com" not in target_url:
        return target_url

    print(f"      🕵️‍♂️ Selenium: Resolving URL: {target_url[:50]}...")

    # إعدادات كروم
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
        
        # مهلة انتظار تحميل الصفحة (30 ثانية)
        driver.set_page_load_timeout(30)
        
        driver.get(target_url)
        
        # حلقة الانتظار (45 ثانية كحد أقصى)
        start_time = time.time()
        while time.time() - start_time < 45:
            current = driver.current_url
            
            # شروط النجاح: الرابط تغير ولم يعد جوجل نيوز أو جوجل بحث أو صفحة موافقة
            if "news.google.com" not in current and "search?" not in current:
                if "consent.google" not in current and "google.com/url" not in current:
                    print(f"      ✅ URL Found: {current}")
                    return current

            time.sleep(1.5)
            
        print("      ⚠️ Timeout: Could not resolve URL.")
        return None

    except Exception as e:
        print(f"      ❌ Selenium Error: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
