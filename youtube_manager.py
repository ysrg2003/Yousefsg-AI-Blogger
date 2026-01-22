import os
import json
import googleapiclient.discovery
from google.oauth2.credentials import Credentials

def get_authenticated_service():
    json_creds = os.getenv('YOUTUBE_CREDENTIALS_JSON')
    if not json_creds: return None
    try:
        creds_data = json.loads(json_creds)
        creds = Credentials.from_authorized_user_info(creds_data)
        return googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    except: return None

def upload_video_to_youtube(file_path, title, description, tags):
    youtube = get_authenticated_service()
    if not youtube: return None, None
    
    print(f"📤 Uploading YT: {title[:40]}...")
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4500], # Leave room for link later
            "tags": tags,
            "categoryId": "28"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    try:
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True))
        res = req.execute()
        return res.get('id'), f"https://youtu.be/{res.get('id')}"
    except Exception as e:
        print(f"❌ YT Upload Error: {e}")
        return None, None

def update_video_description(video_id, extra_text):
    """Appends text to description instead of replacing it."""
    youtube = get_authenticated_service()
    if not youtube or not video_id: return
    
    try:
        # 1. Fetch current details
        res = youtube.videos().list(part="snippet", id=video_id).execute()
        if not res.get("items"): return
        
        snippet = res["items"][0]["snippet"]
        old_desc = snippet["description"]
        
        # 2. Append, not replace
        snippet["description"] = f"{old_desc}\n\n{extra_text}"
        
        youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
        print("✅ YT Description Appended Successfully.")
    except Exception as e:
        print(f"⚠️ YT Update Error: {e}")
