"""Tool web: buka URL & cari di Google lewat browser pengguna.

Yang melakukan request jaringan adalah browser pengguna, bukan Jarvis.
"""

from __future__ import annotations

import re
import urllib.request
import webbrowser
from urllib.parse import quote_plus, urlparse

from jarvis.tools.registry import ToolError, context, tool


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


_VIDEO_ID = re.compile(r'"videoId":"([\w-]{11})"')
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def first_video_id(query: str, timeout: float = 8.0) -> str | None:
    """ID video hasil pertama pencarian YouTube (membaca halaman hasil; tanpa API key)."""
    req = urllib.request.Request(  # noqa: S310 — URL tetap https://www.youtube.com
        f"https://www.youtube.com/results?search_query={quote_plus(query)}",
        headers={"User-Agent": _UA, "Accept-Language": "id,en;q=0.8"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        html = resp.read(2_000_000).decode("utf-8", "ignore")
    m = _VIDEO_ID.search(html)
    return m.group(1) if m else None


@tool(
    name="play_youtube",
    description="Memutar video/lagu di YouTube di browser berdasarkan judul atau kata kunci",
    risk="low",
    category="web",
)
def play_youtube(query: str) -> str:
    query = " ".join(query.split())[:150]
    if not query:
        raise ToolError("Mau putar apa di YouTube?")
    if context.cfg.general.offline_only:
        raise ToolError(
            "Mode offline aktif. Set general.offline_only: false di config.yaml untuk fitur ini"
        )
    try:
        video = first_video_id(query)
    except Exception:  # noqa: BLE001 — jaringan mati / YouTube berubah: cadangan halaman hasil
        video = None
    if video:
        _open(f"https://www.youtube.com/watch?v={video}")
        return f"Oke, memutar {query} di YouTube"
    _open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
    return f"Saya buka hasil pencarian {query} di YouTube, pilih salah satu"
