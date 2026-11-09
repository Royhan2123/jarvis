"""Draf pesan WhatsApp: membuka chat dengan teks terisi. KAMU yang menekan kirim.

Tidak ada pengiriman otomatis: salah dengar tidak akan mengirim pesan ke orang yang salah.
Hanya kontak yang terdaftar di `messaging.contacts` (nama → nomor).
"""

from __future__ import annotations

import re
import urllib.parse
import webbrowser

from jarvis.tools.registry import ToolError, context, tool


def _clean(text: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", text).strip()[:500]


@tool(
    name="whatsapp_draft",
    description="Menyiapkan pesan WhatsApp ke kontak, chat terbuka dengan teks terisi",
    risk="medium",
    category="messaging",
)
def whatsapp_draft(contact: str, message: str) -> str:
    contacts = {k.lower().strip(): v for k, v in context.cfg.messaging.contacts.items()}
    key = " ".join(contact.lower().split())
    number = re.sub(r"[\s\-()+]", "", contacts.get(key, ""))
    if not number:
        known = ", ".join(context.cfg.messaging.contacts) or "(belum ada)"
        raise ToolError(f"Kontak {contact} tidak dikenal. Yang terdaftar: {known}")
    if not re.fullmatch(r"\d{8,15}", number):
        raise ToolError(f"Nomor kontak {contact} tidak valid, pakai format 62812xxxx")
    text = _clean(message)
    if not text:
        raise ToolError("Isi pesannya kosong")
    url = f"https://wa.me/{number}?text={urllib.parse.quote(text)}"
    if not webbrowser.open(url):
        raise ToolError("WhatsApp tidak bisa dibuka")
    return f"Pesan untuk {contact} sudah disiapkan di WhatsApp, tinggal kamu kirim"
