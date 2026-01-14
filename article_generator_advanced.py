import requests

client_id = "291465728218-li940ggvqjc7jid3kvrdi9okjcireiqm.apps.googleusercontent.com"
client_secret = "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"
auth_code = "4/1ASc3gC2Dvyt7J-lbpPAEYuZbSWQrvqYmM2fhLoz6tWI4DASuaWX9or1pJ-o"

def get_refresh_token():
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=params)
    print("\nYOUR REFRESH TOKEN IS:")
    print(r.json().get('refresh_token'))

if __name__ == "__main__":
    get_refresh_token()

