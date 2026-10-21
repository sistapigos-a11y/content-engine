"""Free neural voiceover with Microsoft Edge TTS, keeping word timings for captions."""
import asyncio
import os
from pathlib import Path

import edge_tts

from .util import retry

TICKS = 10_000_000  # edge-tts offsets are in 100ns units


async def _synth(text, voice, rate, out: Path):
    words = []
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary",
                                 proxy=os.environ.get("HTTPS_PROXY") or None)
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"word": chunk["text"],
                              "start": chunk["offset"] / TICKS,
                              "end": (chunk["offset"] + chunk["duration"]) / TICKS})
    if out.stat().st_size == 0:
        raise RuntimeError("TTS returned no audio")
    return words


def synthesize(text: str, voice: str, rate: str, out: Path) -> list[dict]:
    """Write an mp3 to `out` and return [{word,start,end}] in seconds."""
    return retry(lambda: asyncio.run(_synth(text, voice, rate, out)), what="edge-tts")
