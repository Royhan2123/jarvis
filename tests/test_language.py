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


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("take a note: buy coffee tomorrow", [Intent("add_note", {"text": "buy coffee tomorrow"})]),
        ("note that the meeting moved to 3",
         [Intent("add_note", {"text": "the meeting moved to 3"})]),
        ("type: hello, the meeting is at 3",
         [Intent("type_text", {"text": "hello, the meeting is at 3"})]),
        ("send a WhatsApp to Budi saying I'll be late",
         [Intent("whatsapp_draft", {"contact": "Budi", "message": "I'll be late"})]),
        ("work on fixing the login bug", [Intent("run_agent", {"task": "fixing the login bug"})]),
        ("remind me to drink water in 10 minutes",
         [Intent("set_reminder", {"text": "drink water", "minutes": 10.0})]),
        ("remind me in 2 hours to call mom",
         [Intent("set_reminder", {"text": "call mom", "minutes": 120.0})]),
        ("read my notes", [Intent("list_notes")]),
        ("my name is Roy", [Intent("remember_fact", {"key": "nama", "value": "Roy"})]),
        ("summarize my screen", [Intent("read_screen",
                                        {"question": "Summarize what is on this screen briefly"})]),
        ("what's on my calendar today", [Intent("calendar_events", {"days": 1})]),
        ("do I have any new emails", [Intent("unread_emails")]),
        ("shut down computer", [Intent("shutdown")]),
        ("restart", [Intent("restart")]),
    ],
)  # fmt: skip
def test_more_english_rules(said, expected) -> None:
    assert rules.match(said) == expected


def test_english_device_commands() -> None:
    names = ["lampu ruang tamu"]
    assert rules.match_devices("turn on the lampu ruang tamu", names) == [
        Intent("device_control", {"name": "lampu ruang tamu", "action": "on"})
    ]
    assert rules.match_devices("switch off lampu ruang tamu", names) == [
        Intent("device_control", {"name": "lampu ruang tamu", "action": "off"})
    ]
    assert rules.match_devices("is lampu ruang tamu on", names) == [
        Intent("device_state", {"name": "lampu ruang tamu"})
    ]


def test_english_questions_are_not_hijacked() -> None:
    for q in ["how do I take a screenshot", "who is the note taker", "why did the system restart"]:
        assert rules.match(q) is None, q


# ── TTS dua bahasa ──
class SpyTTS:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.stopped = False

    def speak(self, text: str) -> None:
        self.said.append(text)

    def stop(self) -> None:
        self.stopped = True


def test_bilingual_tts_picks_voice_per_sentence() -> None:
    from jarvis.tts import BilingualTTS

    idt, ent = SpyTTS(), SpyTTS()
    tts = BilingualTTS(idt, ent)
    tts.speak("Siap, saya buka Spotify.")
    tts.speak("Good morning everyone.")
    tts.stop()
    assert idt.said == ["Siap, saya buka Spotify."] and ent.said == ["Good morning everyone."]
    assert idt.stopped and ent.stopped


def test_bilingual_tts_without_english_voice_uses_indonesian_for_all() -> None:
    from jarvis.tts import BilingualTTS

    idt = SpyTTS()
    BilingualTTS(idt, None).speak("Good morning everyone.")
    assert idt.said == ["Good morning everyone."]


def test_system_tts_uses_english_voice_table(adapter) -> None:
    from jarvis.tts.fallback import SystemTTS

    cfg = Config()
    assert SystemTTS(cfg, adapter, lang="en").voice == "Daniel"
    cfg.tts.gender = "female"
    assert SystemTTS(cfg, adapter, lang="en").voice == "Samantha"
    assert SystemTTS(cfg, adapter).voice == "Damayanti"


def test_guess_short_english_phrases() -> None:
    for s in ["Good morning everyone.", "Thank you very much", "Paris is the capital of France."]:
        assert language.guess(s) == "en", s
    for s in ["Siap, saya buka Spotify.", "Terima kasih banyak", "Oke"]:
        assert language.guess(s) == "id", s


@pytest.mark.parametrize(
    "said",
    [
        "sekarang tanggal berapa?",
        "tanggal berapa hari ini",
        "hari apa sekarang",
        "hari ini hari apa",
    ],
)
def test_date_questions_use_the_tool_not_the_llm(said) -> None:
    assert rules.match(said) == [Intent("get_time", {"what": "date"})]


