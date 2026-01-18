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
    payload = {
        'url': image_url,
        'caption': f"{content}\n\n🔗 Read here: {link}",
        'access_token': access_token
    }
    
    try:
        r = requests.post(post_url, data=payload)
        if r.status_code == 200:
            print("   ✅ Posted to Facebook.")
        else:
            print(f"   ❌ Facebook Post Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ Facebook Error: {e}")

# ==============================================================================
# MAIN ORCHESTRATOR (Publishing Only)
# ==============================================================================
def distribute_content(facebook_text, article_url, image_url):
    """
    Takes the generated text and publishes it to Facebook.
    """
    print(f"\n📢 Distributing to Social Media (Facebook)...")
    
    if facebook_text:
        post_to_facebook(facebook_text, image_url, article_url)
    else:
        print("⚠️ No Facebook text provided, skipping.")
