import os
import requests
import datetime
import time
from github import Github  # تأكد أن PyGithub موجودة في requirements.txt

# ==============================================================================
# TOKEN AUTO-RENEWAL SYSTEM (كودك مع تحسينات بسيطة)
# ==============================================================================

def check_and_renew_facebook_token():
    """
    Checks if the Facebook token is expiring soon.
    If yes, refreshes it via Graph API and updates GitHub Secrets automatically.
    """
    token = os.getenv('FB_PAGE_ACCESS_TOKEN')
    app_id = os.getenv('FB_APP_ID')
    app_secret = os.getenv('FB_APP_SECRET')
    repo_name = os.getenv('GITHUB_REPO_NAME')
    github_token = os.getenv('MY_GITHUB_TOKEN')

    # إذا كانت البيانات ناقصة، نعيد التوكن الموجود ونخرج لتجنب توقف النظام
    if not (token and app_id and app_secret and repo_name and github_token):
        # print("⚠️ Auto-Renew info missing. Using current token.") 
        return token

    # 1. Check Token Validity & Expiry
    debug_url = f"https://graph.facebook.com/debug_token?input_token={token}&access_token={token}"
    try:
        r = requests.get(debug_url).json()
        if 'data' not in r:
            return token
            
        expires_at_timestamp = r['data'].get('expires_at', 0)
        
        # If token is permanent (0), return it.
        if expires_at_timestamp == 0:
            return token 
            
        expires_date = datetime.datetime.fromtimestamp(expires_at_timestamp)
        days_left = (expires_date - datetime.datetime.now()).days
        
        print(f"   ⏳ Facebook Token expires in: {days_left} days.")

        if days_left > 10:
            return token 

        # 2. RENEWAL LOGIC
        print("   🔄 Token expiring soon! Attempting auto-renewal...")
        
        exchange_url = (
            f"https://graph.facebook.com/v19.0/oauth/access_token?"
            f"grant_type=fb_exchange_token&"
            f"client_id={app_id}&"
            f"client_secret={app_secret}&"
            f"fb_exchange_token={token}"
        )
        
        refresh_r = requests.get(exchange_url).json()
        new_token = refresh_r.get('access_token')
        
        if new_token:
            print("   ✅ SUCCESS: Fetched new Long-Lived Token.")
            
            # 3. Update GitHub Secret
            try:
                g = Github(github_token)
                repo = g.get_repo(repo_name)
                repo.create_secret("FB_PAGE_ACCESS_TOKEN", new_token)
                print("   💾 GitHub Secret 'FB_PAGE_ACCESS_TOKEN' updated.")
                return new_token
            except Exception as gh_e:
                print(f"   ❌ GitHub Update Failed: {gh_e}")
                return new_token 
        else:
            print(f"   ❌ Token Refresh Failed: {refresh_r}")
            return token

    except Exception as e:
        print(f"⚠️ Token Monitor Error: {e}")
        return token

# ==============================================================================
# FACEBOOK MANAGER (Standard Posting) - تم إصلاح مشكلة تحميل الصورة هنا
# ==============================================================================

def download_image_robust(url):
    """تحميل الصورة بقوة لتجنب خطأ RemoteDisconnected."""
    # نضيف User-Agent لنبدو كمتصفح
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 3 محاولات تحميل
    for i in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 200:
                return r.content
        except Exception as e:
            print(f"      ⚠️ Image download retry {i+1}/3 failed: {e}")
            time.sleep(2)
            
    print("      ❌ Failed to download image after 3 attempts.")
    return None

def post_to_facebook(content, image_url, link):
    # نفحص التجديد أولاً ولكن لا نعتمد عليه كلياً في حال الفشل
    current_token = os.getenv('FB_PAGE_ACCESS_TOKEN') 
    
    # محاولة سريعة للتجديد، إن فشلت نستخدم الموجود
    try:
        renewed = check_and_renew_facebook_token()
        if renewed: current_token = renewed
    except: pass

    page_id = os.getenv('FB_PAGE_ID')

    if not page_id or not current_token:
        print("⚠️ Facebook credentials missing.")
        return

    post_url = f"https://graph.facebook.com/{page_id}/photos"
    
    # 1. تحميل الصورة (الطريقة القوية الجديدة)
    img_content = download_image_robust(image_url)
    if not img_content:
        return # لا نكمل إذا لم توجد صورة

    # 2. البيانات
    payload = {
        'caption': f"{content}\n\n🔗 Read here: {link}",
        'access_token': current_token
    }
    
    files = {
        'source': ('image.jpg', img_content, 'image/jpeg')
    }

    try:
        r = requests.post(post_url, data=payload, files=files, timeout=90) # زيادة الوقت
        if r.status_code == 200:
            print("   ✅ Posted Image to Facebook.")
        else:
            print(f"   ❌ FB Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ FB Connection Error: {e}")

def post_reel_to_facebook(video_path, caption):
    current_token = os.getenv('FB_PAGE_ACCESS_TOKEN')
    try:
        renewed = check_and_renew_facebook_token()
        if renewed: current_token = renewed
    except: pass
    
    page_id = os.getenv('FB_PAGE_ID')
    
    if not page_id or not current_token:
        print("⚠️ Credentials missing for Reel.")
        return
    
    if not os.path.exists(video_path):
        return

    print("   🚀 Uploading FB Reel...")
    
    # نستخدم السيرفر المخصص للفيديو
    post_url = f"https://graph-video.facebook.com/{page_id}/videos"
    
    payload = {
        'description': caption,
        'access_token': current_token,
        'published': 'true'
    }
    
    try:
        with open(video_path, 'rb') as f:
            files = {'source': (os.path.basename(video_path), f, 'video/mp4')}
            # وقت طويل للرفع
            r = requests.post(post_url, data=payload, files=files, timeout=200)
            
        if r.status_code == 200:
            print("   ✅ Posted Reel to FB.")
        else:
            print(f"   ❌ FB Reel Failed: {r.text}")
            
    except Exception as e:
        print(f"   ❌ FB Reel Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def distribute_content(facebook_text, article_url, image_url):
    print(f"\n📢 Distributing to Social Media (Facebook)...")
    if facebook_text and article_url and image_url:
        post_to_facebook(facebook_text, image_url, article_url)
    else:
        print("⚠️ Missing data for FB distribution.")
