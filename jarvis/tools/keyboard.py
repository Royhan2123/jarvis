"""Tool keyboard: ketik teks ke jendela aktif."""

from __future__ import annotations

import re

from jarvis.tools.registry import ToolError, context, tool

MAX_CHARS = 500


def clean_typed_text(text: str) -> str:
    """Satu baris saja, tanpa Enter/Tab/karakter kontrol (cegah eksekusi di terminal)."""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = "".join(c for c in text if c.isprintable())
    text = text.strip()
    if not text:
        raise ToolError("Tidak ada teks yang bisa diketik")
    return text[:MAX_CHARS]


@tool(
    name="type_text",
    description="Mengetik teks ke jendela atau aplikasi yang sedang aktif",
    risk="medium",
    category="keyboard",
)
def type_text(text: str) -> str:
    context.adapter.type_text(clean_typed_text(text))
    return "Sudah saya ketik"
