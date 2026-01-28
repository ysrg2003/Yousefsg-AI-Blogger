# FILE: indexer.py
# ROLE: Force Google to index the new URL immediately via Indexing API.

import os
import json
import requests
from oauth2client.service_account import ServiceAccountCredentials
from config import log

SCOPES = ["https://www.googleapis.com/auth/indexing"]
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

def get_credentials():
    # يحتاج مفتاح خدمة (Service Account) جديد بصلاحيات Indexing API
    json_creds = os.getenv('GOOGLE_INDEXING_JSON')
    if not json_creds:
        log("⚠️ Indexing Skipped: GOOGLE_INDEXING_JSON not found.")
        return None
    
    try:
        info = json.loads(json_creds)
        return ServiceAccountCredentials.from_json_keyfile_dict(info, SCOPES)
    except Exception as e:
        log(f"❌ Indexing Auth Error: {e}")
        return None

def submit_url(url):
    log(f"   🚀 [Indexer] Pinging Google for: {url}...")
    creds = get_credentials()
    if not creds: return

    try:
        access_token = creds.get_access_token().access_token
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        
        content = {
            "url": url,
            "type": "URL_UPDATED"
        }
        
        r = requests.post(ENDPOINT, data=json.dumps(content), headers=headers)
        
        if r.status_code == 200:
            log("      ✅ Google Indexing API: Request Submitted Successfully.")
        else:
            log(f"      ⚠️ Indexing API Failed: {r.text}")
            
    except Exception as e:
        log(f"      ❌ Indexing Error: {e}")
