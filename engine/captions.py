"""Subtitle files from TTS word timings: SRT for long videos, animated ASS for Shorts."""
from pathlib import Path


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


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


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(words, out: Path, w: int, h: int, font: str = "DejaVu Sans") -> Path:
    """Big centred 1-3 word captions; the word being spoken is highlighted yellow."""
    size = int(w * 0.085)
    events = []
    for g in _group(words, 3, max_gap=0.35):
        for j, cur in enumerate(g):
            end = g[j + 1]["start"] if j + 1 < len(g) else cur["end"] + 0.15
            parts = [(r"{\c&H00E5FF&}" + x["word"].upper() + r"{\c&HFFFFFF&}") if x is cur
                     else x["word"].upper() for x in g]
            pop = r"{\fscx108\fscy108\t(0,90,\fscx100\fscy100)}" if j == 0 else ""
            events.append(f"Dialogue: 0,{_ass_time(cur['start'])},{_ass_time(end)},Cap,,0,0,0,,"
                          f"{pop}{' '.join(parts)}")
    out.write_text(ASS_HEADER.format(w=w, h=h, font=font, size=size, outline=max(4, size // 14))
                   + "\n".join(events) + "\n", encoding="utf-8")
    return out
