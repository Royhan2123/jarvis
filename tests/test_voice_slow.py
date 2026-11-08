"""Uji model asli (butuh model terunduh). Jalankan: pytest -m slow"""

from __future__ import annotations

import numpy as np
import pytest

from jarvis.config import Config

pytestmark = pytest.mark.slow


def test_piper_to_whisper_roundtrip() -> None:
    from jarvis.stt.whisper import WhisperSTT
    from jarvis.tts.piper import PiperTTS

    cfg = Config()
    audio, rate = PiperTTS(cfg).synthesize("Buka browser sekarang")
    assert rate > 0 and audio.size > 0
    # resample kasar ke 16 kHz
    idx = np.linspace(0, audio.size - 1, int(audio.size * 16000 / rate)).astype(int)
    text = WhisperSTT(cfg.stt).transcribe(audio[idx]).lower()
    assert "browser" in text or "buka" in text


def test_vad_detects_synth_speech() -> None:
    from jarvis.audio.vad import VAD
    from jarvis.tts.piper import PiperTTS

    cfg = Config()
    audio, rate = PiperTTS(cfg).synthesize("Halo, apa kabar hari ini")
    idx = np.linspace(0, audio.size - 1, int(audio.size * 16000 / rate)).astype(int)
    a16 = audio[idx]
    vad = VAD(cfg.vad)
    hits = [vad.is_speech(a16[i : i + 1280]) for i in range(0, len(a16) - 1280, 1280)]
    assert any(hits)
    vad.reset()
    assert not any(vad.is_speech(np.zeros(1280, dtype=np.int16)) for _ in range(5))


def test_wake_phrase_recognised_by_whisper() -> None:
    from jarvis.audio.wakeword import match_phrase
    from jarvis.stt.whisper import WhisperSTT
    from jarvis.tts.piper import PiperTTS

    cfg = Config()
    audio, rate = PiperTTS(cfg).synthesize("Hello, jam berapa sekarang")
    idx = np.linspace(0, audio.size - 1, int(audio.size * 16000 / rate)).astype(int)
    text = WhisperSTT(cfg.stt).transcribe(audio[idx])
    assert match_phrase(text, cfg.wakeword.phrase) is not None, text
