"""Tool memori: catatan, pengingat, dan fakta tentang pengguna."""

from __future__ import annotations

import time
from datetime import datetime

from jarvis.tools.registry import ToolError, context, tool

MAX_MINUTES = 60 * 24 * 7


def _clean(text: str, limit: int) -> str:
    text = " ".join(text.split())[:limit]
    if not text:
        raise ToolError("Teksnya kosong")
    return text


@tool(
    name="add_note",
    description="Mencatat sesuatu ke catatan pengguna, misalnya beli kopi besok",
    risk="low",
    category="notes",
)
def add_note(text: str) -> str:
    text = _clean(text, 300)
    mem = context.memory
    mem.add_note(text)
    md = mem.path.with_name("notes.md")  # salinan Markdown yang bisa dibuka pengguna
    with md.open("a", encoding="utf-8") as f:
        f.write(f"- {datetime.now():%Y-%m-%d %H:%M} — {text}\n")
    return "Sudah saya catat"


@tool(
    name="list_notes",
    description="Membacakan catatan terbaru milik pengguna",
    risk="low",
    category="notes",
)
def list_notes(limit: int = 3) -> str:
    notes = context.memory.notes(max(1, min(limit, 10)))
    if not notes:
        return "Belum ada catatan"
    return "Catatan terakhir: " + ". ".join(notes)


@tool(
    name="set_reminder",
    description="Mengingatkan pengguna beberapa menit lagi, misalnya minum obat 10 menit lagi",
    risk="low",
    category="notes",
)
def set_reminder(text: str, minutes: float) -> str:
    text = _clean(text, 200)
    if not 0.1 <= minutes <= MAX_MINUTES:
        raise ToolError("Waktu pengingat harus antara beberapa detik sampai tujuh hari")
    context.memory.add_reminder(time.time() + minutes * 60, text)
    if minutes < 1:
        waktu = f"{round(minutes * 60)} detik"
    elif minutes >= 120:
        waktu = f"{round(minutes / 60)} jam"
    else:
        waktu = f"{round(minutes)} menit"
    return f"Siap, saya ingatkan {waktu} lagi: {text}"


@tool(
    name="remember_fact",
    description="Mengingat fakta tentang pengguna, misalnya nama = Roy atau kota = Jakarta",
    risk="low",
    category="notes",
)
def remember_fact(key: str, value: str) -> str:
    key, value = _clean(key, 40), _clean(value, 120)
    context.memory.set_fact(key, value)
    return f"Oke, saya ingat {key} kamu {value}"
