"""Who is trending right now? Free signals: Wikipedia most-viewed pages + Google Trends RSS."""
import datetime as dt
import re
import xml.etree.ElementTree as ET

import requests

from .util import log

UA = {"User-Agent": "content-engine/1.0 (https://github.com/; automated research)"}
SKIP = re.compile(r"^(Main_Page|Special:|Wikipedia:|Portal:|File:|Help:|Template:|Category:|Talk:|"
                  r"Página_principal|Especial:|Anexo:)")


def wikipedia_top(lang: str, limit: int = 120) -> list[dict]:
    for days_back in (1, 2):
        day = dt.date.today() - dt.timedelta(days=days_back)
        url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/"
               f"{day:%Y/%m/%d}")
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            arts = r.json()["items"][0]["articles"]
            return [{"title": a["article"].replace("_", " "), "views": a["views"], "source": f"wikipedia-{lang}"}
                    for a in arts if not SKIP.match(a["article"])][:limit]
        except Exception as e:  # noqa: BLE001
            log.warning("Wikipedia top (%s) failed: %s", lang, e)
            return []
    return []


def google_trends(geo: str) -> list[dict]:
    try:
        r = requests.get(f"https://trends.google.com/trending/rss?geo={geo}", headers=UA, timeout=30)
        r.raise_for_status()
        ns = {"ht": "https://trends.google.com/trending/rss"}
        out = []
        for item in ET.fromstring(r.content).iter("item"):
            news = [n.findtext("ht:news_item_title", default="", namespaces=ns)
                    for n in item.findall("ht:news_item", ns)]
            out.append({"title": item.findtext("title"), "traffic": item.findtext("ht:approx_traffic", namespaces=ns),
                        "news": [n for n in news if n][:2], "source": f"google-trends-{geo}"})
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("Google Trends (%s) failed: %s", geo, e)
        return []


def collect(cfg: dict) -> list[dict]:
    t = cfg["channel"]["trending"]
    signals = []
    for lang in t.get("wikipedia", ["en", "es"]):
        signals += wikipedia_top(lang)
    for geo in t.get("google_trends_geos", ["US", "MX", "ES"]):
        signals += google_trends(geo)
    log.info("Collected %d trend signals", len(signals))
    return signals
