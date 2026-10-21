"""End-to-end daily job. Each stage is checkpointed in work/<job>/job.json so a crash resumes."""
import datetime as dt
from pathlib import Path

from . import render, writer
from .llm import LLM
from .uploaders import meta, tiktok, youtube
from .util import ROOT, log, read_json, slugify, write_json

STATE = ROOT / "state" / "history.json"
WORK = ROOT / "work"


class Job:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path / "job.json", {})

    def save(self):
        write_json(self.path / "job.json", self.data)

    def stage(self, key, fn):
        """Run fn once; reuse its saved result on later runs."""
        if key not in self.data:
            self.data[key] = fn()
            self.save()
        return self.data[key]


def _open_job(history) -> Job:
    unfinished = history.get("in_progress")
    if unfinished and (WORK / unfinished / "job.json").exists():
        log.info("Resuming unfinished job %s", unfinished)
        return Job(WORK / unfinished)
    name = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    job = Job(WORK / name)
    job.path.mkdir(parents=True, exist_ok=True)
    history["in_progress"] = name
    write_json(STATE, history)
    return job


def run(cfg: dict, publish: bool = True):
    history = read_json(STATE, {"topics": [], "published": []})
    llm = LLM(cfg)
    job = _open_job(history)

    idea = job.stage("idea", lambda: writer.pick_topic(llm, cfg, history["topics"]))

    def scripted():
        script = writer.write_long_script(llm, cfg, idea)
        q = cfg["quality"]
        for i in range(q["max_rewrites"] + 1):
            review = writer.review_script(llm, cfg, script)
            log.info("Script review %d: %.1f/10", i + 1, review.get("overall", 0))
            if review.get("overall", 0) >= q["min_score"] or i == q["max_rewrites"]:
                break
            script = writer.improve_script(llm, cfg, script, review)
        script["review"] = review
        return script

    scripts = {"en": job.stage("script_en", scripted)}
    if "es" in cfg["languages"]:
        scripts["es"] = job.stage("script_es", lambda: writer.adapt_to_spanish(llm, cfg, scripts["en"]))

    slug = slugify(idea["topic"])
    for lang, lang_cfg in cfg["languages"].items():
        script = scripts[lang]
        md = job.stage(f"meta_{lang}", lambda: writer.write_metadata(llm, cfg, script, lang))

        # ---- long video -> YouTube
        if cfg["long_video"]["enabled"]:
            scenes = [sc for sec in script["sections"] for sc in sec["scenes"]]
            out = job.path / lang / f"{slug}.mp4"

            def make_long():
                video, srt = render.render(scenes, lang_cfg, cfg, "long", job.path / lang / "long",
                                           out, cfg["long_video"]["burn_subtitles"])
                thumb = render.thumbnail(video, md["thumbnail_text"], job.path / lang / "thumb.jpg")
                return {"video": str(video), "srt": str(srt), "thumb": str(thumb)}

            files = job.stage(f"render_long_{lang}", make_long)
            if publish:
                _publish(job, f"yt_long_{lang}", cfg["publish"]["youtube"], youtube.available(lang),
                         lambda: youtube.upload(lang, Path(files["video"]), md["title"], md["description"],
                                                md["tags"], cfg, Path(files["thumb"]), Path(files["srt"])))

        # ---- shorts -> YouTube Shorts, TikTok, Instagram, Facebook
        if cfg["shorts"]["enabled"]:
            shorts = job.stage(f"shorts_{lang}", lambda: writer.write_shorts(llm, cfg, script, lang))
            for i, short in enumerate(shorts):
                out = job.path / lang / f"short_{i + 1}.mp4"
                files = job.stage(f"render_short_{lang}_{i}", lambda: {"video": str(render.render(
                    short["scenes"], lang_cfg, cfg, "short", job.path / lang / f"s{i}", out, True)[0])})
                if not publish:
                    continue
                video = Path(files["video"])
                tags = " ".join(h if h.startswith("#") else f"#{h}" for h in short.get("hashtags", []))
                caption = f"{short['caption']}\n\n{tags}".strip()
                yt_desc = f"{caption}\n\n{_full_video_line(job, lang)}".strip()
                p = cfg["publish"]
                _publish(job, f"yt_short_{lang}_{i}", p["youtube"] and i < p["youtube_shorts_per_video"],
                         youtube.available(lang),
                         lambda: youtube.upload(lang, video, f"{short['title'][:90]} #Shorts", yt_desc,
                                                short.get("hashtags", []), cfg))
                _publish(job, f"tt_{lang}_{i}", p["tiktok"], tiktok.available(lang),
                         lambda: tiktok.upload(lang, video, caption))
                _publish(job, f"ig_{lang}_{i}", p["instagram"], meta.ig_available(lang),
                         lambda: meta.instagram_reel(lang, video, caption))
                _publish(job, f"fb_{lang}_{i}", p["facebook"], meta.fb_available(lang),
                         lambda: meta.facebook_reel(lang, video, caption))

    history["topics"].append(idea["topic"])
    history["published"].append({"date": job.path.name, "topic": idea["topic"],
                                 "links": job.data.get("published", {})})
    history.pop("in_progress", None)
    write_json(STATE, history)
    log.info("All done for %s", idea["topic"])


def _full_video_line(job, lang):
    link = job.data.get("published", {}).get(f"yt_long_{lang}")
    if not link:
        return ""
    return ("Full documentary: " if lang == "en" else "Documental completo: ") + str(link)


def _publish(job: Job, key: str, enabled: bool, configured: bool, fn):
    done = job.data.setdefault("published", {})
    if key in done or not enabled:
        return
    if not configured:
        log.info("Skipping %s: credentials not set", key)
        return
    try:
        done[key] = fn()
    except Exception as e:  # noqa: BLE001  one platform failing must not stop the others
        log.error("Publishing %s failed: %s", key, e)
        job.data.setdefault("errors", []).append(f"{key}: {e}")
    job.save()
