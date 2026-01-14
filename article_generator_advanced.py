import os
from google_auth_oauthlib.flow import InstalledAppFlow

# ضع بياناتك هنا مؤقتاً
client_id = "ضع_هنا_الـ_client_id"
client_secret = "ضع_هنا_الـ_client_secret"

flow = InstalledAppFlow.from_client_config(
    {"installed": {"client_id": client_id, "client_secret": client_secret, 
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth", 
                   "token_uri": "https://oauth2.googleapis.com/token"}},
    scopes=['https://www.googleapis.com/auth/blogger']
)
flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
auth_url, _ = flow.authorization_url(prompt='consent')
print(f"انسخ هذا الرابط وافتحه في المتصفح ووافق على الصلاحيات: \n\n{auth_url}\n")
