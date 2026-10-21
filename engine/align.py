"""Word-level timestamps for generated audio (needed for captions) using faster-whisper."""
from pathlib import Path

_model = None


def word_timings(audio: Path, lang: str) -> list[dict]:
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(str(audio), language=lang, word_timestamps=True, vad_filter=False)
    return [{"word": w.word.strip(), "start": w.start, "end": w.end}
            for seg in segments for w in seg.words if w.word.strip()]
