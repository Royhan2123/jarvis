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
    return re.sub(r"\s+(?:itu|nya|ini|saya|ku)$", "", item)


def _open_intent(item: str) -> Intent:
    item = _clean_app(item)
    if item in SITES:
        return Intent("open_url", {"url": SITES[item]})
    if "." in item and " " not in item:
        return Intent("open_url", {"url": item})
    return Intent("open_app", {"name": item.title()})


_RAW_VERBS = (
    (re.compile(r"^\W*(?:jarvis\W+)?(?:tolong\s+)?ketik(?:kan)?\b\s*[:,]?\s*(.+)$", re.I | re.S),
     "type_text"),
    (re.compile(r"^\W*(?:jarvis\W+)?(?:tolong\s+)?catat(?:kan)?\b\s*[:,]?\s*(.+)$", re.I | re.S),
     "add_note"),
)  # fmt: skip
_WA = re.compile(
    r"^\W*(?:jarvis\W+)?(?:tolong\s+)?(?:kirim|tulis|buat|siapkan)(?:kan)?\s+(?:pesan\s+)?"
    r"(?:whatsapp|wa)\s+(?:ke\s+)?(\w+)\s*(?:isinya|bilang|katakan|:|,)?\s*(.+)$",
    re.I | re.S,
)
_AGENT = re.compile(
    r"^\W*(?:jarvis\W+)?(?:tolong\s+)?(?:agen|agent|kerjakan)\b\s*[:,]?\s*(.+)$", re.I | re.S
)
_ISLAND = re.compile(
    r"^\W*(?:jarvis\W+)?(?:tolong\s+)?(?:tampilkan|tunjukkan|kirim)\s+(?:ke\s+|di\s+)(?:pulau|isla)\b"
    r"\s*[:,]?\s*(.+)$",
    re.I | re.S,
)
_NO_ASK = re.compile(
    r"^(?:jangan|tidak usah|gak usah|ga usah|nggak usah|tak usah) tanya(?: izin)?(?: lagi)?"
    r"(?: untuk| soal| buat| sebelum)? (.+)$"
)
_ASK = re.compile(
    r"^(?:selalu|mulai|kembali) tanya(?: izin)?(?: lagi)?(?: untuk| soal| buat| sebelum)? (.+)$"
    r"|^tanya(?: izin)?(?: lagi)? (?:untuk|soal|buat|sebelum) (.+)$"  # "dulu" dibuang normalize()
)
_TR_VERB = r"(?:terjemahkan|terjemahin|artikan|translate)"
_TRANSLATE = (
    # "terjemahkan ke bahasa inggris: selamat pagi" / "translate to english: good morning"
    re.compile(
        rf"^\W*(?:jarvis\W+)?(?:tolong\s+|please\s+)?{_TR_VERB}\s+(?:ke|dalam|to|into)\s+"
        r"(?:bahasa\s+)?(\w+)\s*[:,]?\s*(.+)$",
        re.I | re.S,
    ),
    # "terjemahkan selamat pagi ke bahasa inggris" / "translate good morning to indonesian"
    re.compile(
        rf"^\W*(?:jarvis\W+)?(?:tolong\s+|please\s+)?{_TR_VERB}\s+(.+?)\s+"
        r"(?:ke|dalam|to|into)\s+(?:bahasa\s+)?(\w+)\W*$",
        re.I | re.S,
    ),
)
_HOW_SAY = (
    # "apa bahasa inggris dari selamat pagi" / "bagaimana bahasa inggrisnya terima kasih"
    re.compile(
        r"^\W*(?:jarvis\W+)?(?:apa|bagaimana)\s+bahasa\s+(\w+?)(?:nya)?\s+(?:dari\s+|untuk\s+)?"
        r"(.+?)\W*$",
        re.I | re.S,
    ),
    # "how do you say thank you in indonesian"
    re.compile(
        r"^\W*(?:jarvis\W+)?how (?:do you|to|would you) say\s+(.+?)\s+in\s+(\w+)\W*$", re.I | re.S
    ),
)
_UNIT_MIN = {"detik": 1 / 60, "menit": 1.0, "jam": 60.0}


