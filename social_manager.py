import os
import requests
import datetime
import time
from github import Github  # مكتبة التعامل مع جيت هب

# ==============================================================================
# TOKEN AUTO-RENEWAL SYSTEM (القلب النابض الجديد)
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

    if not (token and app_id and app_secret and repo_name and github_token):
        print("⚠️ Auto-Renew skipped: Missing credentials (APP_ID, SECRET, or GITHUB_TOKEN).")
        return token

    # 1. Check Token Validity & Expiry
    debug_url = f"https://graph.facebook.com/debug_token?input_token={token}&access_token={token}"
    try:
        r = requests.get(debug_url).json()
        if 'data' not in r:
            print(f"⚠️ Token Debug Failed: {r}")
            return token
            
        expires_at_timestamp = r['data'].get('expires_at', 0)
        
        # If token is permanent (0) or expires in > 10 days, do nothing
        if expires_at_timestamp == 0:
            return token # Permanent token, all good.
            
        expires_date = datetime.datetime.fromtimestamp(expires_at_timestamp)
        days_left = (expires_date - datetime.datetime.now()).days
        
        print(f"   ⏳ Facebook Token expires in: {days_left} days.")

        if days_left > 10:
            return token # Still valid for enough time

        # 2. RENEWAL LOGIC: Token is expiring soon (< 10 days)
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
                # Create/Update the secret
                repo.create_secret("FB_PAGE_ACCESS_TOKEN", new_token)
                print("   💾 SUCCESS: GitHub Secret 'FB_PAGE_ACCESS_TOKEN' updated automatically.")
                return new_token # Use new token for current session
            except Exception as gh_e:
                print(f"   ❌ GitHub Update Failed: {gh_e}")
                return new_token # Use it anyway even if save failed
        else:
            print(f"   ❌ Token Refresh Failed: {refresh_r}")
            return token

    except Exception as e:
        print(f"⚠️ Token Monitor Error: {e}")
        return token

# ==============================================================================
# FACEBOOK MANAGER (Standard Posting)
# ==============================================================================

def post_to_facebook(content, image_url, link):
    # استخدام الدالة الذكية للحصول على التوكن (القديم أو الجديد المجدد)
    # ملاحظة: إذا فشل التجديد، سيعود بالتوكن القديم من البيئة
    # لكن بما أننا لا نستطيع تحديث os.environ بسهولة داخل الدالة،
    # نعتمد على أن الدالة جددت في GitHub للمرات القادمة، 
    # وفي هذه الجلسة نستخدم المتغير المعاد.
    
    # للتسهيل، سنقرأ من البيئة مباشرة لأن التحديث للبيئة الحالية معقد في الـ runtime، 
    # لكن سننفذ فحص التجديد في بداية التشغيل.
    
    page_id = os.getenv('FB_PAGE_ID')
    access_token = os.getenv('FB_PAGE_ACCESS_TOKEN') 

    if not page_id or not access_token:
        print("⚠️ Facebook credentials missing.")
        return

    post_url = f"https://graph.facebook.com/{page_id}/photos"
    
    # تحميل الصورة
    try:
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            print(f"❌ Failed to download image for FB: {img_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return

    payload = {
        'caption': f"{content}\n\n🔗 Read here: {link}",
        'access_token': access_token
    }
    
    files = {
        'source': ('image.jpg', img_response.content, 'image/jpeg')
    }

    try:
        r = requests.post(post_url, data=payload, files=files, timeout=60)
        if r.status_code == 200:
            print("   ✅ Posted Image to Facebook.")
        else:
            print(f"   ❌ FB Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ FB Connection Error: {e}")

def post_reel_to_facebook(video_path, caption):
    # *Trigger Renewal Check Before Posting Reel*
    # هذه الخطوة ستحاول تجديد التوكن وتخزينه في جيت هب للمستقبل
    # وسنستخدم التوكن العائد للمحاولة الحالية
    
    current_token = check_and_renew_facebook_token()
    page_id = os.getenv('FB_PAGE_ID')
    
    if not page_id or not current_token:
        print("⚠️ Credentials missing for Reel.")
        return
    
    if not os.path.exists(video_path):
        return

    print("   🚀 Uploading FB Reel...")
    
    post_url = f"https://graph-video.facebook.com/{page_id}/videos"
    
    payload = {
        'description': caption,
        'access_token': current_token, # استخدام التوكن (المحتمل تجديده)
        'published': 'true'
    }
    
    try:
        with open(video_path, 'rb') as f:
            files = {'source': (os.path.basename(video_path), f, 'video/mp4')}
            r = requests.post(post_url, data=payload, files=files, timeout=120)
            
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
    
    # نتأكد من التجديد هنا أيضاً
    check_and_renew_facebook_token()

    if facebook_text and article_url and image_url:
        post_to_facebook(facebook_text, image_url, article_url)
    else:
        print("⚠️ Missing data for FB distribution.")
