import os
import requests

# ==============================================================================
# FACEBOOK MANAGER
# ==============================================================================

def post_to_facebook(content, image_url, link):
    page_id = os.getenv('FB_PAGE_ID')
    access_token = os.getenv('FB_PAGE_ACCESS_TOKEN')

    if not page_id or not access_token:
        print("⚠️ Facebook credentials missing.")
        return

    post_url = f"https://graph.facebook.com/{page_id}/photos"
    
    # 1. تحميل الصورة أولاً (Download Image)
    try:
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            print(f"❌ Failed to download image for Facebook: {img_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return

    # 2. تجهيز البيانات (بدون رابط الصورة، بل الصورة نفسها)
    payload = {
        'caption': f"{content}\n\n🔗 Read here: {link}",
        'access_token': access_token
    }
    
    # 3. إرسال الصورة كملف (Binary Source)
    files = {
        'source': ('image.jpg', img_response.content, 'image/jpeg')
    }

    try:
        # نستخدم files لرفع الصورة مباشرة
        r = requests.post(post_url, data=payload, files=files, timeout=60)
        
        if r.status_code == 200:
            print("   ✅ Posted to Facebook successfully.")
        else:
            print(f"   ❌ Facebook Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ Facebook Connection Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def distribute_content(facebook_text, article_url, image_url):
    """
    Takes the generated text and publishes it to Facebook.
    """
    print(f"\n📢 Distributing to Social Media (Facebook)...")

    if facebook_text and article_url and image_url:
        post_to_facebook(facebook_text, image_url, article_url)
    else:
        print("⚠️ Missing content, URL, or Image for Facebook distribution.")
