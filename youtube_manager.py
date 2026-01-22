import os
import json
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials

def get_authenticated_service():
    json_creds = os.getenv('YOUTUBE_CREDENTIALS_JSON')
    if not json_creds:
        print("❌ Error: YOUTUBE_CREDENTIALS_JSON secret is missing.")
        return None

    try:
        creds_data = json.loads(json_creds)
        creds = Credentials.from_authorized_user_info(creds_data)
        return googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Error loading YouTube credentials: {e}")
        return None

def upload_video_to_youtube(file_path, title, description, tags, category_id="28"):
    youtube = get_authenticated_service()
    if not youtube: return None, None
    
    # ضمان وجود الهاشتاجات داخل الوصف
    final_desc = description
    if tags:
        hashtags_str = " ".join([f"#{tag.replace(' ', '')}" for tag in tags])
        final_desc = f"{description}\n\n{hashtags_str}"

    print(f"📤 Uploading to YouTube: {title[:30]}...")
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": final_desc[:4500], # تجنب تجاوز الحد المسموح
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": "public", 
            "selfDeclaredMadeForKids": False
        }
    }
    
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )
        response = request.execute()
        video_id = response.get('id')
        print(f"✅ YouTube Upload Success! ID: {video_id}")
        return video_id, f"https://www.youtube.com/embed/{video_id}"
    except Exception as e:
        print(f"❌ YouTube Upload Failed: {e}")
        return None, None

def update_video_description(video_id, update_text):
    """
    Appends the article URL (update_text) to the TOP of the existing description
    to preserve SEO tags and the original description.
    """
    youtube = get_authenticated_service()
    if not youtube or not video_id: return
    
    print(f"🔄 Updating YouTube Description for ID: {video_id}...")
    
    try:
        video_response = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()
        
        if not video_response.get("items"):
            print("❌ Video not found.")
            return

        snippet = video_response["items"][0]["snippet"]
        original_desc = snippet["description"]
        
        # نضع الرابط في المقدمة للحصول على نقرات أكثر + نبقي الوصف القديم
        new_desc = f"{update_text}\n\n{original_desc}"
        snippet["description"] = new_desc
        
        update_request = youtube.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": snippet
            }
        )
        update_request.execute()
        print("✅ YouTube Description Updated safely (Appended).")
        
    except Exception as e:
        print(f"⚠️ Failed to update YouTube description: {e}")
