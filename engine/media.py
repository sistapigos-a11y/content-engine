"""Royalty-free stock footage from Pexels / Pixabay."""
import hashlib
from pathlib import Path

import requests

from .util import env, log

CACHE = Path("work/cache/media")


def _download(url: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".mp4")
    if not path.exists():
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = path.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.rename(path)
    return path


def _pexels(query, portrait):
    key = env("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                     params={"query": query, "per_page": 8,
                             "orientation": "portrait" if portrait else "landscape"}, timeout=30)
    r.raise_for_status()
    urls = []
    for v in r.json().get("videos", []):
        files = [f for f in v["video_files"] if f.get("width") and f.get("file_type") == "video/mp4"]
        # smallest file that is still at least HD on its short side
        good = sorted([f for f in files if min(f["width"], f["height"]) >= 720],
                      key=lambda f: f["width"] * f["height"])
        if good:
            urls.append(good[0]["link"])
    return urls


def _pixabay(query, portrait):
    key = env("PIXABAY_API_KEY")
    if not key:
        return []
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": key, "q": query[:100], "per_page": 8, "safesearch": "true"}, timeout=30)
    r.raise_for_status()
    urls = []
    for hit in r.json().get("hits", []):
        v = hit["videos"].get("medium") or hit["videos"].get("large")
        if v and v.get("url"):
            urls.append(v["url"])
    return urls


SOURCES = {"pexels": _pexels, "pixabay": _pixabay}


class MediaPicker:
    """Finds clips for a query and avoids reusing the same clip within one video."""

    def __init__(self, cfg, portrait: bool):
        self.sources = cfg["media"]["sources"]
        self.portrait = portrait
        self.used: set[str] = set()

    def clips(self, query: str, n: int) -> list[Path]:
        candidates = []
        for q in (query, " ".join(query.split()[:2])):  # broaden if nothing found
            for name in self.sources:
                try:
                    candidates += SOURCES[name](q, self.portrait)
                except Exception as e:  # noqa: BLE001
                    log.warning("%s search failed for %r: %s", name, q, e)
            if candidates:
                break
        fresh = [u for u in candidates if u not in self.used] or candidates
        picked = []
        for url in fresh[:n]:
            try:
                picked.append(_download(url))
                self.used.add(url)
            except Exception as e:  # noqa: BLE001
                log.warning("download failed: %s", e)
        return picked

