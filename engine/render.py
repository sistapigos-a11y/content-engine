"""Turns a script into a finished video: voiceover, footage, music, captions."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import captions, tts
from .media import MediaPicker, fallback_clip
from .util import ROOT, log, media_duration, run

FPS = 30
FORMATS = {"long": (1920, 1080), "short": (1080, 1920)}


def _voiceover(scenes, lang_cfg, workdir: Path):
    """One mp3 per scene, then joined; returns (audio_path, words, scene_bounds)."""
    words, bounds, files, t = [], [], [], 0.0
    for i, sc in enumerate(scenes):
        mp3 = workdir / f"vo_{i:03}.mp3"
        ws = tts.synthesize(sc["narration"], lang_cfg["voice"], lang_cfg.get("rate", "+0%"), mp3)
        dur = media_duration(mp3) + 0.25  # small breath between scenes
        words += [{**w, "start": w["start"] + t, "end": w["end"] + t} for w in ws]
        bounds.append((t, t + dur))
        files.append((mp3, dur))
        t += dur
    listfile = workdir / "vo_list.txt"
    # pad each scene to its exact slot so audio and video stay in sync
    padded = []
    for i, (mp3, dur) in enumerate(files):
        wav = workdir / f"vo_{i:03}.wav"
        run(["ffmpeg", "-y", "-i", str(mp3), "-af", f"apad=whole_dur={dur:.3f}",
             "-ar", "44100", "-ac", "2", str(wav)])
        padded.append(wav)
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in padded))
    voice = workdir / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(voice)])
    return voice, words, bounds


def _segment(src: Path | None, out: Path, w, h, frames, portrait):
    secs = frames / FPS
    if src is None:
        return fallback_clip(out, w, h, secs)
    zoom = random.choice(["1.0+0.0004*on", "1.08-0.0004*on"])  # gentle push-in / pull-out
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},"
          f"zoompan=z='{zoom}':d=1:s={w}x{h}:fps={FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
          "setsar=1,eq=saturation=0.9:contrast=1.05")
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-vf", vf, "-frames:v", str(frames),
         "-an", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-r", str(FPS), str(out)])
    return out


def _visuals(scenes, bounds, cfg, kind, workdir: Path) -> Path:
    w, h = FORMATS[kind]
    portrait = kind == "short"
    picker = MediaPicker(cfg, portrait)
    max_clip = cfg["media"]["clip_max_seconds"] if kind == "long" else 3.5
    segs, idx = [], 0
    for sc, (start, end) in zip(scenes, bounds):
        n = max(1, round((end - start) / max_clip + 0.49))
        clips = picker.clips(sc["visual"], n)
        step = (end - start) / n
        for k in range(n):
            # frame counts from absolute times so rounding never accumulates drift
            f0, f1 = round((start + k * step) * FPS), round((start + (k + 1) * step) * FPS)
            src = clips[k % len(clips)] if clips else None
            segs.append(_segment(src, workdir / f"seg_{idx:04}.mp4", w, h, f1 - f0, portrait))
            idx += 1
    listfile = workdir / "seg_list.txt"
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
    video = workdir / "visual.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(video)])
    return video


def _music() -> Path | None:
    tracks = list((ROOT / "assets" / "music").glob("*.mp3"))
    return random.choice(tracks) if tracks else None


def render(scenes, lang_cfg, cfg, kind: str, workdir: Path, out: Path, burn_captions: bool):
    workdir.mkdir(parents=True, exist_ok=True)
    log.info("Rendering %s video (%d scenes) -> %s", kind, len(scenes), out)
    voice, words, bounds = _voiceover(scenes, lang_cfg, workdir)
    video = _visuals(scenes, bounds, cfg, kind, workdir)
    w, h = FORMATS[kind]

    inputs = ["-i", str(video), "-i", str(voice)]
    music = _music()
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        vol = cfg["media"]["music_volume"]
        afilter = (f"[2:a]volume={vol},afade=t=in:d=2[m];"
                   "[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]")
    else:
        afilter = "[1:a]anull[a]"

    srt = captions.write_srt(words, out.with_suffix(".srt"))
    if burn_captions:
        ass = captions.write_ass(words, workdir / "captions.ass", w, h)
        fonts = ROOT / "assets" / "fonts"
        vfilter = f"[0:v]ass={ass}:fontsdir={fonts}[v]"
        vcodec = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        vmap = "[v]"
    else:
        vfilter = ""
        vcodec = ["-c:v", "copy"]  # no re-encode: the long video is already final
        vmap = "0:v"

    out.parent.mkdir(parents=True, exist_ok=True)
    graph = f"{vfilter};{afilter}" if vfilter else afilter
    run(["ffmpeg", "-y", *inputs, "-filter_complex", graph,
         "-map", vmap, "-map", "[a]", *vcodec, "-c:a", "aac", "-b:a", "192k",
         "-shortest", "-movflags", "+faststart", str(out)])
    log.info("Done: %s (%.1f s)", out, media_duration(out))
    return out, srt


def thumbnail(video: Path, text: str, out: Path) -> Path:
    frame = out.with_suffix(".frame.jpg")
    dur = media_duration(video)
    run(["ffmpeg", "-y", "-ss", f"{min(8, dur / 3):.2f}", "-i", str(video), "-frames:v", "1", str(frame)])
    img = Image.open(frame).convert("RGB").resize((1280, 720))
    img = ImageEnhance.Brightness(img.filter(ImageFilter.GaussianBlur(1))).enhance(0.55)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    draw = ImageDraw.Draw(img)
    font_path = next((p for p in [ROOT / "assets/fonts/thumb.ttf",
                                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
                      if p.exists()), None)
    text = text.upper()
    size = 150
    while size > 50:
        font = ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default()
        lines = _wrap(draw, text, font, 1180)
        if len(lines) <= 3:
            break
        size -= 10
    y = 360 - (len(lines) * size * 1.1) / 2
    for i, line in enumerate(lines):
        color = (255, 214, 0) if i == len(lines) - 1 else (255, 255, 255)
        draw.text((60, y), line, font=font, fill=color, stroke_width=8, stroke_fill=(0, 0, 0))
        y += size * 1.1
    img.save(out, quality=92)
    frame.unlink(missing_ok=True)
    return out


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines
