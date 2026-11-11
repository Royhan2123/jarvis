"""Perintah dasar dalam bahasa Inggris (Tier 0), dipanggil `rules.match` setelah aturan Indonesia.

Menerima teks yang sudah dinormalisasi (huruf kecil, tanpa tanda baca; "what's" jadi "what s").
Sengaja kecil: hanya perintah yang sering dipakai. Sisanya ditangani LLM dengan tool.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from jarvis.brain.rules import Intent

_FILL = {"please", "hey", "could", "can", "you", "would", "the", "a", "my"}


_P = r"^\W*(?:jarvis\W+)?(?:please\s+)?(?:(?:could|can|would) you\s+(?:please\s+)?)?"
_RAW = (
    (re.compile(_P + r"(?:take a note|make a note|note down|note)\b\s*[:,]?\s*(?:that\s+)?(.+)$",
                re.I | re.S), "add_note", "text"),
    (re.compile(_P + r"type\b\s*[:,]?\s*(.+)$", re.I | re.S), "type_text", "text"),
    (re.compile(_P + r"(?:work on|agent)\b\s*[:,]?\s*(.+)$", re.I | re.S), "run_agent", "task"),
)  # fmt: skip
_WA = re.compile(
    _P + r"(?:send|write|draft|make)\s+(?:a\s+)?(?:whatsapp|wa)(?:\s+message)?\s+(?:to\s+)?(\w+)"
    r"\s*(?:saying|that says|:|,)?\s*(.+)$",
    re.I | re.S,
)
_UNIT_MIN = {"second": 1 / 60, "seconds": 1 / 60, "minute": 1.0, "minutes": 1.0,
             "hour": 60.0, "hours": 60.0}  # fmt: skip


def match_raw(text: str) -> list[Intent] | None:
    """Perintah Inggris yang isinya harus persis seperti diucapkan (catatan, ketik, pesan)."""
    s = text.strip()
    if m := _WA.match(s):
        return [Intent("whatsapp_draft", {"contact": m.group(1), "message": m.group(2).strip()})]
    for pat, tool, arg in _RAW:
        if m := pat.match(s):
            return [Intent(tool, {arg: m.group(1).strip()})]
    return None


def match(
    t: str,
    open_intent: Callable[[str], Intent],
    clean_app: Callable[[str], str],
) -> list[Intent] | None:
    words = [w for w in t.split() if w not in _FILL]
    t = " ".join(words)
    if m := re.fullmatch(r"(?:set )?volume(?: to)? (\d{1,3})(?: percent)?", t):
        return [Intent("set_volume", {"percent": int(m.group(1))})]
    if re.fullmatch(r"(?:mute|mute sound|mute volume|silence)", t):
        return [Intent("mute", {"on": True})]
    if re.fullmatch(r"(?:unmute|unmute sound|unmute volume)", t):
        return [Intent("mute", {"on": False})]
    if re.fullmatch(r"(?:play|resume|play music|resume music|pause|pause music|stop music)", t):
        return [Intent("media", {"action": "play_pause"})]
    if re.fullmatch(r"(?:next|next song|next track|skip|skip song|skip track)", t):
        return [Intent("media", {"action": "next"})]
    if re.fullmatch(r"(?:previous|previous song|previous track|prev|go back)", t):
        return [Intent("media", {"action": "prev"})]
    if re.fullmatch(r"(?:what time is it|what s the time|what is the time|time|tell time)", t):
        return [Intent("get_time", {"what": "time"})]
    if re.fullmatch(
        r"(?:what s|what is)(?: today s| the)? date(?: today)?"
        r"|what day is it(?: today)?|today s date",
        t,
    ):
        return [Intent("get_time", {"what": "date"})]
    if m := re.fullmatch(
        r"(?:what s|what is|how s|how is) weather(?: in ([a-z ]+?))?(?: today)?", t
    ):
        return [Intent("get_weather", {"city": (m.group(1) or "").strip().title()})]
    if m := re.fullmatch(
        r"(?:what s|what is|check) (?:battery|ram|memory|cpu)(?: level| usage)?", t
    ):
        kind = "battery" if "battery" in t else "cpu" if "cpu" in t else "ram"
        return [Intent("system_info", {"kind": kind})]
    if m := re.fullmatch(
        r"remind me(?: to)? (.+?) in (\d+(?:\.\d+)?) (minutes?|hours?|seconds?)", t
    ):
        return [
            Intent(
                "set_reminder",
                {"text": m.group(1), "minutes": float(m.group(2)) * _UNIT_MIN[m.group(3)]},
            )
        ]
    if m := re.fullmatch(
        r"remind me in (\d+(?:\.\d+)?) (minutes?|hours?|seconds?)(?: to)? (.+)", t
    ):
        return [
            Intent(
                "set_reminder",
                {"text": m.group(3), "minutes": float(m.group(1)) * _UNIT_MIN[m.group(2)]},
            )
        ]
    if re.fullmatch(
        r"(?:read|read out|list|what are) notes|read notes? back|what notes do i have", t
    ):
        return [Intent("list_notes")]
    if m := re.fullmatch(r"(?:name is|call me|i am called)\s+(.+)", t):
        return [Intent("remember_fact", {"key": "nama", "value": m.group(1).title()})]
    if m := re.fullmatch(r"i live in\s+(.+)", t):
        return [Intent("remember_fact", {"key": "kota", "value": m.group(1).title()})]
    if re.fullmatch(
        r"(?:summarize|read|explain|describe)(?: what s on)?(?: this| my)? screen"
        r"|what s on(?: this| my)? screen",
        t,
    ):
        return [Intent("read_screen", {"question": "Summarize what is on this screen briefly"})]
    if re.fullmatch(r"what s this error|what error is this|why is there an error", t):
        return [Intent("read_screen", {"question": "What error is on screen and what causes it?"})]
    if re.fullmatch(
        r"(?:what s|what is|check)(?: on)?(?: my)? (?:calendar|schedule|agenda)(?: today)?"
        r"|what do i have today|what meetings do i have(?: today)?",
        t,
    ):
        return [Intent("calendar_events", {"days": 1})]
    if re.fullmatch(
        r"(?:check|read) (?:email|emails|mail|inbox)"
        r"|(?:do i have )?(?:any )(?:new |unread )?emails?|do i have (?:new |unread )?emails?",
        t,
    ):
        return [Intent("unread_emails")]
    if re.fullmatch(r"(?:shut down|shutdown|turn off)(?: computer| laptop| pc| mac)?", t):
        return [Intent("shutdown")]
    if re.fullmatch(r"restart(?: computer| laptop| pc| mac)?", t):
        return [Intent("restart")]
    if re.fullmatch(r"lock(?: screen| computer| laptop| mac| pc)?", t):
        return [Intent("lock_screen")]
    if re.fullmatch(r"(?:stop|be quiet|quiet|enough|stop talking|shut up)", t):
        return [Intent("stop_speaking")]
    if m := re.fullmatch(r"(?:search google for|search for|search|google|look up)\s+(.+)", t):
        return [Intent("web_search", {"query": m.group(1)})]
    if m := re.fullmatch(r"(?:close|quit)\s+(.+)", t):
        items = re.split(r"\s+(?:and|then)\s+", m.group(1))
        return [Intent("close_app", {"name": clean_app(i).title()}) for i in items if i]
    if m := re.fullmatch(r"(?:open|launch|start)\s+(.+)", t):
        return [open_intent(i) for i in re.split(r"\s+(?:and|then)\s+", m.group(1)) if i]
    return None
