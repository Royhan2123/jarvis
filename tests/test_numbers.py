from __future__ import annotations

import pytest

from jarvis.tts.numbers import spell_numbers, terbilang
from jarvis.tts.stream import speakable


@pytest.mark.parametrize(
    ("n", "words"),
    [
        (0, "nol"), (7, "tujuh"), (11, "sebelas"), (12, "dua belas"), (19, "sembilan belas"),
        (20, "dua puluh"), (21, "dua puluh satu"), (100, "seratus"), (101, "seratus satu"),
        (111, "seratus sebelas"), (250, "dua ratus lima puluh"), (1000, "seribu"),
        (1100, "seribu seratus"), (2026, "dua ribu dua puluh enam"),
        (12000, "dua belas ribu"), (100000, "seratus ribu"),
        (1250000, "satu juta dua ratus lima puluh ribu"),
        (2000000000, "dua miliar"),
    ],
)  # fmt: skip
def test_terbilang(n, words) -> None:
    assert terbilang(n) == words


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("Sekarang jam 19.43", "Sekarang jam sembilan belas empat puluh tiga"),
        ("Pukul 07:05 pagi", "Pukul tujuh nol lima pagi"),
        ("Rabu, 11 November 2026", "Rabu, sebelas November dua ribu dua puluh enam"),
        ("Baterai 80 persen", "Baterai delapan puluh persen"),
        ("Volume 30%", "Volume tiga puluh persen"),
        ("Suhu 27,5 derajat", "Suhu dua puluh tujuh koma lima derajat"),
        ("Harganya 1.250.000 rupiah", "Harganya satu juta dua ratus lima puluh ribu rupiah"),
        ("Hubungi 0812", "Hubungi nol delapan satu dua"),
        ("Tidak ada angka di sini.", "Tidak ada angka di sini."),
    ],
)  # fmt: skip
def test_spell_numbers(text, spoken) -> None:
    assert spell_numbers(text) == spoken


def test_decimal_that_looks_like_a_clock_is_a_decimal() -> None:
    assert spell_numbers("Nilainya 3.14") == "Nilainya tiga koma satu empat"


def test_speakable_spells_indonesian_and_leaves_english_alone() -> None:
    assert (
        speakable("Angka pi adalah 3,141592653589793.") == "Angka pi adalah tiga koma satu empat."
    )
    assert speakable("Ada 3 file") == "Ada tiga file"
    assert speakable("Paris is the capital of France in 2026.") == (
        "Paris is the capital of France in 2026."
    )
