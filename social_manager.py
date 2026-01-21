import os
import requests

# ==============================================================================
# FACEBOOK MANAGER
# ==============================================================================

def post_to_facebook(content, image_url, link):
    """Publishes a Photo Post with a link."""
    page_id = os.getenv('FB_PAGE_ID')
    access_token = os.getenv('FB_PAGE_ACCESS_TOKEN')

    if not page_id or not access_token:
        print("⚠️ Facebook credentials missing.")
        return

    post_url = f"https://graph.facebook.com/{page_id}/photos"
    
    # 1. تحميل الصورة
    try:
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            print(f"❌ Failed to download image for Facebook: {img_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return

    # 2. تجهيز البيانات
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
            print("   ✅ Posted Image to Facebook successfully.")
        else:
            print(f"   ❌ Facebook Image Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ Facebook Connection Error: {e}")

def post_reel_to_facebook(video_path, caption):
    """Publishes a Video Reel to Facebook."""
    page_id = os.getenv('FB_PAGE_ID')
    access_token = os.getenv('FB_PAGE_ACCESS_TOKEN')

    if not page_id or not access_token:
        print("⚠️ Facebook credentials missing for Reel.")
        return
    
    if not os.path.exists(video_path):
        print("⚠️ Video file not found for Reel.")
        return

    print("   🚀 Uploading Facebook Reel...")
    
    # نستخدم graph-video لأنه مخصص لرفع الملفات الكبيرة
    post_url = f"https://graph-video.facebook.com/{page_id}/videos"
    
    payload = {
        'description': caption,
        'access_token': access_token,
        'published': 'true'
    }
    
    try:
        with open(video_path, 'rb') as f:
            files = {
                'source': (os.path.basename(video_path), f, 'video/mp4')
            }
            # زيادة المهلة (timeout) لأن الفيديو يأخذ وقتاً
            r = requests.post(post_url, data=payload, files=files, timeout=120)
            
        if r.status_code == 200:
            print("   ✅ Posted Reel to Facebook successfully.")
        else:
            print(f"   ❌ Facebook Reel Failed: {r.text}")
            
    except Exception as e:
        print(f"   ❌ Facebook Reel Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def distribute_content(facebook_text, article_url, image_url):
    """
    Takes the generated text and publishes the main article post.
    """
    print(f"\n📢 Distributing Article Post to Facebook...")

    if facebook_text and article_url and image_url:
        post_to_facebook(facebook_text, image_url, article_url)
    else:
        print("⚠️ Missing content, URL, or Image for Facebook distribution.")
