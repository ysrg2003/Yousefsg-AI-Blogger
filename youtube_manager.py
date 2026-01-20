import os
import json
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials

def get_authenticated_service():
    """
    Loads credentials from the YOUTUBE_CREDENTIALS_JSON environment variable.
    This variable must contain the full JSON content of the authorized token.
    """
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
    # 28 = Science & Technology
    youtube = get_authenticated_service()
    if not youtube: return None, None
    
    print(f"📤 Uploading to YouTube: {title[:30]}...")
    
    body = {
        "snippet": {
            "title": title[:100], # Max 100 chars
            "description": description[:5000],
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
        return f"https://youtu.be/{video_id}", f"https://www.youtube.com/embed/{video_id}"
    except Exception as e:
        print(f"❌ YouTube Upload Failed: {e}")
        return None, None