def _match_translate(text: str) -> list[Intent] | None:
    from jarvis.brain.language import target_language

    s = text.strip()
    for i, pat in enumerate(_TRANSLATE):
        if m := pat.match(s):
            lang, body = (m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
            if target_language(lang):
                return [Intent("translate", {"text": body.strip(), "target": lang.lower()})]
    for i, pat in enumerate(_HOW_SAY):
        if m := pat.match(s):
            lang, body = (m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
            if target_language(lang):
                return [Intent("translate", {"text": body.strip(), "target": lang.lower()})]
    return None


def _match_raw(text: str) -> list[Intent] | None:
    """Perintah yang isinya harus persis seperti diucapkan (ketik/catat): jangan dinormalisasi."""
    if tr := _match_translate(text):
        return tr
    if m := _ISLAND.match(text.strip()):
        return [Intent("show_on_island", {"text": m.group(1).strip()})]
    if m := _AGENT.match(text.strip()):
        return [Intent("run_agent", {"task": m.group(1).strip()})]
    if m := _WA.match(text.strip()):
        return [Intent("whatsapp_draft", {"contact": m.group(1), "message": m.group(2).strip()})]
    for pat, tool in _RAW_VERBS:
        if m := pat.match(text.strip()):
            return [Intent(tool, {"text": m.group(1).strip()})]
    return None


def match(text: str) -> list[Intent] | None:
    """Kembalikan daftar intent jika `text` cocok dengan salah satu aturan, selain itu None."""
    if raw := _match_raw(text):
        return raw
    t = normalize(text)
    if not t:
        return None

    if m := re.fullmatch(
        r"ingatkan(?: saya)?(?: untuk)? (.+?) (\d+(?:\.\d+)?) (menit|jam|detik) lagi", t
    ):
        return [
            Intent(
                "set_reminder",
                {"text": m.group(1), "minutes": float(m.group(2)) * _UNIT_MIN[m.group(3)]},
            )
        ]
    if m := re.fullmatch(
        r"ingatkan(?: saya)? (\d+(?:\.\d+)?) (menit|jam|detik) lagi(?: untuk)? (.+)", t
    ):
        return [
            Intent(
                "set_reminder",
                {"text": m.group(3), "minutes": float(m.group(1)) * _UNIT_MIN[m.group(2)]},
            )
        ]
    if m := _NO_ASK.match(t):
        from jarvis.agent import policy

        if action := policy.resolve_action(m.group(1)):
            return [Intent("agent_auto_approve", {"action": action})]
    if m := _ASK.match(t):
        from jarvis.agent import policy

        if action := policy.resolve_action(m.group(1) or m.group(2) or ""):
            return [Intent("agent_ask_always", {"action": action})]
    if re.fullmatch(r"(?:bacakan|baca) catatan(?: saya)?|catatan saya apa(?: saja)?", t):
        return [Intent("list_notes")]
    if m := re.fullmatch(r"(?:nama saya|namaku|panggil saya)\s+(.+)", t):
        return [Intent("remember_fact", {"key": "nama", "value": m.group(1).title()})]
    if m := re.fullmatch(r"(?:saya|aku) tinggal di\s+(.+)", t):
        return [Intent("remember_fact", {"key": "kota", "value": m.group(1).title()})]
    if re.fullmatch(
        r"(?:rangkum|baca|jelaskan) (?:isi )?layar(?: ini)?"
        r"|apa (?:yang )?(?:ada )?di layar(?: ini)?",
        t,
    ):
        return [Intent("read_screen", {"question": "Rangkum isi layar ini secara singkat"})]
    if re.fullmatch(r"ini error apa|error apa ini|kenapa error ini", t):
        return [
            Intent("read_screen", {"question": "Ada error apa di layar ini dan apa penyebabnya?"})
        ]

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

    if m := re.fullmatch(
        r"(?:bagaimana |gimana |apa )?(?:cek )?cuaca(?: hari ini)?"
        r"(?: di ([a-z ]+?))?(?: hari ini| sekarang)?",
        t,
    ):
        city = (m.group(1) or "").strip()
        return [Intent("get_weather", {"city": city.title()})]
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
        if re.match(r"(?:di |dalam )?(?:dokumen|berkas|arsip|file)\b", m.group(1)):
            return None  # pencarian dokumen pribadi → LLM + tool search_docs, bukan web
        return [Intent("web_search", {"query": m.group(1)})]
    if m := re.fullmatch(r"(?:tutup|quit|matikan aplikasi)\s+(.+)", t):
        return [
            Intent("close_app", {"name": _clean_app(i).title()}) for i in _split_items(m.group(1))
        ]
    if m := re.fullmatch(r"(?:buka|bukakan|jalankan)\s+(.+)", t):
        return [_open_intent(i) for i in _split_items(m.group(1))]
    from jarvis.brain import rules_en

    return rules_en.match(t, _open_intent, _clean_app)


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


_DEVICE_VERBS = {
    "nyalakan": "on", "hidupkan": "on", "nyalain": "on", "matikan": "off", "matiin": "off",
}  # fmt: skip


def match_devices(text: str, names: list[str]) -> list[Intent] | None:
    """'nyalakan lampu ruang tamu' → device_control, hanya jika nama cocok perangkat terdaftar."""
    t = normalize(text)
    for name in sorted(names, key=len, reverse=True):
        n = " ".join(name.lower().split())
        for verb, action in _DEVICE_VERBS.items():
            if re.fullmatch(rf"{verb} {re.escape(n)}", t):
                return [Intent("device_control", {"name": name, "action": action})]
        if re.fullmatch(rf"(?:apakah |apa )?{re.escape(n)} (?:sedang )?(?:menyala|nyala|mati)", t):
            return [Intent("device_state", {"name": name})]
    return None
