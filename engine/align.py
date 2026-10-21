"""Word-level timestamps for generated audio (needed for captions) using faster-whisper."""
from pathlib import Path

_model = None


def _whisper():
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def transcribe(audio, lang: str) -> str:
    """Plain transcript of a path or a 16 kHz float32 array (used to quality-check TTS takes)."""
    segments, _ = _whisper().transcribe(audio, language=lang, beam_size=1)
    return " ".join(s.text for s in segments)


def word_timings(audio: Path, lang: str) -> list[dict]:
    segments, _ = _whisper().transcribe(str(audio), language=lang, word_timestamps=True, vad_filter=False)
    return [{"word": w.word.strip(), "start": w.start, "end": w.end}
            for seg in segments for w in seg.words if w.word.strip()]
