"""Tool aplikasi: buka & tutup."""

from __future__ import annotations

import re

from jarvis.platform.base import AppNotFound
from jarvis.tools.registry import ToolError, context, tool

# Huruf/angka, spasi, titik, minus, plus, underscore, kurung, apostrof. Tanpa tanda kutip,
# backslash, titik koma, &, |, $, dll → aman dari injeksi.
_SAFE_NAME = re.compile(r"^[\w .+()'-]{1,60}$")


def resolve_app(name: str) -> str:
    """Normalisasi nama app: validasi karakter, alias dari config, daftar allowed."""
    name = " ".join(name.split())
    if not _SAFE_NAME.match(name):
        raise ToolError("Nama aplikasi mengandung karakter yang tidak diizinkan")
    if name.lower() in {"jarvis", context.cfg.general.name.lower()}:
        raise ToolError("Saya tidak bisa menutup atau membuka diri sendiri")
    apps = context.cfg.tools.apps
    name = {k.lower(): v for k, v in apps.aliases.items()}.get(name.lower(), name)
    if apps.allowed and name.lower() not in {a.lower() for a in apps.allowed}:
        raise ToolError(f"Aplikasi {name} tidak ada dalam daftar yang diizinkan")
    return name


def _with_shorter_names(name: str, action) -> str:  # noqa: ANN001
    """Jalankan `action(app)`; bila aplikasi tidak ada dan namanya beberapa kata, coba tanpa kata
    terakhir ("kalkulator kalo" → "kalkulator"): ekor ucapan sering ikut terdengar."""
    words = name.split()
    error: AppNotFound | None = None
    for n in range(len(words), 0, -1):
        app = resolve_app(" ".join(words[:n]))
        try:
            action(app)
            return app
        except AppNotFound as e:
            error = error or e
    raise error or AppNotFound(f"Aplikasi {name} tidak ditemukan")


@tool(
    name="open_app",
    description="Membuka aplikasi di komputer, misalnya Spotify, Chrome, atau VS Code",
    risk="low",
    category="apps",
)
def open_app(name: str) -> str:
    app = _with_shorter_names(name, context.adapter.open_app)
    return f"Siap, {app} sudah dibuka"


@tool(
    name="close_app",
    description="Menutup aplikasi yang sedang berjalan",
    risk="medium",
    category="apps",
)
def close_app(name: str) -> str:
    app = _with_shorter_names(name, context.adapter.close_app)
    return f"Oke, {app} sudah ditutup"
