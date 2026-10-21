"""Readable Markdown scripts (one per language + Shorts) from a job, ready to record.

The format is the same one engine/importer.py reads, so any exported script can also be
voiced later with the workflow's `script` input.
"""
import datetime as dt
from pathlib import Path

from .util import log, slugify


def _visual(sc: dict) -> str:
    kind = sc.get("type") or "broll"
    what = sc.get("onscreen") or sc.get("person") or sc.get("query") or ""
    return f"*[{kind}: {what}]*" if what else ""


def long_md(job: dict, lang: str) -> str:
    md, script, idea = job[f"meta_{lang}"], job[f"script_{lang}"], job["idea"]
    words = sum(len(sc["narration"].split()) for s in script["sections"] for sc in s["scenes"])
    review = script.get("review") or job.get("script_en", {}).get("review") or {}
    out = [
        f"# {md['title']}\n",
        f"**{'Length' if lang == 'en' else 'Duración'}:** ~{words:,} words ≈ {words / 140:.0f} min",
        f"**Thumbnail:** `{md.get('thumb_left', '')}` [{idea.get('main_person') or '-'}] `{md.get('thumb_right', '')}`"
        + (f" · second person: {idea['secondary_person']}" if idea.get("secondary_person") else ""),
        f"**Tags:** {', '.join(md.get('tags', []))}",
    ]
    if review.get("overall") is not None:
        out.append(f"**AI review:** {review['overall']}/10")
    out += ["", "**Description:**", "", md.get("description", ""), "", "---", ""]
    for n, sec in enumerate(script["sections"], 1):
        out += [f"## {n}. {sec['title']}", ""]
        for sc in sec["scenes"]:
            v = _visual(sc)
            if v:
                out += [v, ""]
            out += [sc["narration"], ""]
        out += ["---", ""]
    risks = review.get("factual_risks") or []
    if risks and lang == "en":
        out += ["## ⚠️ Fact-check before recording", ""] + [f"- {r}" for r in risks] + [""]
    return "\n".join(out)


def shorts_md(job: dict, lang: str) -> str:
    out = [f"# Shorts — {job[f'meta_{lang}']['title']}", ""]
    for i, short in enumerate(job.get(f"shorts_{lang}", []), 1):
        tags = " ".join("#" + h.lstrip("#") for h in short.get("hashtags", []))
        out += [f"## Short {i}: {short['title']}", "", f"**Caption:** {short.get('caption', '')}", "",
                f"**Hashtags:** {tags}", ""]
        for sc in short["scenes"]:
            v = _visual(sc)
            if v:
                out += [v, ""]
            out += [sc["narration"], ""]
        out += ["---", ""]
    return "\n".join(out)


def export(job: dict, dest_root: Path) -> Path:
    """Writes <dest_root>/<date>-<slug>/{en.md, es.md, shorts-en.md, shorts-es.md}."""
    folder = dest_root / f"{dt.date.today():%Y-%m-%d}-{slugify(job['idea']['topic'], 50)}"
    folder.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "es"):
        if f"script_{lang}" not in job:
            continue
        # -es.md suffix: the workflow voices it in Spanish if ever needed
        name = "script-en.md" if lang == "en" else "script-es.md"
        (folder / name).write_text(long_md(job, lang), encoding="utf-8")
        if job.get(f"shorts_{lang}"):
            (folder / f"shorts-{lang}.md").write_text(shorts_md(job, lang), encoding="utf-8")
    log.info("Scripts exported to %s", folder)
    return folder
