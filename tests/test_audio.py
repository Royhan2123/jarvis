from __future__ import annotations

import numpy as np

from jarvis.app import shorten_for_speech
from jarvis.audio.vad import record_utterance
from jarvis.config import VADConfig

CHUNK = np.zeros(1280, dtype=np.int16)


def _run(pattern: list[bool], **cfg) -> np.ndarray | None:
    flags = iter(pattern)
    return record_utterance(
        iter([CHUNK] * len(pattern)),
        lambda _c: next(flags),
        VADConfig(**cfg),
        sample_rate=16000,
        chunk_ms=80,
    )


def test_no_speech_times_out() -> None:
    assert _run([False] * 200, listen_timeout_s=2) is None


def test_stops_after_silence() -> None:
    # 5 chunk bicara lalu 10 diam (800 ms = 10 chunk) → berhenti
    out = _run([False, True] * 3 + [False] * 40)
    assert out is not None
    assert out.size < 40 * 1280


def test_max_record_limit() -> None:
    out = _run([True] * 500, max_record_s=1)
    assert out is not None
    assert out.size == (1000 // 80) * 1280


def test_shorten_for_speech() -> None:
    assert shorten_for_speech("Halo.  Apa kabar?", 400) == "Halo. Apa kabar?"
    long = "Kalimat satu. " + "x" * 500
    assert shorten_for_speech(long, 50) == "Kalimat satu."
