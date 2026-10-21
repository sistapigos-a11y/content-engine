"""Instagram Reels and Facebook Page Reels via the Graph API (resumable binary upload)."""
import time
from pathlib import Path

import requests

from ..util import env, log

GRAPH = "https://graph.facebook.com/v21.0"


def ig_available(lang: str) -> bool:
    return bool(env(f"META_TOKEN_{lang.upper()}") and env(f"IG_USER_ID_{lang.upper()}"))


def fb_available(lang: str) -> bool:
    return bool(env(f"META_TOKEN_{lang.upper()}") and env(f"FB_PAGE_ID_{lang.upper()}"))


def _push(upload_url: str, token: str, video: Path):
    with open(video, "rb") as f:
        requests.post(upload_url, data=f, timeout=900, headers={
            "Authorization": f"OAuth {token}", "offset": "0",
            "file_size": str(video.stat().st_size)}).raise_for_status()


def instagram_reel(lang: str, video: Path, caption: str) -> str:
    token = env(f"META_TOKEN_{lang.upper()}", required=True)
    user = env(f"IG_USER_ID_{lang.upper()}", required=True)
    r = requests.post(f"{GRAPH}/{user}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
        "share_to_feed": "true", "access_token": token})
    r.raise_for_status()
    container = r.json()["id"]
    _push(r.json()["uri"], token, video)

    for _ in range(60):
        status = requests.get(f"{GRAPH}/{container}", timeout=30,
                              params={"fields": "status_code", "access_token": token}).json()
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing error: {status}")
        time.sleep(10)
    r = requests.post(f"{GRAPH}/{user}/media_publish", timeout=60,
                      data={"creation_id": container, "access_token": token})
    r.raise_for_status()
    log.info("Instagram[%s] published %s", lang, r.json()["id"])
    return r.json()["id"]


def facebook_reel(lang: str, video: Path, caption: str) -> str:
    token = env(f"META_TOKEN_{lang.upper()}", required=True)
    page = env(f"FB_PAGE_ID_{lang.upper()}", required=True)
    r = requests.post(f"{GRAPH}/{page}/video_reels", timeout=60,
                      data={"upload_phase": "start", "access_token": token})
    r.raise_for_status()
    vid = r.json()["video_id"]
    _push(r.json()["upload_url"], token, video)
    r = requests.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": caption[:2200], "access_token": token})
    r.raise_for_status()
    log.info("Facebook[%s] published reel %s", lang, vid)
    return vid