def test_system_prompt_time_is_indonesian() -> None:
    from jarvis.brain.prompts import build_system_prompt

    prompt = build_system_prompt("Bos")
    assert any(
        d in prompt for d in ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
    )


def test_misheard_command_words_are_corrected_only_when_it_helps() -> None:
    assert rules.match("Anggal berapa ini?") == [Intent("get_time", {"what": "date"})]
    assert rules.match("tangal berapa hari ini") == [Intent("get_time", {"what": "date"})]
    assert rules.fix_misheard("anggal berapa") == "tanggal berapa"
    # ucapan biasa tidak disentuh dan tidak berubah jadi perintah
    assert rules.match("angka pi itu berapa") is None
    assert rules.match("saya suka anggur") is None


def test_speakable_rounds_long_decimals_then_spells_them() -> None:
    from jarvis.tts.stream import speakable

    assert (
        speakable("Angka pi adalah 3,141592653589793.") == "Angka pi adalah tiga koma satu empat."
    )
    assert speakable("Sekarang jam 19.43") == "Sekarang jam sembilan belas empat puluh tiga"
    assert (
        speakable("versi 1.2.3 dan 12,5 persen")
        == "versi satu titik dua titik tiga dan dua belas koma lima persen"
    )


# ── pendengaran & perintah yang gagal di uji nyata (log 2026-11-11) ──
def test_fuzzy_fix_never_turns_buatkan_into_an_open_command() -> None:
    assert rules.fix_misheard("buatkan volumenya") == "buatkan volumenya"
    assert rules.match("buatkan sesuatu yang bagus") is None


@pytest.mark.parametrize(
    ("said", "percent"),
    [("Buatkan volumenya besar 100%.", 100), ("buat volume jadi 50 persen", 50),
     ("atur volumenya ke 30", 30)],
)  # fmt: skip
def test_volume_phrasings(said, percent) -> None:
    assert rules.match(said) == [Intent("set_volume", {"percent": percent})]


@pytest.mark.parametrize(
    ("said", "query"),
    [("putar lagu dewa 19 di youtube", "dewa 19"),
     ("putarkan Bohemian Rhapsody dari YouTube", "Bohemian Rhapsody"),
     ("mainkan musik santai di youtube", "musik santai"),
     ("play despacito on youtube", "despacito")],
)  # fmt: skip
def test_play_on_youtube_rule(said, query) -> None:
    assert rules.match(said) == [Intent("play_youtube", {"query": query})]


def test_plain_play_music_still_controls_the_player() -> None:
    assert rules.match("putar musik") == [Intent("media", {"action": "play_pause"})]


def test_closest_app_fixes_misheard_names() -> None:
    from jarvis.platform.macos import closest_app

    apps = ["Safari", "Google Chrome", "Spotify", "Calculator", "WhatsApp"]
    assert closest_app("Savari", apps) == "Safari"
    assert closest_app("whatsap", apps) == "WhatsApp"
    assert closest_app("Fitur Whatsapp", apps) is None
    assert closest_app("Xyzzy", apps) is None


def test_play_youtube_tool_opens_first_result_and_respects_offline(adapter, monkeypatch) -> None:
    from jarvis.tools import web

    cfg = Config()
    cfg.general.offline_only = False
    context.configure(adapter, cfg, context.memory)
    opened: list[str] = []
    monkeypatch.setattr(web, "first_video_id", lambda q: "abcDEF12345")
    monkeypatch.setattr(web, "_open", opened.append)
    assert "memutar" in registry.call("play_youtube", {"query": "dewa 19"})
    assert opened == ["https://www.youtube.com/watch?v=abcDEF12345"]
    monkeypatch.setattr(web, "first_video_id", lambda q: None)
    registry.call("play_youtube", {"query": "dewa 19"})
    assert opened[-1].startswith("https://www.youtube.com/results?search_query=dewa+19")
    cfg.general.offline_only = True
    with pytest.raises(ToolError, match="offline"):
        registry.call("play_youtube", {"query": "x"})


# ── ±100 bahasa ──
def test_language_table_covers_whisper_and_resolves_names() -> None:
    assert len(language.WHISPER_LANGUAGES) == 100
    assert language.target_language("Jepang") == "Japanese"
    assert language.target_language("spanyol") == "Spanish"
    assert language.target_language("swahili") == "Swahili"
    assert language.target_language("sw") == "Swahili"
    assert language.target_language("tagalog") == "Tagalog"
    assert language.target_language("kucing") is None
    assert language.language_name("ja") == "Japanese"


