"""Balasan tool dalam bahasa Inggris untuk pengguna yang berbicara Inggris.

Tool menghasilkan kalimat Indonesia; di sini kalimat yang paling umum dialihkan ke Inggris dengan
templat (cepat, tanpa LLM). Kalimat yang tidak dikenal dibiarkan apa adanya.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_DAYS = {"Senin": "Monday", "Selasa": "Tuesday", "Rabu": "Wednesday", "Kamis": "Thursday",
         "Jumat": "Friday", "Sabtu": "Saturday", "Minggu": "Sunday"}  # fmt: skip
_MONTHS = {"Januari": "January", "Februari": "February", "Maret": "March", "April": "April",
           "Mei": "May", "Juni": "June", "Juli": "July", "Agustus": "August",
           "September": "September", "Oktober": "October", "November": "November",
           "Desember": "December"}  # fmt: skip


def _clock(m: re.Match[str]) -> str:
    h, minute = int(m.group(1)), m.group(2)
    return f"It's {h % 12 or 12}:{minute} {'AM' if h < 12 else 'PM'}"


def _date(m: re.Match[str]) -> str:
    day, d, month, year = m.groups()
    return f"Today is {_DAYS.get(day, day)}, {_MONTHS.get(month, month)} {d}, {year}"


_RULES: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str] | str]] = [
    (re.compile(r"^Sekarang jam (\d{1,2})\.(\d{2})$"), _clock),
    (re.compile(r"^Hari ini (\w+), (\d{1,2}) (\w+) (\d{4})$"), _date),
    (re.compile(r"^Siap, (.+) sudah dibuka$"), r"Opening \1"),
    (re.compile(r"^Oke, (.+) sudah ditutup$"), r"Closed \1"),
    (re.compile(r"^Aplikasi (.+) tidak ditemukan$"), r"I couldn't find the app \1"),
    (re.compile(r"^(.+) tidak sedang berjalan$"), r"\1 isn't running"),
    (re.compile(r"^Volume sekarang (\d+) persen$"), r"Volume is now \1 percent"),
    (re.compile(r"^Baterai (\d+) persen, sedang diisi$"), r"Battery is at \1 percent, charging"),
    (re.compile(r"^Baterai (\d+) persen, tidak diisi$"), r"Battery is at \1 percent, not charging"),
    (re.compile(r"^RAM terpakai (\d+) persen$"), r"RAM usage is \1 percent"),
    (re.compile(r"^CPU terpakai (\d+) persen$"), r"CPU usage is \1 percent"),
    (re.compile(r"^Oke, dibatalkan\.$"), "Okay, cancelled."),
    (re.compile(r"^Yakin mau (.+)\? Bilang ya atau tidak\.$"),
     "Are you sure you want to do that? Say yes or no."),
]  # fmt: skip


def to_english(text: str) -> str:
    """Terjemahkan kalimat hasil tool yang dikenal ke Inggris; selainnya dikembalikan apa adanya."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip()) if text else []:
        for pattern, repl in _RULES:
            if m := pattern.match(sentence.strip()):
                sentence = m.expand(repl) if isinstance(repl, str) else repl(m)
                break
        out.append(sentence)
    return " ".join(out)
