"""Tool web: buka URL & cari di Google lewat browser pengguna.

Yang melakukan request jaringan adalah browser pengguna, bukan Jarvis.
"""

from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus, urlparse

from jarvis.tools.registry import ToolError, tool


def normalize_url(url: str) -> str:
    """Hanya http/https. Tanpa skema → ditambah https://. file:, javascript:, dll ditolak."""
    url = url.strip()
    if "://" not in url and not url.lower().startswith(("javascript:", "data:", "file:")):
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.netloc or " " in url:
        raise ToolError("Alamat web tidak valid, hanya http dan https yang diizinkan")
    return url


def _open(url: str) -> None:
    if not webbrowser.open(url):
        raise ToolError("Browser tidak bisa dibuka")


@tool(
    name="open_url",
    description="Membuka alamat website di browser, misalnya youtube.com",
    risk="low",
    category="web",
)
def open_url(url: str) -> str:
    _open(normalize_url(url))
    return "Siap, sudah saya buka di browser"


@tool(
    name="web_search",
    description="Mencari sesuatu di Google lewat browser",
    risk="low",
    category="web",
)
def web_search(query: str) -> str:
    query = " ".join(query.split())[:200]
    if not query:
        raise ToolError("Mau cari apa?")
    _open(f"https://www.google.com/search?q={quote_plus(query)}")
    return f"Oke, saya cari {query}"
