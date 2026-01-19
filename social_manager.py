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

    # استخدام نقطة نهاية الصور لأن التفاعل مع الصور أعلى
    post_url = f"https://graph.facebook.com/{page_id}/photos"
    
    payload = {
        'url': image_url,
        'caption': f"{content}\n\n🔗 Rrad More: {link}", # تم التعريب أو تركه انجليزي حسب جمهورك
        'access_token': access_token
    }

    try:
        r = requests.post(post_url, data=payload, timeout=30)
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
