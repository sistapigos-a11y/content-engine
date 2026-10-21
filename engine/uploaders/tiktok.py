"""TikTok Content Posting API (direct post, chunked file upload)."""
import math
import time
from pathlib import Path

import requests

from ..util import env, log

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024


def available(lang: str) -> bool:
    return all(env(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
                                f"TIKTOK_REFRESH_TOKEN_{lang.upper()}"))


def _token(lang: str) -> str:
    old = env(f"TIKTOK_REFRESH_TOKEN_{lang.upper()}", required=True)
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": env("TIKTOK_CLIENT_KEY", required=True),
        "client_secret": env("TIKTOK_CLIENT_SECRET", required=True),
        "grant_type": "refresh_token", "refresh_token": old}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("refresh_token") and data["refresh_token"] != old:
        log.warning("TikTok issued a new refresh token for %s; update the secret before it expires.", lang)
    return data["access_token"]


def upload(lang: str, video: Path, caption: str) -> str:
    token = _token(lang)
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    size = video.stat().st_size
    chunk = min(CHUNK, size)
    count = max(1, size // chunk)  # TikTok: last chunk absorbs the remainder
    # Apps that have not passed TikTok's audit can only post as SELF_ONLY
    privacy = env("TIKTOK_PRIVACY") or "SELF_ONLY"
    r = requests.post(f"{API}/post/publish/video/init/", headers=auth, json={
        "post_info": {"title": caption[:2200], "privacy_level": privacy,
                      "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                      "is_aigc": True},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                        "chunk_size": chunk, "total_chunk_count": count}}, timeout=60)
    r.raise_for_status()
    data = r.json()["data"]
    url, publish_id = data["upload_url"], data["publish_id"]

    with open(video, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            body = f.read(end - start + 1)
            requests.put(url, data=body, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{size}"}).raise_for_status()

    for _ in range(60):
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=auth,
                          json={"publish_id": publish_id}, timeout=30).json()["data"]
        if s.get("status") == "PUBLISH_COMPLETE":
            log.info("TikTok[%s] published (%s)", lang, publish_id)
            return publish_id
        if s.get("status") == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {s}")
        time.sleep(10)
    log.warning("TikTok[%s] still processing (%s)", lang, publish_id)
    return publish_id
