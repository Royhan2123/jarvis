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


def test_match_phrase() -> None:
    from jarvis.audio.wakeword import match_phrase

    assert match_phrase("Hey teman", "hey teman") == ""
    assert match_phrase("Hai temen, jam berapa sekarang?", "hey teman") == "jam berapa sekarang"
    assert match_phrase("hey teman buka spotify", "hey teman") == "buka spotify"
    assert match_phrase("Heyteman volume 30", "hey teman") == "volume 30"
    assert match_phrase("cuaca hari ini cerah", "hey teman") is None
    assert match_phrase("teman saya datang", "hey teman") is None
