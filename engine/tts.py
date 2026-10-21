"""Voiceover in YOUR cloned voice.

Providers (config.yaml -> voice.provider):
  chatterbox  free, open-source (MIT), clones from a 10-30 s sample, EN + ES. Runs on CPU.
  elevenlabs  paid, fastest and most natural; uses your ElevenLabs cloned voice id.
  edge        free Microsoft voices (not your voice) - emergency fallback.

Every provider returns word timings [{word,start,end}] in seconds for captions.
"""
import asyncio
import base64
import difflib
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


def _chunks(text: str) -> list[str]:
    """Group sentences into chunks of ~70-230 chars; a short tail is merged into the previous chunk."""
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text.strip()):
        if cur and len(cur) >= 70:
            out.append(cur)
            cur = s
        elif cur and len(cur) + len(s) > 230:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        if out and len(cur) < 40:
            out[-1] += " " + cur
        else:
            out.append(cur)
    return out


def _match(expected: str, heard: str) -> float:
    """How close the Whisper transcript is to the text we asked for (0..1)."""
    norm = lambda t: re.sub(r"[^\w\s]", "", t.lower()).split()  # noqa: E731
    return difflib.SequenceMatcher(None, norm(expected), norm(heard)).ratio()


def _best_take(model, text: str, lang: str, v: dict):
    """Generate up to N takes with different seeds; keep the one Whisper understands best.
    Catches the mumbles, skipped words and strange noises Chatterbox sometimes produces."""
    import librosa
    import torch
    from .align import transcribe

    tries, good_enough = v.get("best_of", 5), v.get("min_match", 0.92)
    best = (-1.0, None, 0)
    for i in range(tries):
        torch.manual_seed(3000 + i)
        wav = model.generate(text, language_id=lang, exaggeration=v.get("exaggeration", 0.5),
                             cfg_weight=v.get("cfg_weight", 0.5), temperature=v.get("temperature", 0.7)).cpu()
        dur = wav.shape[-1] / model.sr
        audio16 = librosa.resample(wav.squeeze(0).numpy(), orig_sr=model.sr, target_sr=16000)
        score = _match(text, transcribe(audio16, lang))
        # takes far longer than the text needs usually contain babbling or long silences
        if dur > len(text) / 7 + 2:
            score -= 0.3
        if score > best[0]:
            best = (score, wav, i + 1)
        if score >= good_enough:
            break
    log.info("chunk ok: match %.2f after %d take(s)", best[0], best[2])
    return best[1]


def _chatterbox(text, lang, cfg, out: Path):
    global _cb_model
    import noisereduce as nr
    import numpy as np
    import soundfile as sf
    import torch
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

    pause = np.zeros(int(_cb_model.sr * 0.18), dtype=np.float32)
    pieces = []
    for chunk in _chunks(text):
        pieces += [_best_take(_cb_model, chunk, lang, v).squeeze(0).numpy(), pause]
    raw = np.concatenate(pieces)

    # gentle stationary denoise, then a fixed RMS level so every scene sounds the same
    x = nr.reduce_noise(y=raw, sr=_cb_model.sr, stationary=True, prop_decrease=0.5)
    x = np.clip(x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 0.08, -1.0, 1.0)
    path = out.with_suffix(".wav")
    sf.write(str(path), x.astype(np.float32), _cb_model.sr)
    from .align import word_timings
    return path, word_timings(path, lang)


# --- ElevenLabs (paid, your cloned voice) ----------------------------------------

def _elevenlabs(text, lang, cfg, out: Path):
    voice_id = env(f"ELEVENLABS_VOICE_ID_{lang.upper()}") or env("ELEVENLABS_VOICE_ID", required=True)

    model = cfg["voice"].get("elevenlabs_model", "eleven_multilingual_v2")
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.3}}
    if "turbo" in model or "flash" in model:  # only these models accept a forced language
        body["language_code"] = lang

    def call():
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
                          headers={"xi-api-key": env("ELEVENLABS_API_KEY", required=True)},
                          json=body, timeout=300)
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


# --- Fish Audio (paid, cheap, your cloned voice) -------------------------------

def _fish(text, lang, cfg, out: Path):
    """Fish Audio TTS with your cloned voice model (create it once on fish.audio, then put its id
    in FISH_VOICE_ID). The language is detected from the text, so one voice works for EN and ES."""
    v = cfg["voice"]
    voice_id = env(f"FISH_VOICE_ID_{lang.upper()}") or env("FISH_VOICE_ID", required=True)

    def call():
        r = requests.post("https://api.fish.audio/v1/tts", timeout=300, headers={
            "Authorization": f"Bearer {env('FISH_API_KEY', required=True)}",
            "Content-Type": "application/json",
            "model": v.get("fish_model", "s2.1-pro")},
            json={"text": text, "reference_id": voice_id, "format": "mp3",
                  "temperature": v.get("fish_temperature", 0.7), "top_p": v.get("fish_top_p", 0.7),
                  "prosody": {"speed": v.get("fish_speed", 1.0), "normalize_loudness": True},
                  "normalize": True})
        if r.status_code >= 400:
            raise RuntimeError(f"Fish Audio HTTP {r.status_code}: {r.text[:300]}")
        if not r.content:
            raise RuntimeError("Fish Audio returned no audio")
        return r.content

    path = out.with_suffix(".mp3")
    path.write_bytes(retry(call, what="fish-audio"))
    from .align import word_timings
    return path, word_timings(path, lang)


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


PROVIDERS = {"chatterbox": _chatterbox, "elevenlabs": _elevenlabs, "fish": _fish, "edge": _edge}


def normalize_loudness(path: Path, out: Path) -> Path:
    """YouTube-friendly loudness (-14 LUFS) and a gentle de-ess/high-pass for cloned voices."""
    run(["ffmpeg", "-y", "-i", str(path), "-af",
         "highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(out)])
    return out