def test_detect_candidates_all_skips_ambiguous_and_falls_back() -> None:
    allc = language.detect_candidates(["all"])
    assert allc[0] == "id" and "ja" in allc and "en" in allc
    assert not (set(allc) & language.AMBIGUOUS)
    assert language.detect_candidates(["xx"]) == ["id", "en"]
    assert language.detect_candidates(["id", "ja"]) == ["id", "ja"]


def test_guess_flags_other_scripts_and_latin_languages() -> None:
    assert language.guess("こんにちは、今日は天気がとても良いです") == "other"
    assert language.guess("Buenos días, hoy el clima es muy bueno") == "other"
    assert language.guess("Guten Morgen, ich bin sehr müde") == "other"
    assert language.guess("Baterai 80 persen, sedang diisi") == "id"


def test_speakable_leaves_foreign_text_alone() -> None:
    from jarvis.tts.stream import speakable

    assert speakable("今日は2026年11月11日です") == "今日は2026年11月11日です"
    assert speakable("Hoy es 11 de noviembre, hola") == "Hoy es 11 de noviembre, hola"


@pytest.mark.parametrize(
    ("said", "language_word"),
    [("ganti bahasa ke Jepang", "jepang"), ("Jarvis, ganti bahasa jadi Spanyol", "spanyol"),
     ("pakai bahasa Korea", "korea"), ("bicara bahasa Inggris", "inggris"),
     ("switch language to German", "german"), ("ganti ke otomatis", "otomatis")],
)  # fmt: skip
def test_set_language_rule(said, language_word) -> None:
    assert rules.match(said) == [Intent("set_language", {"language": language_word})]


def test_set_language_rule_ignores_unknown_languages_and_other_changes() -> None:
    assert rules.match("ganti bahasa ke kucing") is None
    assert rules.match("ganti wallpaper") is None


def test_set_language_tool_switches_and_restores(adapter) -> None:
    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    assert "Japanese" in registry.call("set_language", {"language": "jepang"})
    assert cfg.stt.language == "ja"
    registry.call("set_language", {"language": "otomatis"})
    assert cfg.stt.language == "auto"
    registry.call("set_language", {"language": "indonesia"})
    assert cfg.stt.language == "id"
    with pytest.raises(ToolError, match="tidak dikenal"):
        registry.call("set_language", {"language": "kucing"})


def test_translate_retries_with_smart_model_when_output_barely_changed(
    adapter, monkeypatch
) -> None:
    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    models: list[str] = []

    def fake(text, target, cfg=None, client=None):  # noqa: ANN001, ANN202
        models.append(cfg.llm.fast_model if cfg else "?")
        return text if len(models) == 1 else "Buongiorno a tutti, oggi fa bel tempo"

    monkeypatch.setattr(lang_tool, "run_translation", fake)
    out = registry.call(
        "translate", {"text": "selamat pagi semuanya hari ini cuaca bagus", "target": "italia"}
    )
    assert out.startswith("Buongiorno")
    assert models == ["?", cfg.llm.smart_model]  # percobaan kedua memakai model pintar


def test_stt_picks_a_non_indonesian_language_only_when_confident(stt_cls) -> None:
    cfg = Config().stt.model_copy(update={"language": "auto", "detect_languages": ["id", "ja"]})
    stt = stt_cls(cfg)
    FakeModel.probs = [("ja", 0.8), ("id", 0.1)]
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "ja" and stt.last_language == "ja"
    FakeModel.probs = [("ja", 0.3), ("id", 0.25)]  # kurang yakin → tetap Indonesia
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "id"
    FakeModel.probs = [("ko", 0.9), ("id", 0.05)]  # ko tidak ada di daftar → Indonesia
    stt.transcribe(AUDIO)
    assert FakeModel.seen[-1] == "id"


def test_open_app_ignores_trailing_words_that_are_not_part_of_the_name(adapter) -> None:
    context.configure(adapter, Config(), context.memory)
    out = registry.call("open_app", {"name": "Spotify kalo sama seperti ini"})
    assert out == "Siap, Spotify sudah dibuka"
    with pytest.raises(ToolError, match="tidak ditemukan"):
        registry.call("open_app", {"name": "Tidak Ada Sama Sekali"})
