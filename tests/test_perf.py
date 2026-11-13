"""Optimasi RAM/CPU: penyaring wake, keep_alive model, trim memori, suara malas."""

from __future__ import annotations

import numpy as np
import pytest

from jarvis.audio.vad import VAD
from jarvis.audio.wakeword import plausible_wake
from jarvis.config import Config


@pytest.mark.parametrize(
    ("heard", "ok"),
    [("Hello.", True), ("hello jarvis", True), ("Halo", True), ("Helo", True), ("hey", True),
     ("", False), ("Berapa lagi nanti dia datang", False), ("Thank you very much", False),
     ("Pituh kanji president", False)],
)  # fmt: skip
def test_plausible_wake_is_loose_but_rejects_ordinary_speech(heard, ok) -> None:
    assert plausible_wake(heard, ["hello"]) is ok


def test_plausible_wake_follows_configured_phrases() -> None:
    assert plausible_wake("hey teman tolong", ["hey teman"])
    assert not plausible_wake("tolong buka kalkulator sekarang", ["hey teman"])


def test_speech_stats_counts_voiced_time(monkeypatch) -> None:
    vad = VAD.__new__(VAD)
    vad.cfg = Config().vad
    probs = np.array([0.9] * 10 + [0.1] * 30, dtype=np.float32)  # 10 dari 40 jendela = suara
    vad.model = lambda audio: probs[: len(audio) // 512]
    voiced, ratio = vad.speech_stats(np.zeros(512 * 40, dtype=np.int16))
    assert voiced == pytest.approx(10 * 512 / 16000) and ratio == pytest.approx(0.25)
    assert vad.speech_stats(np.zeros(100, dtype=np.int16)) == (0.0, 0.0)  # terlalu pendek


def test_smart_model_is_unloaded_when_idle_but_fast_model_stays() -> None:
    llm = Config().llm
    assert llm.keep_alive_for(llm.fast_model) == -1
    assert llm.keep_alive_for(llm.smart_model) == "5m"
    assert llm.keep_alive_for(None) == -1


def test_agent_prewarm_off_by_default_and_wake_threads_small() -> None:
    cfg = Config()
    assert cfg.agent.prewarm is False  # 9B (±6 GB) tidak dimuat otomatis
    assert cfg.stt.wake_threads == 2 and cfg.wakeword.gate


def test_trim_memory_never_raises_on_any_adapter(adapter) -> None:
    adapter.trim_memory()  # default: tidak melakukan apa-apa
    from jarvis.platform import get_adapter

    get_adapter().trim_memory()  # adapter OS sungguhan: aman dipanggil berkali-kali
    get_adapter().trim_memory()


class _Spy:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.stopped = False

    def speak(self, text: str) -> None:
        self.said.append(text)

    def stop(self) -> None:
        self.stopped = True


def test_lazy_tts_builds_only_on_first_use_and_falls_back() -> None:
    from jarvis.tts import LazyTTS

    built: list[int] = []

    def build():  # noqa: ANN202
        built.append(1)
        return _Spy()

    lazy = LazyTTS(build)
    lazy.stop()  # belum dimuat: tidak memuat hanya untuk berhenti
    assert built == []
    lazy.speak("halo")
    lazy.speak("lagi")
    assert built == [1] and lazy._impl.said == ["halo", "lagi"]

    backup = _Spy()
    missing = LazyTTS(lambda: None, fallback=backup)  # suara Inggris tak ada → pakai cadangan
    missing.speak("hello")
    assert backup.said == ["hello"]


def test_local_tts_loads_no_voice_until_spoken(monkeypatch) -> None:
    from jarvis import tts

    calls: list[str] = []
    monkeypatch.setattr(tts, "_build_local", lambda cfg, lang: calls.append(lang) or _Spy())
    local = tts._local_tts(Config())
    assert calls == []  # Fish aktif: suara cadangan tidak memakan RAM
    local.speak("Siap, saya buka Spotify.")
    assert calls == ["id"]
    local.speak("Good morning everyone.")
    assert calls == ["id", "en"]
