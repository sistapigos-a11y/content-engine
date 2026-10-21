"""SRT subtitles from word timings (uploaded to YouTube as closed captions)."""
from pathlib import Path


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _group(words, max_words, max_gap=0.6):
    group = []
    for w in words:
        if group and (len(group) >= max_words or w["start"] - group[-1]["end"] > max_gap
                      or group[-1]["word"][-1:] in ".?!"):
            yield group
            group = []
        group.append(w)
    if group:
        yield group


def write_srt(words, out: Path, max_words: int = 9) -> Path:
    lines = []
    for i, g in enumerate(_group(words, max_words), 1):
        text = " ".join(w["word"] for w in g)
        lines.append(f"{i}\n{_srt_time(g[0]['start'])} --> {_srt_time(g[-1]['end'])}\n{text}\n")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

