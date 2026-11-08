"""Tool audio & media: volume, mute, kontrol pemutar."""

from __future__ import annotations

from typing import Literal

from jarvis.tools.registry import context, tool


@tool(
    name="set_volume",
    description="Mengatur volume suara komputer, angka 0 sampai 100 persen",
    risk="low",
    category="media",
)
def set_volume(percent: int) -> str:
    percent = max(0, min(100, percent))
    context.adapter.set_volume(percent)
    return f"Volume sekarang {percent} persen"


@tool(
    name="mute",
    description="Membisukan suara komputer (on=true) atau menyalakannya lagi (on=false)",
    risk="low",
    category="media",
)
def mute(on: bool = True) -> str:
    context.adapter.mute(on)
    return "Suara dibisukan" if on else "Suara dinyalakan lagi"


@tool(
    name="media",
    description="Kontrol pemutar musik: play_pause, next (lagu berikutnya), prev (lagu sebelumnya)",
    risk="low",
    category="media",
)
def media(action: Literal["play_pause", "next", "prev"]) -> str:
    context.adapter.media(action)
    return {"play_pause": "Oke", "next": "Lagu berikutnya", "prev": "Lagu sebelumnya"}[action]
