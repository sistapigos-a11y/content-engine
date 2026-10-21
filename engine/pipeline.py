"""The daily job, split in 3 stages so GitHub Actions can render EN and ES in parallel:

  write     topic, research, script, review, Spanish adaptation, metadata, shorts  -> work/<job>/job.json
  produce   (per language) voice, visuals, Remotion render, thumbnail, publish     -> work/<job>/<lang>/result.json
  finalize  record the topic + links in state/history.json

Every step is checkpointed, so re-running after a crash continues where it stopped.
"""
import datetime as dt
import os
from pathlib import Path

from . import render, writer
from .llm import LLM
from .uploaders import meta, tiktok, youtube
from .util import ROOT, log, read_json, slugify, write_json

STATE = ROOT / "state" / "history.json"
WORK = ROOT / "work"


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path, {})

    def save(self):
        write_json(self.path, self.data)

    def stage(self, key, fn):
        """Run fn once; reuse its saved result on later runs."""
        if key not in self.data:
            self.data[key] = fn()
            self.save()
        return self.data[key]


def job_name() -> str:
    return os.environ.get("JOB_NAME") or dt.datetime.now().strftime("%Y-%m-%d_%H%M")


def history() -> dict:
    return read_json(STATE, {"topics": [], "published": []})


# --- stage 1 ----------------------------------------------------------------------

def write_stage(cfg: dict, name: str):
    job = Checkpoint(WORK / name / "job.json")
    llm = LLM(cfg)
    idea = job.stage("idea", lambda: writer.pick_topic(llm, cfg, history()["topics"]))
    research = job.stage("research", lambda: writer.gather_research(idea))

    def scripted():
        script = writer.write_long_script(llm, cfg, idea, research)
        q = cfg["quality"]
        for i in range(q["max_rewrites"] + 1):
            review = writer.review_script(llm, cfg, script, research)
            log.info("Script review %d: %.1f/10", i + 1, review.get("overall", 0))
            if review.get("overall", 0) >= q["min_score"] or i == q["max_rewrites"]:
                break
            script = writer.improve_script(llm, cfg, script, review)
        script["review"] = review
        return script

    scripts = {"en": job.stage("script_en", scripted)}
    if "es" in cfg["languages"]:
        scripts["es"] = job.stage("script_es", lambda: writer.adapt_to_spanish(llm, cfg, scripts["en"]))
    for lang in cfg["languages"]:
        job.stage(f"meta_{lang}", lambda: writer.write_metadata(llm, cfg, scripts[lang], idea, lang))
        if cfg["shorts"]["enabled"]:
            job.stage(f"shorts_{lang}", lambda: writer.write_shorts(llm, cfg, scripts[lang], lang))
    log.info("Writing stage done: %s", idea["topic"])


# --- stage 2 ----------------------------------------------------------------------

def produce_stage(cfg: dict, name: str, lang: str, publish: bool = True):
    job = read_json(WORK / name / "job.json")
    if f"script_{lang}" not in job:
        log.info("No %s script in this job, nothing to produce", lang)
        return
    res = Checkpoint(WORK / name / lang / "result.json")
    idea, md, script = job["idea"], job[f"meta_{lang}"], job[f"script_{lang}"]
    base = WORK / name / lang
    slug = slugify(idea["topic"])
    main_person = idea.get("main_person")
    p = cfg["publish"]

    if cfg["long_video"]["enabled"]:
        scenes, chapters = [], {}
        for sec in script["sections"]:
            chapters[len(scenes)] = sec["title"]
            scenes += sec["scenes"]

        def make_long():
            video, srt, credits = render.render(scenes, lang, cfg, "long", base / "long", base / f"{slug}.mp4",
                                                cfg["long_video"]["burn_subtitles"], chapters, main_person)
            thumb = render.thumbnail(idea, md, cfg, video, base / "thumb", base / "thumb.jpg")
            return {"video": str(video), "srt": str(srt), "thumb": str(thumb), "credits": credits}

        files = res.stage("render_long", make_long)
        if publish:
            desc = md["description"] + _credits_block(files["credits"], lang)
            _publish(res, "yt_long", p["youtube"], youtube.available(lang),
                     lambda: youtube.upload(lang, Path(files["video"]), md["title"], desc, md["tags"], cfg,
                                            Path(files["thumb"]), Path(files["srt"])))

    for i, short in enumerate(job.get(f"shorts_{lang}", [])):
        def make_short():
            video, _, credits = render.render(short["scenes"], lang, cfg, "short", base / f"s{i}",
                                              base / f"short_{i + 1}.mp4", True, None, main_person)
            return {"video": str(video), "credits": credits}

        files = res.stage(f"render_short_{i}", make_short)
        if not publish:
            continue
        video = Path(files["video"])
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in short.get("hashtags", []))
        caption = f"{short['caption']}\n\n{tags}".strip()
        full = res.data.get("published", {}).get("yt_long")
        link = (("Full story: " if lang == "en" else "Historia completa: ") + full) if full else ""
        yt_desc = f"{caption}\n\n{link}{_credits_block(files['credits'], lang)}".strip()
        _publish(res, f"yt_short_{i}", p["youtube"] and i < p["youtube_shorts_per_video"], youtube.available(lang),
                 lambda: youtube.upload(lang, video, f"{short['title'][:90]} #Shorts", yt_desc,
                                        short.get("hashtags", []), cfg))
        _publish(res, f"tt_{i}", p["tiktok"], tiktok.available(lang), lambda: tiktok.upload(lang, video, caption))
        _publish(res, f"ig_{i}", p["instagram"], meta.ig_available(lang),
                 lambda: meta.instagram_reel(lang, video, caption))
        _publish(res, f"fb_{i}", p["facebook"], meta.fb_available(lang),
                 lambda: meta.facebook_reel(lang, video, caption))
    log.info("Produce stage done for %s", lang)


def _credits_block(credits: list[str], lang: str) -> str:
    head = "\n\nPhotos:" if lang == "en" else "\n\nFotos:"
    return head + "".join(f"\n• {c}" for c in credits[:15]) if credits else ""


def _publish(res: Checkpoint, key: str, enabled: bool, configured: bool, fn):
    done = res.data.setdefault("published", {})
    if key in done or not enabled:
        return
    if not configured:
        log.info("Skipping %s: credentials not set", key)
        return
    try:
        done[key] = fn()
    except Exception as e:  # noqa: BLE001  one platform failing must not stop the others
        log.error("Publishing %s failed: %s", key, e)
        res.data.setdefault("errors", []).append(f"{key}: {e}")
    res.save()


# --- stage 3 ----------------------------------------------------------------------

def finalize(cfg: dict, name: str):
    job = read_json(WORK / name / "job.json")
    h = history()
    if job["idea"]["topic"] not in h["topics"]:
        h["topics"].append(job["idea"]["topic"])
    links = {lang: read_json(WORK / name / lang / "result.json", {}).get("published", {})
             for lang in ("en", "es") if f"script_{lang}" in job}
    h["published"].append({"job": name, "topic": job["idea"]["topic"], "format": job["idea"]["format"],
                           "links": links})
    write_json(STATE, h)
    log.info("History updated: %s", links)


def run_all(cfg: dict, publish: bool = True):
    name = job_name()
    write_stage(cfg, name)
    for lang in cfg["languages"]:
        produce_stage(cfg, name, lang, publish)
    finalize(cfg, name)
