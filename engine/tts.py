"""Voiceover in YOUR cloned voice.

Providers (config.yaml -> voice.provider):
  chatterbox  free, open-source (MIT), clones from a 10-30 s sample, EN + ES. Runs on CPU.
  elevenlabs  paid, fastest and most natural; uses your ElevenLabs cloned voice id.
  edge        free Microsoft voices (not your voice) - emergency fallback.

Every provider returns word timings [{word,start,end}] in seconds for captions.
"""
import asyncio
import base64
import os
import re
from pathlib import Path

import requests

from .util import ROOT, env, log, retry, run

TICKS = 10_000_000  # edge-tts offsets are in 100ns units


def synthesize(text: str, lang: str, cfg: dict, out: Path) -> tuple[Path, list[dict]]:
    """Writes audio next to `out` (extension decided by provider) and returns (path, words)."""
    provider = cfg["voice"]["provider"]
    try:
        return PROVIDERS[provider](text, lang, cfg, out)
    except Exception as e:  # noqa: BLE001
        fb = cfg["voice"].get("fallback")
        if not fb or fb == provider:
            raise
        log.error("Voice provider %s failed (%s); falling back to %s", provider, e, fb)
        return PROVIDERS[fb](text, lang, cfg, out)


def voice_sample(lang: str) -> Path:
    folder = ROOT / "assets" / "voice"
    for name in (f"me_{lang}.wav", f"me_{lang}.mp3", "me.wav", "me.mp3"):
        if (folder / name).exists():
            return folder / name
    raise FileNotFoundError("Put a clean 10-30 s recording of your voice in assets/voice/me.wav")


# --- Chatterbox (open-source voice cloning) -----------------------------------

_cb_model = None


def _sentences(text: str, max_chars: int = 260) -> list[str]:
    """Chatterbox is best with short inputs: split on sentences, then on commas if needed."""
    out = []
    for s in re.split(r"(?<=[.!?…])\s+", text.strip()):
        while len(s) > max_chars:
            cut = s.rfind(",", 0, max_chars)
            cut = cut if cut > 40 else s.rfind(" ", 0, max_chars)
            out.append(s[: cut + 1].strip())
            s = s[cut + 1 :].strip()
        if s:
            out.append(s)
    return out


def _chatterbox(text, lang, cfg, out: Path):
    global _cb_model
    import torch
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    if _cb_model is None:
        log.info("Loading Chatterbox (first time downloads ~2 GB of weights)...")
        _cb_model = ChatterboxMultilingualTTS.from_pretrained(
            device="cuda" if torch.cuda.is_available() else "cpu")
        _cb_model.prepared_for = None
    v = cfg["voice"]
    sample = voice_sample(lang)
    if _cb_model.prepared_for != sample:
        _cb_model.prepare_conditionals(str(sample), exaggeration=v.get("exaggeration", 0.5))
        _cb_model.prepared_for = sample

    pause = torch.zeros(1, int(_cb_model.sr * 0.18))
    pieces = []
    for sentence in _sentences(text):
        wav = _cb_model.generate(sentence, language_id=lang, exaggeration=v.get("exaggeration", 0.5),
                                 cfg_weight=v.get("cfg_weight", 0.5), temperature=v.get("temperature", 0.8))
        pieces += [wav, pause]
    path = out.with_suffix(".wav")
    torchaudio.save(str(path), torch.cat(pieces, dim=1), _cb_model.sr)
    from .align import word_timings
    return path, word_timings(path, lang)


# --- ElevenLabs (paid, your cloned voice) ----------------------------------------

def _elevenlabs(text, lang, cfg, out: Path):
    voice_id = env(f"ELEVENLABS_VOICE_ID_{lang.upper()}") or env("ELEVENLABS_VOICE_ID", required=True)

    def call():
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
                          headers={"xi-api-key": env("ELEVENLABS_API_KEY", required=True)},
                          json={"text": text, "model_id": cfg["voice"].get("elevenlabs_model", "eleven_multilingual_v2"),
                                "language_code": lang,
                                "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.3}},
                          timeout=300)
        r.raise_for_status()
        return r.json()

    data = retry(call, what="elevenlabs")
    path = out.with_suffix(".mp3")
    path.write_bytes(base64.b64decode(data["audio_base64"]))
    a = data["alignment"]
    words, cur, start = [], "", None
    for ch, t0, t1 in zip(a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": start, "end": prev_end})
            cur, start = "", None
            continue
        if not cur:
            start = t0
        cur += ch
        prev_end = t1
    if cur:
        words.append({"word": cur, "start": start, "end": prev_end})
    return path, words


# --- Edge TTS (free, generic voice) -------------------------------------------------

async def _edge_stream(text, voice, rate, path):
    import edge_tts
    words = []
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary",
                                proxy=os.environ.get("HTTPS_PROXY") or None)
    with open(path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"word": chunk["text"], "start": chunk["offset"] / TICKS,
                              "end": (chunk["offset"] + chunk["duration"]) / TICKS})
    return words


def _edge(text, lang, cfg, out: Path):
    v = cfg["voice"]["edge_voices"][lang]
    path = out.with_suffix(".mp3")
    words = retry(lambda: asyncio.run(_edge_stream(text, v["voice"], v.get("rate", "+0%"), path)), what="edge-tts")
    return path, words


PROVIDERS = {"chatterbox": _chatterbox, "elevenlabs": _elevenlabs, "edge": _edge}


def normalize_loudness(path: Path, out: Path) -> Path:
    """YouTube-friendly loudness (-14 LUFS) and a gentle de-ess/high-pass for cloned voices."""
    run(["ffmpeg", "-y", "-i", str(path), "-af",
         "highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(out)])
    return out
