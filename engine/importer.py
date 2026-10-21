"""Turn a ready-made Markdown script (like output/*.md) into a job, so it gets the same
voice + package treatment as the scripts the system writes itself.

Format: "# Title", chapters as "## N. Chapter title", narration paragraphs.
Ignored: *[visual notes]*, > quotes, **bold meta lines**, tables, ---, and everything from "## ⚠️" on.
"""
import re
from pathlib import Path

from .util import log, write_json


def parse(md: str) -> tuple[str, list[dict]]:
    md = md.split("\n## ⚠️")[0]
    title = (re.search(r"^# (.+)$", md, re.M) or [None, "Untitled"])[1].strip()
    sections, cur = [], None
    for block in re.split(r"\n\s*\n", md):
        block = block.strip()
        if not block:
            continue
        head = re.match(r"^## (?:\d+\.\s*)?(.+)$", block)
        if head:
            cur = {"title": head.group(1).split("—")[-1].strip(), "scenes": []}
            sections.append(cur)
            continue
        if cur is None or re.match(r"^(#|\*\[|>|\*\*|\||---)", block):
            continue
        text = re.sub(r"\*\[.*?\]\*", "", block)            # inline visual notes
        text = re.sub(r"[*_`]", "", text).replace("\n", " ").strip()
        if text:
            cur["scenes"].append({"narration": text, "type": "broll", "query": "", "person": None, "onscreen": None})
    return title, [s for s in sections if s["scenes"]]


def import_script(path: Path, lang: str, job_dir: Path) -> None:
    title, sections = parse(path.read_text(encoding="utf-8"))
    words = sum(len(sc["narration"].split()) for s in sections for sc in s["scenes"])
    log.info("Imported '%s': %d chapters, %d words (~%.0f min)", title, len(sections), words, words / 140)
    write_json(job_dir / "job.json", {
        "idea": {"topic": title, "angle": "", "format": "imported", "main_person": None},
        f"script_{lang}": {"topic": title, "angle": "", "format": "imported", "sections": sections},
        f"meta_{lang}": {"title": title, "description": "", "tags": [], "thumb_left": "", "thumb_right": ""},
        f"shorts_{lang}": [],
    })
