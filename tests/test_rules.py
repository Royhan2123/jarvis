from __future__ import annotations

import pytest

from jarvis.brain.rules import Intent, match, normalize, parse_yes_no, words_to_digits


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("tiga puluh lima", "35"),
        ("seratus", "100"),
        ("sebelas", "11"),
        ("dua belas", "12"),
        ("seratus dua puluh", "120"),
        ("volume lima puluh", "volume 50"),
    ],
)
def test_words_to_digits(said, expected) -> None:
    assert words_to_digits(said) == expected


def test_normalize() -> None:
    assert normalize("Jarvis, tolong buka Spotify dong!") == "buka spotify"
    assert normalize("Volume 30%") == "volume 30 persen"
    assert normalize("buka youtube.com.") == "buka youtube.com"


@pytest.mark.parametrize(
    ("said", "tool", "args"),
    [
        ("Volume 30 persen", "set_volume", {"percent": 30}),
        ("tolong atur volume ke tiga puluh", "set_volume", {"percent": 30}),
        ("volume 80%", "set_volume", {"percent": 80}),
        ("Mute", "mute", {"on": True}),
        ("nyalakan suara", "mute", {"on": False}),
        ("putar musik", "media", {"action": "play_pause"}),
        ("pause", "media", {"action": "play_pause"}),
        ("lagu berikutnya", "media", {"action": "next"}),
        ("lagu sebelumnya", "media", {"action": "prev"}),
        ("Jam berapa sekarang?", "get_time", {"what": "time"}),
        ("hari apa", "get_time", {"what": "date"}),
        ("baterai tinggal berapa?", "system_info", {"kind": "battery"}),
        ("RAM kepake berapa?", "system_info", {"kind": "ram"}),
        ("kunci layar", "lock_screen", {}),
        ("matikan komputer", "shutdown", {}),
        ("restart", "restart", {}),
        ("berhenti", "stop_speaking", {}),
        ("cari resep rendang", "web_search", {"query": "resep rendang"}),
        ("buka spotify", "open_app", {"name": "Spotify"}),
        ("tutup chrome", "close_app", {"name": "Chrome"}),
        ("buka youtube", "open_url", {"url": "youtube.com"}),
        ("buka github.com", "open_url", {"url": "github.com"}),
        ("tolong bukakan aplikasi kalkulator itu", "open_app", {"name": "Kalkulator"}),
    ],
)
def test_rule_matches(said, tool, args) -> None:
    got = match(said)
    assert got == [Intent(tool, args)]


def test_multiple_apps() -> None:
    assert match("buka vs code dan spotify") == [
        Intent("open_app", {"name": "Vs Code"}),
        Intent("open_app", {"name": "Spotify"}),
    ]


@pytest.mark.parametrize(
    "said",
    ["apa ibu kota jepang", "jelaskan cara kerja blockchain", "", "ceritakan lelucon", "volume"],
)
def test_no_match_goes_to_llm(said) -> None:
    assert match(said) is None


def test_shutdown_not_mistaken_for_close_app() -> None:
    assert match("matikan komputer")[0].tool == "shutdown"
    assert match("matikan aplikasi chrome")[0].tool == "close_app"


@pytest.mark.parametrize(
    ("said", "ans"),
    [("ya", True), ("iya, yakin", True), ("tidak", False), ("jangan", False),
     ("tidak yakin", False), ("terima kasih", None), ("", None)],
)  # fmt: skip
def test_parse_yes_no(said, ans) -> None:
    assert parse_yes_no(said) is ans


@pytest.mark.parametrize(
    "said",
    [
        "apa bedanya RAM dan SSD",
        "kenapa baterai laptop cepat habis",
        "RAM itu apa",
        "ceritakan tentang cpu",
    ],
)
def test_info_rules_do_not_hijack_questions(said) -> None:
    assert match(said) is None


def test_type_and_note_keep_exact_text() -> None:
    assert match("Ketik: Halo, Meeting diundur jam 3.") == [
        Intent("type_text", {"text": "Halo, Meeting diundur jam 3."})
    ]
    assert match("tolong catat beli kopi besok") == [
        Intent("add_note", {"text": "beli kopi besok"})
    ]
    assert match("catatan saya apa saja") == [Intent("list_notes")]


def test_reminder_rules() -> None:
    assert match("ingatkan saya 10 menit lagi minum obat") == [
        Intent("set_reminder", {"text": "minum obat", "minutes": 10.0})
    ]
    assert match("ingatkan saya untuk minum obat 2 jam lagi") == [
        Intent("set_reminder", {"text": "minum obat", "minutes": 120.0})
    ]
    assert match("ingatkan saya tiga puluh detik lagi cek oven")[0].args["minutes"] == 0.5


def test_memory_and_screen_rules() -> None:
    assert match("nama saya Roy") == [Intent("remember_fact", {"key": "nama", "value": "Roy"})]
    assert match("rangkum isi layar ini")[0].tool == "read_screen"
    assert match("ini error apa")[0].tool == "read_screen"
    assert match("jelaskan cara kerja layar sentuh") is None
