"""Tool sistem: jam/tanggal, info baterai/CPU/RAM, kunci layar."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from jarvis.tools.registry import context, tool

_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]  # fmt: skip


def format_time_id(dt: datetime) -> str:
    return f"Sekarang jam {dt.hour:02d}.{dt.minute:02d}"


def format_date_id(dt: datetime) -> str:
    return f"Hari ini {_HARI[dt.weekday()]}, {dt.day} {_BULAN[dt.month - 1]} {dt.year}"


@tool(
    name="get_time",
    description="Memberi tahu jam sekarang (what=time) atau tanggal hari ini (what=date)",
    risk="low",
    category="system",
)
def get_time(what: Literal["time", "date"] = "time") -> str:
    now = datetime.now()
    return format_time_id(now) if what == "time" else format_date_id(now)


@tool(
    name="system_info",
    description="Info komputer: battery (baterai), cpu, ram, atau all (semuanya)",
    risk="low",
    category="system",
)
def system_info(kind: Literal["battery", "cpu", "ram", "all"] = "all") -> str:
    import psutil

    parts: list[str] = []
    if kind in ("battery", "all"):
        bat = psutil.sensors_battery()
        if bat is None:
            parts.append("Komputer ini tidak punya baterai")
        else:
            state = "sedang diisi" if bat.power_plugged else "tidak diisi"
            parts.append(f"Baterai {round(bat.percent)} persen, {state}")
    if kind in ("cpu", "all"):
        parts.append(f"CPU terpakai {round(psutil.cpu_percent(interval=0.3))} persen")
    if kind in ("ram", "all"):
        parts.append(f"RAM terpakai {round(psutil.virtual_memory().percent)} persen")
    return ". ".join(parts)


@tool(
    name="lock_screen",
    description="Mengunci layar komputer",
    risk="medium",
    category="system",
)
def lock_screen() -> str:
    context.adapter.lock_screen()
    return "Layar dikunci"


@tool(
    name="shutdown",
    description="Mematikan komputer. Selalu butuh konfirmasi pengguna",
    risk="high",
    category="system",
)
def shutdown() -> str:
    context.adapter.shutdown()
    return "Komputer akan dimatikan"


@tool(
    name="restart",
    description="Merestart komputer. Selalu butuh konfirmasi pengguna",
    risk="high",
    category="system",
)
def restart() -> str:
    context.adapter.restart()
    return "Komputer akan direstart"
