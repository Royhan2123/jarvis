"""Tool layar: baca & rangkum isi layar dengan model vision."""

from __future__ import annotations

from jarvis.brain import vision
from jarvis.tools.registry import ToolError, context, tool


@tool(
    name="read_screen",
    description="Membaca isi layar komputer lalu merangkum atau menjawab pertanyaan tentang layar",
    risk="low",
    category="screen",
)
def read_screen(question: str = "Rangkum isi layar ini secara singkat") -> str:
    png = context.adapter.screenshot()
    try:
        answer = vision.describe(png, question, context.cfg)
    except Exception as e:  # noqa: BLE001 — Ollama mati / model vision belum ada
        raise ToolError(f"Model vision tidak bisa dipakai: {e}") from e
    return answer or "Saya tidak bisa membaca apa pun dari layar ini"
