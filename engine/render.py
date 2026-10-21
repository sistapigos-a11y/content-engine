"""Bridge to the Remotion project in video/: builds the voiceover, picks visuals for every
scene, writes props.json and renders with `remotion render` / `remotion still`."""
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

from . import captions, people, tts
from .media import MediaPicker
from .util import ROOT, log, media_duration, run

FPS = 30
FORMATS = {"long": (1920, 1080), "short": (1080, 1920)}
VIDEO_DIR = ROOT / "video"
PHOTO_SECONDS = 4.0  # a still photo stays on screen at most this long


def remotion(args: list[str]):
    cmd = ["npx", "remotion", *args, "--log=warn"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    proc = subprocess.run(cmd, cwd=VIDEO_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Remotion failed:\n{(proc.stdout + proc.stderr)[-3000:]}")


class Assets:
    """Copies everything Remotion needs into the job's public dir and remembers photo credits."""

    def __init__(self, public: Path, cfg: dict, kind: str):
        self.public = public
        (public / "assets").mkdir(parents=True, exist_ok=True)
        self.stock = MediaPicker(cfg, portrait=kind == "short")
        self.max_clip = cfg["media"]["clip_max_seconds"] if kind == "long" else 3.0
        self._photos: dict[str, list[dict]] = {}
        self._photo_turn: dict[str, int] = {}
        self.credits: set[str] = set()

    def _place(self, src: Path) -> str:
        dst = self.public / "assets" / src.name
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy(src, dst)
        return f"assets/{src.name}"

    def person_photos(self, name: str) -> list[dict]:
        if name not in self._photos:
            self._photos[name] = people.photos(name)
        return self._photos[name]

    def photo_shots(self, name: str, frames: int) -> list[dict]:
        pics = self.person_photos(name) if name else []
        if not pics:
            return []
        n = max(1, round(frames / (PHOTO_SECONDS * FPS) + 0.49))
        shots = []
        for k in range(n):
            turn = self._photo_turn.get(name, 0)
            self._photo_turn[name] = turn + 1
            pic = pics[turn % len(pics)]  # rotate so the same photo doesn't repeat back to back
            self.credits.add(pic["credit"])
            shots.append({"src": self._place(pic["path"]), "kind": "image", "durationInFrames": 0})
        return _spread(shots, frames)

    def broll_shots(self, query: str, frames: int) -> list[dict]:
        n = max(1, round(frames / (self.max_clip * FPS) + 0.49))
        clips = self.stock.clips(query, n)
        if not clips:
            return []
        shots, left, i = [], frames, 0
        while left > 0:
            clip = clips[i % len(clips)]
            usable = int(min(self.max_clip, media_duration(clip) - 0.1) * FPS)
            take = max(1, min(left, usable))
            shots.append({"src": self._place(clip), "kind": "video", "durationInFrames": take})
            left -= take
            i += 1
        return shots

    def scene_shots(self, sc: dict, frames: int, main_person: str | None) -> list[dict]:
        kind = sc.get("type", "broll")
        person = sc.get("person") or None
        order = {
            "photo": [("photo", person), ("broll", sc.get("query")), ("photo", main_person)],
            "broll": [("broll", sc.get("query")), ("photo", person), ("photo", main_person)],
            "text": [("broll", sc.get("query")), ("photo", person or main_person)],
            "quote": [("photo", person), ("broll", sc.get("query"))],
        }.get(kind, [("broll", sc.get("query"))])
        for how, what in order:
            if not what:
                continue
            shots = self.photo_shots(what, frames) if how == "photo" else self.broll_shots(what, frames)
            if shots:
                return shots
        return []  # Remotion draws a dark gradient


def _spread(shots: list[dict], frames: int) -> list[dict]:
    base, extra = divmod(frames, len(shots))
    for i, s in enumerate(shots):
        s["durationInFrames"] = base + (1 if i < extra else 0)
    return shots


def _voiceover(scenes, lang, cfg, workdir: Path):
    """Per-scene audio -> one loudness-normalised track. Returns (voice.wav, words, bounds)."""
    words, bounds, parts, t = [], [], [], 0.0
    for i, sc in enumerate(scenes):
        raw, ws = tts.synthesize(sc["narration"], lang, cfg, workdir / f"vo_{i:03}")
        dur = media_duration(raw) + 0.25  # a breath between scenes
        words += [{**w, "start": w["start"] + t, "end": w["end"] + t} for w in ws]
        bounds.append((t, t + dur))
        wav = workdir / f"vo_{i:03}_pad.wav"
        run(["ffmpeg", "-y", "-i", str(raw), "-af", f"apad=whole_dur={dur:.3f}", "-ar", "44100", "-ac", "2", str(wav)])
        parts.append(wav)
        t += dur
    listfile = workdir / "vo_list.txt"
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    joined = workdir / "voice_raw.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(joined)])
    voice = tts.normalize_loudness(joined, workdir / "voice.wav")
    for p in parts:
        p.unlink(missing_ok=True)
    return voice, words, bounds


def render(scenes: list[dict], lang: str, cfg: dict, kind: str, workdir: Path, out: Path,
           burn_captions: bool, chapters: dict[int, str] | None = None, main_person: str | None = None):
    """Returns (video, srt, photo_credits)."""
    workdir.mkdir(parents=True, exist_ok=True)
    log.info("Rendering %s video (%d scenes) -> %s", kind, len(scenes), out)
    voice, words, bounds = _voiceover(scenes, lang, cfg, workdir)
    assets = Assets(workdir, cfg, kind)
    w, h = FORMATS[kind]

    props_scenes = []
    for i, (sc, (start, end)) in enumerate(zip(scenes, bounds)):
        f0, f1 = round(start * FPS), round(end * FPS)  # absolute frames: no rounding drift
        scene = {"from": f0, "durationInFrames": f1 - f0, "type": sc.get("type", "broll"),
                 "shots": assets.scene_shots(sc, f1 - f0, main_person),
                 "onscreen": sc.get("onscreen"), "person": sc.get("person")}
        if scene["type"] in ("text", "quote") and not sc.get("onscreen"):
            scene["type"] = "broll"
        if chapters and i in chapters:
            scene["chapter"] = {"index": list(chapters).index(i) + 1, "title": chapters[i]}
        props_scenes.append(scene)

    tracks = list((ROOT / "assets" / "music").glob("*.mp3"))
    music = assets._place(random.choice(tracks)) if tracks else None
    total = round(bounds[-1][1] * FPS)
    props = {
        "width": w, "height": h, "fps": FPS, "durationInFrames": total,
        "voice": voice.name, "music": music, "musicVolume": cfg["media"]["music_volume"],
        "scenes": props_scenes, "captions": burn_captions,
        "words": [{"text": x["word"], "startMs": int(x["start"] * 1000), "endMs": int(x["end"] * 1000)} for x in words],
        "accent": cfg["style"]["accent"], "chapterLabel": cfg["style"]["chapter_label"][lang],
    }
    props_file = workdir / "props.json"
    props_file.write_text(json.dumps(props, ensure_ascii=False))

    out.parent.mkdir(parents=True, exist_ok=True)
    remotion(["render", "src/index.ts", "Video", str(out.resolve()), f"--props={props_file.resolve()}",
              f"--public-dir={workdir.resolve()}", "--codec=h264", "--crf=20"])
    srt = captions.write_srt(words, out.with_suffix(".srt"))
    log.info("Done: %s (%.1f s)", out, media_duration(out))
    return out, srt, sorted(assets.credits)


def thumbnail(idea: dict, md: dict, cfg: dict, video: Path, workdir: Path, out: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)

    def cut(name, tag):
        if not name:
            return None
        for i, pic in enumerate(people.photos(name)[:4]):  # first photo that cuts out cleanly
            res = people.cutout(pic["path"], workdir / f"{tag}_{i}.png")
            if res:
                return res.name
        return None

    main = cut(idea.get("main_person"), "main")
    secondary = cut(idea.get("secondary_person"), "second") if main else None
    background = None
    if not main:  # no person: use a frame of the video itself
        frame = workdir / "bg.jpg"
        run(["ffmpeg", "-y", "-ss", f"{min(20, media_duration(video) / 4):.1f}", "-i", str(video),
             "-frames:v", "1", str(frame)])
        background = frame.name
    props = {"left": md["thumb_left"], "right": md["thumb_right"], "main": main, "secondary": secondary,
             "background": background, "accent": cfg["style"]["accent"]}
    pf = workdir / "thumb_props.json"
    pf.write_text(json.dumps(props, ensure_ascii=False))
    remotion(["still", "src/index.ts", "Thumbnail", str(out.resolve()), f"--props={pf.resolve()}",
              f"--public-dir={workdir.resolve()}", "--image-format=jpeg", "--jpeg-quality=92"])
    return out
