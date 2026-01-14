import os
from google_auth_oauthlib.flow import InstalledAppFlow

# ضع بياناتك هنا مؤقتاً
client_id = "291465728218-li940ggvqjc7jid3kvrdi9okjcireiqm.apps.googleusercontent.com"
client_secret = "{"installed":{"client_id":"291465728218-li940ggvqjc7jid3kvrdi9okjcireiqm.apps.googleusercontent.com","project_id":"prime-haven-481407-a6","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}
"

flow = InstalledAppFlow.from_client_config(
    {"installed": {"client_id": client_id, "client_secret": client_secret, 
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth", 
                   "token_uri": "https://oauth2.googleapis.com/token"}},
    scopes=['https://www.googleapis.com/auth/blogger']
)
flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
auth_url, _ = flow.authorization_url(prompt='consent')
print(f"انسخ هذا الرابط وافتحه في المتصفح ووافق على الصلاحيات: \n\n{auth_url}\n")
