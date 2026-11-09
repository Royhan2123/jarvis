"""Contoh plugin: lempar dadu. Salin ke folder plugins/ (lihat docs/COMMANDS.md, bagian Plugin)."""

from __future__ import annotations

import random

from jarvis.tools.registry import ToolError, tool

KEYWORDS = ["dadu", "lempar", "acak"]


@tool(name="roll_dice", description="Melempar dadu dan menyebutkan hasilnya", risk="low")
def roll_dice(sides: int = 6) -> str:
    if not 2 <= sides <= 100:
        raise ToolError("Sisi dadu harus antara 2 dan 100")
    return f"Hasilnya {random.randint(1, sides)}"
