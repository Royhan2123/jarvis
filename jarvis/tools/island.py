"""Tool pulau Isla: tampilkan teks di pulau notifikasi Isla Desk."""

from __future__ import annotations

from jarvis import island
from jarvis.tools.registry import ToolError, context, tool


@tool(
    name="show_on_island",
    description="Menampilkan pesan singkat di pulau notifikasi Isla Desk di layar",
    risk="low",
    category="island",
)
def show_on_island(text: str) -> str:
    cfg = context.cfg
    if not cfg.island.enabled:
        raise ToolError("Sambungan Isla belum diaktifkan. Setel island.enabled: true")
    if not island.notify(cfg, text):
        raise ToolError("Isla Desk tidak berjalan atau tidak terjangkau")
    # Isla hanya membalas "diterima": pesan bisa dibuang (Jangan Ganggu) atau tak terlihat (Space).
    return "Sudah saya kirim ke pulau Isla"
