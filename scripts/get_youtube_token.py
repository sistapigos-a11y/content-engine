"""Run ONCE on your own computer per YouTube channel to get its refresh token.

  python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET

A browser opens; log in and pick the channel (EN or ES). The printed refresh token
goes into the GitHub secret YT_REFRESH_TOKEN_EN or YT_REFRESH_TOKEN_ES.
"""
import http.server
import sys
import urllib.parse
import webbrowser

import requests

PORT = 8765
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"


def main(client_id, client_secret):
    redirect = f"http://127.0.0.1:{PORT}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent"})
    code = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code["value"] = q.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab.")

        def log_message(self, *a):
            pass

    print("Opening browser... if it does not open, visit:\n", url)
    webbrowser.open(url)
    http.server.HTTPServer(("127.0.0.1", PORT), Handler).handle_request()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code["value"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    print("\nREFRESH TOKEN:\n" + r.json()["refresh_token"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
