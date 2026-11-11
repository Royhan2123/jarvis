"""Perintah dasar dalam bahasa Inggris (Tier 0), dipanggil `rules.match` setelah aturan Indonesia.

Menerima teks yang sudah dinormalisasi (huruf kecil, tanpa tanda baca; "what's" jadi "what s").
Sengaja kecil: hanya perintah yang sering dipakai. Sisanya ditangani LLM dengan tool.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from jarvis.brain.rules import Intent

_FILL = {"please", "hey", "could", "can", "you", "would", "the", "a", "my"}


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
