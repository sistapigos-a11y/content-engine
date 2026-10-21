"""YouTube Data API v3 upload with an OAuth refresh token (one per channel/language)."""
import json
from pathlib import Path

import requests

from ..util import env, log, retry

API = "https://www.googleapis.com"


def _token(lang: str) -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("YT_CLIENT_ID", required=True),
        "client_secret": env("YT_CLIENT_SECRET", required=True),
        "refresh_token": env(f"YT_REFRESH_TOKEN_{lang.upper()}", required=True),
        "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def available(lang: str) -> bool:
    return all(env(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", f"YT_REFRESH_TOKEN_{lang.upper()}"))


def upload(lang: str, video: Path, title: str, description: str, tags: list[str], cfg: dict,
           thumbnail: Path | None = None, srt: Path | None = None) -> str:
    pub = cfg["publish"]
    token = _token(lang)
    auth = {"Authorization": f"Bearer {token}"}
    meta = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:30],
                    "categoryId": pub["youtube_category"], "defaultLanguage": lang,
                    "defaultAudioLanguage": lang},
        "status": {"privacyStatus": pub["youtube_privacy"], "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": bool(pub.get("ai_disclosure", True))},
    }

    def start():
        r = requests.post(f"{API}/upload/youtube/v3/videos",
                          params={"uploadType": "resumable", "part": "snippet,status"},
                          headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                                   "X-Upload-Content-Type": "video/mp4",
                                   "X-Upload-Content-Length": str(video.stat().st_size)},
                          data=json.dumps(meta), timeout=60)
        r.raise_for_status()
        return r.headers["Location"]

    session = retry(start, what="youtube init")

    def send():
        with open(video, "rb") as f:
            r = requests.put(session, headers={**auth, "Content-Type": "video/mp4"}, data=f, timeout=3600)
        r.raise_for_status()
        return r.json()["id"]

    vid = retry(send, what="youtube upload")
    log.info("YouTube[%s] uploaded: https://youtu.be/%s", lang, vid)

    if thumbnail and thumbnail.exists():
        try:
            with open(thumbnail, "rb") as f:
                requests.post(f"{API}/upload/youtube/v3/thumbnails/set", params={"videoId": vid},
                              headers={**auth, "Content-Type": "image/jpeg"}, data=f,
                              timeout=120).raise_for_status()
        except Exception as e:  # noqa: BLE001  (needs a phone-verified channel)
            log.warning("Thumbnail upload failed: %s", e)

    if srt and srt.exists():
        try:
            boundary = "captionboundary"
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                    + json.dumps({"snippet": {"videoId": vid, "language": lang, "name": ""}})
                    + f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n"
                    ).encode() + srt.read_bytes() + f"\r\n--{boundary}--".encode()
            requests.post(f"{API}/upload/youtube/v3/captions",
                          params={"part": "snippet", "uploadType": "multipart"},
                          headers={**auth, "Content-Type": f"multipart/related; boundary={boundary}"},
                          data=body, timeout=120).raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("Caption upload failed: %s", e)
    return f"https://youtu.be/{vid}"
