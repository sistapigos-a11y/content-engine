"""Research (Wikipedia text) and freely-licensed photos (Wikimedia Commons) for a story,
plus background-removed cut-outs of people for the thumbnail."""
import hashlib
import re
from pathlib import Path

import requests

from .trends import UA
from .util import log

CACHE = Path("work/cache/people")


def _api(lang: str, **params) -> dict:
    params |= {"format": "json", "formatversion": 2}
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def research(title: str, lang: str = "en", max_chars: int = 30000) -> str:
    """Plain-text article: grounds the script in real facts instead of model memory."""
    try:
        pages = _api(lang, action="query", prop="extracts", explaintext=1, redirects=1, titles=title)["query"]["pages"]
        text = pages[0].get("extract", "")
        text = re.split(r"\n==\s*(References|See also|External links|Notes|Referencias|Véase también)\s*==", text)[0]
        return text[:max_chars]
    except Exception as e:  # noqa: BLE001
        log.warning("Wikipedia research failed for %s: %s", title, e)
        return ""


def _commons_images(query: str, limit: int) -> list[dict]:
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
        "action": "query", "format": "json", "formatversion": 2, "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit * 3,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1920})
    r.raise_for_status()
    out = []
    for p in r.json().get("query", {}).get("pages", []):
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if info.get("width", 0) < 600 or not lic or "fair use" in lic.lower():
            continue
        artist = re.sub("<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        out.append({"url": info.get("thumburl") or info["url"], "credit": f"{artist or 'Unknown'} / {lic} / Wikimedia Commons",
                    "title": p["title"]})
    return out[:limit]


def photos(name: str, limit: int = 8) -> list[dict]:
    """Main Wikipedia photo first, then more Commons photos. Returns [{path, credit}]."""
    found = []
    try:
        pages = _api("en", action="query", prop="pageimages", piprop="original", redirects=1, titles=name)["query"]["pages"]
        orig = pages[0].get("original")
        if orig:
            found.append({"url": orig["source"], "credit": "Wikimedia Commons"})
    except Exception as e:  # noqa: BLE001
        log.warning("pageimage failed for %s: %s", name, e)
    try:
        found += _commons_images(name, limit)
    except Exception as e:  # noqa: BLE001
        log.warning("Commons search failed for %s: %s", name, e)

    CACHE.mkdir(parents=True, exist_ok=True)
    out, seen = [], set()
    for f in found:
        if f["url"] in seen:
            continue
        seen.add(f["url"])
        ext = Path(f["url"].split("?")[0]).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        path = CACHE / (hashlib.md5(f["url"].encode()).hexdigest() + ext)
        try:
            if not path.exists():
                r = requests.get(f["url"], headers=UA, timeout=60)
                r.raise_for_status()
                path.write_bytes(r.content)
            out.append({"path": path, "credit": f["credit"]})
        except Exception as e:  # noqa: BLE001
            log.warning("photo download failed: %s", e)
        if len(out) >= limit:
            break
    return out


def cutout(image: Path, out: Path) -> Path | None:
    """Remove the background (rembg) and crop to the person, for thumbnails."""
    try:
        from PIL import Image
        from rembg import new_session, remove

        img = Image.open(image).convert("RGB")
        cut = remove(img, session=new_session("u2net_human_seg"))
        bbox = cut.getbbox()
        if not bbox:
            return None
        cut.crop(bbox).save(out)
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("cutout failed for %s: %s", image, e)
        return None
