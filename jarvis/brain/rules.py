"""Tier 0: perintah umum dikenali dengan regex, tanpa LLM (≈ 0 ms).

Teks dinormalisasi dulu (huruf kecil, tanpa tanda baca & kata pengisi, angka kata → digit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

FILLERS = {
    "jarvis", "tolong", "dong", "donk", "deh", "sih", "nih", "coba", "mohon",
    "bisa", "bisakah", "kamu", "ya", "yah", "aja", "saja", "dulu", "bro", "bang",
}  # fmt: skip

_UNITS = {
    "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
}  # fmt: skip
_NUM_WORDS = set(_UNITS) | {"sepuluh", "sebelas", "seratus", "belas", "puluh", "ratus"}

SITES = {
    "youtube": "youtube.com",
    "google": "google.com",
    "gmail": "mail.google.com",
    "github": "github.com",
    "whatsapp": "web.whatsapp.com",
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "twitter": "x.com",
    "tokopedia": "tokopedia.com",
}


_STATUS_WORDS = {
    "berapa", "tinggal", "sisa", "persen", "kepake", "kepakai", "terpakai", "dipakai", "pemakaian",
    "yang", "sekarang", "saat", "ini", "sudah", "udah", "masih", "penggunaan", "status", "cek",
    "baterai", "batre", "ram", "memori", "cpu", "prosesor",
}  # fmt: skip
_SUBJECTS = {
    "battery": {"baterai", "batre"},
    "ram": {"ram", "memori"},
    "cpu": {"cpu", "prosesor"},
}


@dataclass(frozen=True)
class Intent:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


def _parse_number_seq(toks: list[str]) -> int:
    total, i = 0, 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if t == "seratus":
            total += 100
        elif t == "sepuluh":
            total += 10
        elif t == "sebelas":
            total += 11
        elif t in _UNITS:
            u = _UNITS[t]
            if nxt == "belas":
                total, i = total + 10 + u, i + 1
            elif nxt == "puluh":
                total, i = total + u * 10, i + 1
            elif nxt == "ratus":
                total, i = total + u * 100, i + 1
            else:
                total += u
        i += 1
    return total


def words_to_digits(text: str) -> str:
    """'volume tiga puluh lima' → 'volume 35'."""
    out: list[str] = []
    seq: list[str] = []

    def flush() -> None:
        if seq:
            out.append(str(_parse_number_seq(seq)))
            seq.clear()

    for tok in text.split():
        if tok in _NUM_WORDS:
            seq.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return " ".join(out)


def normalize(text: str) -> str:
    text = text.lower().replace("%", " persen")
    text = re.sub(r"[^\w\s.]", " ", text)  # titik dipertahankan untuk alamat web (youtube.com)
    text = re.sub(r"(?<!\w)\.|\.(?!\w)", " ", text)
    toks = [t for t in text.split() if t not in FILLERS]
    return words_to_digits(" ".join(toks))


def _split_items(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s+(?:dan|lalu|sama|terus)\s+", raw) if p.strip()]


def _clean_app(item: str) -> str:
    item = re.sub(r"^(?:aplikasi|app|program)\s+", "", item)
    return re.sub(r"\s+(?:itu|nya|ini)$", "", item)


def _open_intent(item: str) -> Intent:
    item = _clean_app(item)
    if item in SITES:
        return Intent("open_url", {"url": SITES[item]})
    if "." in item and " " not in item:
        return Intent("open_url", {"url": item})
    return Intent("open_app", {"name": item.title()})


def match(text: str) -> list[Intent] | None:
    """Kembalikan daftar intent jika `text` cocok dengan salah satu aturan, selain itu None."""
    t = normalize(text)
    if not t:
        return None

    if m := re.fullmatch(
        r"(?:(?:atur|set|ubah|ganti)\s+)?volume(?:\s+(?:ke|jadi|menjadi))?\s+(\d{1,3})(?:\s+persen)?",
        t,
    ):
        return [Intent("set_volume", {"percent": int(m.group(1))})]
    if re.fullmatch(r"(?:mute|bisukan|matikan suara|diamkan suara|bisukan suara)", t):
        return [Intent("mute", {"on": True})]
    if re.fullmatch(r"(?:unmute|nyalakan suara|hidupkan suara|bunyikan(?: suara)?)(?: lagi)?", t):
        return [Intent("mute", {"on": False})]

    if re.fullmatch(r"(?:putar|play|lanjut|lanjutkan)(?: musik| lagu)?", t):
        return [Intent("media", {"action": "play_pause"})]
    if re.fullmatch(r"(?:pause|jeda|hentikan musik|stop musik)", t):
        return [Intent("media", {"action": "play_pause"})]
    if re.fullmatch(r"(?:(?:lagu )?(?:berikutnya|selanjutnya)|next|skip|ganti lagu)", t):
        return [Intent("media", {"action": "next"})]
    if re.fullmatch(r"(?:(?:lagu )?(?:sebelumnya)|previous|prev)", t):
        return [Intent("media", {"action": "prev"})]

    if re.fullmatch(r"(?:jam berapa(?: sekarang| ini)?|sekarang jam berapa)", t):
        return [Intent("get_time", {"what": "time"})]
    if re.fullmatch(r"(?:tanggal berapa|hari apa|hari ini hari apa)(?: hari ini| sekarang)?", t):
        return [Intent("get_time", {"what": "date"})]
    # Info sistem: hanya jika SEMUA kata berasal dari kosakata pertanyaan status (hindari
    # salah tangkap seperti "apa bedanya RAM dan SSD").
    words = set(t.split())
    if words <= _STATUS_WORDS:
        for kind, subjects in _SUBJECTS.items():
            if words & subjects:
                return [Intent("system_info", {"kind": kind})]

    if re.fullmatch(r"kunci (?:layar|komputer|laptop|mac|pc)", t):
        return [Intent("lock_screen")]
    if re.fullmatch(r"(?:matikan|shutdown|shut down) (?:komputer|laptop|pc|mac)", t):
        return [Intent("shutdown")]
    if re.fullmatch(r"(?:restart|mulai ulang|nyalakan ulang)(?: komputer| laptop| pc| mac)?", t):
        return [Intent("restart")]
    if re.fullmatch(r"(?:berhenti|stop|diam|cukup|sudah)", t):
        return [Intent("stop_speaking")]

    if m := re.fullmatch(r"(?:cari|carikan|googling)(?: di google)?\s+(.+)", t):
        return [Intent("web_search", {"query": m.group(1)})]
    if m := re.fullmatch(r"(?:tutup|quit|matikan aplikasi)\s+(.+)", t):
        return [
            Intent("close_app", {"name": _clean_app(i).title()}) for i in _split_items(m.group(1))
        ]
    if m := re.fullmatch(r"(?:buka|bukakan|jalankan)\s+(.+)", t):
        return [_open_intent(i) for i in _split_items(m.group(1))]
    return None


YES = {"ya", "iya", "yakin", "lanjut", "lanjutkan", "oke", "ok", "boleh", "silakan", "betul",
       "benar", "yes", "siap", "setuju"}  # fmt: skip
NO = {"tidak", "enggak", "nggak", "gak", "ga", "jangan", "batal", "batalkan", "cancel", "no",
      "stop", "bukan", "nanti"}  # fmt: skip


def parse_yes_no(text: str) -> bool | None:
    """True/False untuk jawaban konfirmasi, None jika tidak jelas. Kata 'tidak' selalu menang."""
    toks = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    if toks & NO:
        return False
    if toks & YES:
        return True
    return None
