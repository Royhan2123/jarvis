"""Tool aplikasi: buka & tutup."""

from __future__ import annotations

import re

from jarvis.tools.registry import ToolError, context, tool

# Huruf/angka, spasi, titik, minus, plus, underscore, kurung, apostrof. Tanpa tanda kutip,
# backslash, titik koma, &, |, $, dll → aman dari injeksi.
_SAFE_NAME = re.compile(r"^[\w .+()'-]{1,60}$")


def resolve_app(name: str) -> str:
    """Normalisasi nama app: validasi karakter, alias dari config, daftar allowed."""
    name = " ".join(name.split())
    if not _SAFE_NAME.match(name):
        raise ToolError("Nama aplikasi mengandung karakter yang tidak diizinkan")
    apps = context.cfg.tools.apps
    name = {k.lower(): v for k, v in apps.aliases.items()}.get(name.lower(), name)
    if apps.allowed and name.lower() not in {a.lower() for a in apps.allowed}:
        raise ToolError(f"Aplikasi {name} tidak ada dalam daftar yang diizinkan")
    return name


@tool(
    name="open_app",
    description="Membuka aplikasi di komputer, misalnya Spotify, Chrome, atau VS Code",
    risk="low",
    category="apps",
)
def open_app(name: str) -> str:
    app = resolve_app(name)
    context.adapter.open_app(app)
    return f"Siap, {app} sudah dibuka"


@tool(
    name="close_app",
    description="Menutup aplikasi yang sedang berjalan",
    risk="medium",
    category="apps",
)
def close_app(name: str) -> str:
    app = resolve_app(name)
    context.adapter.close_app(app)
    return f"Oke, {app} sudah ditutup"
