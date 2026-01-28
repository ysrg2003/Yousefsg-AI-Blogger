# FILE: publisher.py
# DESCRIPTION: Handles all interactions with the Blogger API to publish posts.

import os
import requests
import json
from config import log

def get_blogger_token():
    """
    Refreshes the OAuth token needed to authenticate with the Blogger API.
    """
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    try:
        r = requests.post('https://oauth2.googleapis.com/token', data=payload)
        r.raise_for_status()
        return r.json().get('access_token')
    except requests.exceptions.RequestException as e:
        log(f"❌ Blogger Token Refresh Error: {e}")
        return None

def publish_post(title, content, labels):
    """
    Publishes a new post to the configured Blogger blog.
    """
    token = get_blogger_token()
    if not token:
        log("❌ Failed to get Blogger token. Publishing aborted.")
        return None
        
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts?isDraft=false"
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    body = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content,
        "labels": labels
    }
    try:
        r = requests.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()  # أولاً: احفظ الاستجابة في متغير
        link = data.get('url') # ثانياً: استخرج الرابط
        post_id = data.get('id') # ثالثاً: استخرج المعرف
        log(f"✅ Published LIVE: {link}")
        return link, post_id
    except requests.exceptions.RequestException as e:
        log(f"❌ Blogger API Error: {e.response.text if e.response else e}")
        return None

    

def update_existing_post(post_id, title, content):
    """
    تحديث مقال موجود مسبقاً على بلوجر باستخدام معرف المقال (Post ID).
    يُستخدم هذا بعد عملية التدقيق (Audit) لتحسين جودة المقال.
    """
    token = get_blogger_token()
    if not token:
        log("❌ Failed to get Blogger token for update.")
        return False
        
    blog_id = os.getenv('BLOGGER_BLOG_ID')
    # رابط الـ API الخاص بتحديث المقالات (PUT request)
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/{post_id}"
    
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
    # البيانات التي سيتم تحديثها
    body = {
        "kind": "blogger#post",
        "id": post_id,
        "blog": {"id": blog_id},
        "title": title,
        "content": content
    }
    
    try:
        # نستخدم PUT لاستبدال المحتوى القديم بالمحتوى المحسن
        r = requests.put(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        log(f"   ✅ Post updated successfully on Blogger (ID: {post_id})")
        return True
    except requests.exceptions.RequestException as e:
        error_msg = e.response.text if e.response else str(e)
        log(f"   ❌ Blogger Update API Error: {error_msg}")
        return False
