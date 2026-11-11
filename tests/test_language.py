from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.brain import language, rules
from jarvis.brain.rules import Intent
from jarvis.config import Config
from jarvis.tools import language as lang_tool
from jarvis.tools.registry import ToolError, context, registry


def test_target_language_and_guess() -> None:
    assert language.target_language("Inggris") == "English"
    assert language.target_language("japanese") == "Japanese"
    assert language.target_language("kucing") is None
    assert language.guess("what is the capital of japan") == "en"
    assert language.guess("apa ibu kota jepang") == "id"
    assert language.guess("") == "id"


@pytest.mark.parametrize(
    ("said", "text", "target"),
    [
        ("terjemahkan ke bahasa Inggris: selamat pagi", "selamat pagi", "inggris"),
        ("Jarvis, terjemahkan selamat pagi ke bahasa Inggris", "selamat pagi", "inggris"),
        ("apa bahasa Inggris dari terima kasih", "terima kasih", "inggris"),
        ("translate good morning to Indonesian", "good morning", "indonesian"),
        ("translate to japanese: thank you", "thank you", "japanese"),
        ("how do you say thank you in Japanese", "thank you", "japanese"),
    ],
)
def test_translate_rules(said, text, target) -> None:
    assert rules.match(said) == [Intent("translate", {"text": text, "target": target})]


def test_translate_ignores_unknown_language() -> None:
    assert rules.match("terjemahkan ini ke bahasa kucing") is None


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("open Chrome", [Intent("open_app", {"name": "Chrome"})]),
        ("please open chrome and spotify", [Intent("open_app", {"name": "Chrome"}),
                                            Intent("open_app", {"name": "Spotify"})]),
        ("close Spotify", [Intent("close_app", {"name": "Spotify"})]),
        ("What time is it?", [Intent("get_time", {"what": "time"})]),
        ("what's today's date", [Intent("get_time", {"what": "date"})]),
        ("set volume to 40", [Intent("set_volume", {"percent": 40})]),
        ("mute", [Intent("mute", {"on": True})]),
        ("next song", [Intent("media", {"action": "next"})]),
        ("lock screen", [Intent("lock_screen")]),
        ("search for python tutorials", [Intent("web_search", {"query": "python tutorials"})]),
        ("what's the weather in Bandung", [Intent("get_weather", {"city": "Bandung"})]),
    ],
)  # fmt: skip
def test_english_rules(said, expected) -> None:
    assert rules.match(said) == expected


def test_english_rules_do_not_grab_questions() -> None:
    assert rules.match("what is the meaning of life") is None
    assert rules.match("tell me a story about open source") is None


class FakeClient:
    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, []

    def chat(self, **kw):  # noqa: ANN003, ANN201
        self.calls.append(kw)
        return SimpleNamespace(message=SimpleNamespace(content=self.reply))


def test_run_translation_prompts_the_model_and_cleans_output() -> None:
    client = FakeClient('"Good morning"\n')
    out = lang_tool.run_translation("selamat pagi", "English", Config(), client)
    assert out == "Good morning"
    sent = client.calls[0]["messages"]
    assert "English" in sent[0]["content"] and sent[1]["content"] == "selamat pagi"
    assert client.calls[0]["options"]["temperature"] == 0.0


def test_translate_tool_end_to_end(adapter, monkeypatch) -> None:
    context.configure(adapter, Config(), context.memory)
    monkeypatch.setattr(lang_tool, "run_translation", lambda text, target, **_: f"{target}:{text}")
    assert registry.call("translate", {"text": "halo", "target": "inggris"}) == "English:halo"
    with pytest.raises(ToolError, match="Tidak ada teks"):
        registry.call("translate", {"text": "  ", "target": "inggris"})


def test_translate_tool_reports_model_failure(adapter, monkeypatch) -> None:
    context.configure(adapter, Config(), context.memory)

    def boom(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise ConnectionError("ollama mati")

    monkeypatch.setattr(lang_tool, "run_translation", boom)
    with pytest.raises(ToolError, match="tidak bisa dipakai"):
        registry.call("translate", {"text": "halo", "target": "inggris"})


def test_router_offers_translate_tool_for_free_form_requests() -> None:
    from jarvis.brain.router import Router

    names = {
        t["function"]["name"] for t in Router(Config()).tool_schemas("tolong terjemah ini", False)
    }
    assert "translate" in names


# ── STT: deteksi bahasa ──
class FakeModel:
    probs = [("en", 0.9), ("id", 0.05)]
    seen: list[str | None] = []

    def __init__(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        pass

    def detect_language(self, audio):  # noqa: ANN001, ANN201
        return self.probs[0][0], self.probs[0][1], self.probs

    def transcribe(self, audio, language=None, initial_prompt=None, **kw):  # noqa: ANN001, ANN003, ANN201
        FakeModel.seen.append(language)
        seg = SimpleNamespace(text=" hello there friend", avg_logprob=-0.3)
        return [seg], None


@pytest.fixture
def stt_cls(monkeypatch):
    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeModel)
    FakeModel.seen = []
    from jarvis.stt.whisper import WhisperSTT

    return WhisperSTT


AUDIO = np.zeros(16000, dtype=np.int16)


def test_auto_language_picks_english_then_indonesian(stt_cls) -> None:
    cfg = Config().stt.model_copy(update={"language": "auto"})
    stt = stt_cls(cfg)
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "en" and stt.last_language == "en"
    FakeModel.probs = [("id", 0.8), ("en", 0.1)]
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "id" and stt.last_language == "id"


def test_fixed_language_never_detects_and_wake_stays_indonesian(stt_cls) -> None:
    FakeModel.probs = [("en", 0.99), ("id", 0.0)]
    stt = stt_cls(Config().stt)  # language: id
    assert stt.detector is None
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "id"
    auto = stt_cls(Config().stt.model_copy(update={"language": "auto"}))
    auto.transcribe(AUDIO, fast=True)  # wake tidak memakai deteksi
    assert FakeModel.seen[-1] == "id" and auto.last_language == "id"
