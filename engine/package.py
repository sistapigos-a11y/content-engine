"""Script + voice package for editing on your own PC (config: output: package).

work/<job>/<lang>/package/
  README.txt            what is in here
  script.md             the full script, chapter by chapter, with visual notes per scene
  metadata.md / .json   title, description, tags, thumbnail words
  voice.wav             full narration in your cloned voice (-14 LUFS)
  voice.srt             subtitles
  timeline.json         every scene with start/end seconds, narration, visual idea, chapter
  words.json            every word with start/end seconds (for animated captions)
  scenes/NNN.wav        one file per scene, if you prefer to place them yourself
  shorts/short_N.*      same set for each Short (wav, srt, timeline, words, script)
"""
import json
import shutil
from pathlib import Path

from . import captions
from .render import _voiceover
from .util import log, write_json

PACKAGE_README = """Package: {topic}
Language: {lang}

voice.wav       full narration ({minutes:.1f} min)
timeline.json   scenes with start/end seconds (use it to place visuals in Remotion)
words.json      word timings for captions
voice.srt       subtitles
script.md       readable script with visual ideas
metadata.md     title / description / tags / thumbnail words
scenes/         one wav per scene
shorts/         the Shorts, same structure
"""


def _timeline(scenes, bounds, chapters=None):
    out = []
    for i, (sc, (start, end)) in enumerate(zip(scenes, bounds)):
        item = {"index": i, "start": round(start, 3), "end": round(end, 3),
                "narration": sc["narration"], "type": sc.get("type"), "query": sc.get("query"),
                "person": sc.get("person"), "onscreen": sc.get("onscreen")}
        if chapters and i in chapters:
            item["chapter"] = chapters[i]
        out.append(item)
    return out


def _script_md(title, sections) -> str:
    lines = [f"# {title}\n"]
    for n, sec in enumerate(sections, 1):
        lines.append(f"\n## {n}. {sec['title']}\n")
        for sc in sec["scenes"]:
            visual = sc.get("onscreen") or sc.get("person") or sc.get("query") or ""
            lines.append(f"{sc['narration']}\n\n> 🎬 {sc.get('type', 'broll')}: {visual}\n")
    return "\n".join(lines)


def _voice_set(scenes, lang, cfg, workdir: Path, dest: Path, chapters=None):
    """Synthesize, then copy voice + timings into dest. Returns duration in seconds."""
    voice, words, bounds = _voiceover(scenes, lang, cfg, workdir)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(voice, dest / "voice.wav")
    captions.write_srt(words, dest / "voice.srt")
    write_json(dest / "timeline.json", _timeline(scenes, bounds, chapters))
    write_json(dest / "words.json", words)
    (dest / "scenes").mkdir(exist_ok=True)
    for i in range(len(scenes)):
        src = workdir / json.loads((workdir / f"vo_{i:03}.json").read_text())["audio"]
        shutil.copy(src, dest / "scenes" / f"{i:03}{src.suffix}")
    return bounds[-1][1]


def build(job: dict, lang: str, cfg: dict, base: Path, res) -> Path:
    """Voice + files for the long video and every Short. Checkpointed per part."""
    idea, md, script = job["idea"], job[f"meta_{lang}"], job[f"script_{lang}"]
    pkg = base / "package"
    pkg.mkdir(parents=True, exist_ok=True)

    (pkg / "script.md").write_text(_script_md(md["title"], script["sections"]), encoding="utf-8")
    write_json(pkg / "metadata.json", md)
    (pkg / "metadata.md").write_text(
        f"# {md['title']}\n\n## Description\n{md['description']}\n\n## Tags\n{', '.join(md['tags'])}\n\n"
        f"## Thumbnail\n{md['thumb_left']}  [person: {idea.get('main_person') or '-'}]  {md['thumb_right']}\n"
        f"Second person: {idea.get('secondary_person') or '-'}\n", encoding="utf-8")

    if cfg["long_video"]["enabled"]:
        scenes, chapters = [], {}
        for sec in script["sections"]:
            chapters[len(scenes)] = sec["title"]
            scenes += sec["scenes"]
        secs = res.stage("voice_long", lambda: _voice_set(scenes, lang, cfg, base / "long", pkg, chapters))
        log.info("Long voice ready: %.1f min", secs / 60)
        (pkg / "README.txt").write_text(PACKAGE_README.format(topic=idea["topic"], lang=lang, minutes=secs / 60),
                                        encoding="utf-8")

    for i, short in enumerate(job.get(f"shorts_{lang}", [])):
        dest = pkg / "shorts" / f"short_{i + 1}"
        res.stage(f"voice_short_{i}", lambda: _voice_set(short["scenes"], lang, cfg, base / f"s{i}", dest))
        (dest / "script.md").write_text(
            f"# {short['title']}\n\n{short['caption']}\n\n{' '.join('#' + h.lstrip('#') for h in short.get('hashtags', []))}\n\n"
            + "\n\n".join(f"{sc['narration']}\n> 🎬 {sc.get('type', 'broll')}: "
                          f"{sc.get('onscreen') or sc.get('person') or sc.get('query') or ''}" for sc in short["scenes"]),
            encoding="utf-8")
    log.info("Package ready: %s", pkg)
    return pkg
