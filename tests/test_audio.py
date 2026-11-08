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


def test_match_phrase_hello() -> None:
    from jarvis.audio.wakeword import match_phrase

    assert match_phrase("Hello", "hello") == ""
    assert match_phrase("Hi, jam berapa sekarang?", "hello") == "jam berapa sekarang?"
    assert match_phrase("halo buka spotify", "hello") == "buka spotify"
    assert match_phrase("Hey volume 30", "hello") == "volume 30"
    assert match_phrase("hai", "hello") == ""
    assert match_phrase("Hello, Ketik: Halo Dunia.", "hello") == "Ketik: Halo Dunia."
    assert match_phrase("cuaca hari ini cerah", "hello") is None
    assert match_phrase("oke hello", "hello") is None  # bukan di awal ucapan
    assert match_phrase("helmet", "hello") is None


def test_match_phrase_multiword() -> None:
    from jarvis.audio.wakeword import match_phrase

    assert match_phrase("Hey teman", "hey teman") == ""
    assert match_phrase("Hai temen, jam berapa sekarang?", "hey teman") == "jam berapa sekarang?"
    assert match_phrase("Heyteman volume 30", "hey teman") == "volume 30"
    assert match_phrase("teman saya datang", "hey teman") is None


def test_prompt_echo_filter() -> None:
    from jarvis.config import STTConfig
    from jarvis.stt.whisper import WhisperSTT

    stt = object.__new__(WhisperSTT)
    stt.cfg = STTConfig()
    assert stt._is_prompt_echo("Hello, buka, utup, volume, Spotify, Chrome, VS Code")
    assert not stt._is_prompt_echo("buka spotify dan putar musik santai")
    assert not stt._is_prompt_echo("hello")


def test_repetitive_hallucination_dropped() -> None:
    from jarvis.stt.whisper import is_repetitive

    assert is_repetitive("saya juga berada di depan. " * 20)
    assert is_repetitive("1,2,3,4,5," + "6," * 80)
    assert not is_repetitive("tolong buka spotify lalu putar musik santai sekarang juga ya")
    assert not is_repetitive("hello")


def test_sentence_speaker_cancel_drops_queue() -> None:
    import threading

    from jarvis.tts.stream import SentenceSpeaker

    spoken: list[str] = []
    gate = threading.Event()

    class SlowTTS:
        def speak(self, text: str) -> None:
            spoken.append(text)
            gate.wait(timeout=2)

        def stop(self) -> None:
            gate.set()

    sp = SentenceSpeaker(SlowTTS(), 1000)  # type: ignore[arg-type]
    sp.say("Kalimat satu.")
    sp.say("Kalimat dua.")
    sp.say("Kalimat tiga.")
    import time

    time.sleep(0.2)
    sp.cancel()
    sp.say("Setelah batal.")
    sp.finish()
    assert spoken == ["Kalimat satu."]


def test_interrupt_detection() -> None:
    from jarvis.app import Jarvis
    from jarvis.config import Config

    j = object.__new__(Jarvis)
    j.cfg = Config()
    for said in ["berhenti", "Stop.", "cukup", "hello", "Hi, berhenti dong"]:
        assert j._is_interrupt(said), said
    for said in ["Ibu kota Jepang adalah Tokyo", "dan itu sangat menarik sekali", "terima kasih"]:
        assert not j._is_interrupt(said), said
