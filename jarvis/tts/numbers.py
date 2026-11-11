"""Angka → kata Indonesia sebelum diucapkan.

Mesin suara (terutama Fish) membaca angka berbentuk digit dengan ngawur ("19.43" jadi gumaman
asing), jadi semua angka dieja dulu: 80 → "delapan puluh", 2026 → "dua ribu dua puluh enam",
3,14 → "tiga koma satu empat", jam 19.43 → "sembilan belas empat puluh tiga".
"""

from __future__ import annotations

import re

_UNITS = ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan",
          "sepuluh", "sebelas"]  # fmt: skip
_SCALES = [(10**12, "triliun"), (10**9, "miliar"), (10**6, "juta"), (10**3, "ribu")]
MAX_SPELLED = 10**15


def terbilang(n: int) -> str:
    """Ejaan bilangan bulat tak negatif dalam bahasa Indonesia (di atas 10^15: digit per digit)."""
    if n >= MAX_SPELLED:
        return " ".join(_UNITS[int(d)] for d in str(n))
    if n < 12:
        return _UNITS[n]
    if n < 20:
        return f"{_UNITS[n - 10]} belas"
    if n < 100:
        rest = n % 10
        return f"{_UNITS[n // 10]} puluh" + (f" {_UNITS[rest]}" if rest else "")
    if n < 1000:
        head = "seratus" if n // 100 == 1 else f"{_UNITS[n // 100]} ratus"
        return head + (f" {terbilang(n % 100)}" if n % 100 else "")
    for size, name in _SCALES:
        if n >= size:
            q, rest = divmod(n, size)
            head = "seribu" if (size == 1000 and q == 1) else f"{terbilang(q)} {name}"
            return head + (f" {terbilang(rest)}" if rest else "")
    return str(n)  # tak tercapai


def _digits(s: str) -> str:
    return " ".join(_UNITS[int(c)] for c in s)


def _int_words(s: str) -> str:
    """'007' / nomor panjang dibaca per digit; selainnya sebagai bilangan."""
    if (len(s) > 1 and s[0] == "0") or len(s) > 15:
        return _digits(s)
    return terbilang(int(s))


_CLOCK = re.compile(r"(?<![\d.,:])(\d{1,2})[.:](\d{2})(?![\d])")
_THOUSANDS = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?![\d.,])")
_VERSION = re.compile(r"(?<![\d.,])\d+(?:\.\d+){2,}(?![\d])")  # 1.2.3
_DECIMAL = re.compile(r"(?<![\d.,])(\d+)[.,](\d+)(?![\d])")
_INT = re.compile(r"\d+")


def _clock(m: re.Match[str]) -> str:
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return m.group(0)
    if minute == 0:
        return terbilang(hour)
    zero = "nol " if minute < 10 else ""  # 07.05 → "tujuh nol lima"
    return f"{terbilang(hour)} {zero}{terbilang(minute)}"


def spell_numbers(text: str) -> str:
    """Eja semua angka dalam `text` (teks Indonesia)."""
    text = text.replace("%", " persen")
    # Jam hanya bila didahului "jam"/"pukul" atau memakai titik dua (19:43); "3.14" itu desimal.
    text = re.sub(
        r"\b(jam|pukul)\s+(\d{1,2})[.:](\d{2})\b",
        lambda m: f"{m.group(1)} {_clock(re.match(_CLOCK, m.group(2) + ':' + m.group(3)))}",
        text,
        flags=re.I,
    )
    text = re.sub(r"(?<![\d.,])(\d{1,2}):(\d{2})(?![\d])", _clock, text)
    text = _THOUSANDS.sub(lambda m: _int_words(m.group(0).replace(".", "")), text)
    text = _VERSION.sub(
        lambda m: " titik ".join(_int_words(p) for p in m.group(0).split(".")), text
    )
    text = _DECIMAL.sub(lambda m: f"{_int_words(m.group(1))} koma {_digits(m.group(2))}", text)
    return _INT.sub(lambda m: _int_words(m.group(0)), text)
