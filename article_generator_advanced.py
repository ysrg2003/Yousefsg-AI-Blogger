import os
from google_auth_oauthlib.flow import InstalledAppFlow

# البيانات الصحيحة مستخرجة من ملفك
client_id = "291465728218-li940ggvqjc7jid3kvrdi9okjcireiqm.apps.googleusercontent.com"
client_secret = "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"

def get_auth_url():
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=['https://www.googleapis.com/auth/blogger']
    )
    
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    
    # إضافة access_type='offline' ضرورية جداً للحصول على Refresh Token
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print("\n" + "="*50)
    print("OPEN THIS URL IN YOUR BROWSER:")
    print(auth_url)
    print("="*50 + "\n")

if __name__ == "__main__":
    get_auth_url()
