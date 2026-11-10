"""Sambungan ke Isla Desk (pulau notifikasi Tauri): kirim teks ke pulau lewat IPC loopback.

Protokol Isla: file `ipc.json` ({port, token}) di folder data aplikasinya; satu baris JSON
`{"token", "notify": "<teks>"}` lewat TCP 127.0.0.1, dibalas satu baris JSON.
Hanya loopback, jadi aman walau `offline_only: true`. Gagal (Isla tak jalan) = diam-diam False.
"""

from __future__ import annotations

import json
import re
import socket
import threading
from pathlib import Path

from loguru import logger
from platformdirs import user_data_dir

from jarvis.config import Config

APP_ID = "com.royhan.isladesk"  # identifier Tauri; menentukan folder data Isla di tiap OS
MAX_CHARS = 200  # batas Isla (MAX_QUERY_CHARS)


def ipc_file(cfg: Config) -> Path:
    if cfg.island.ipc_file:
        return Path(cfg.island.ipc_file).expanduser()
    # Tauri: Windows %APPDATA%\<id>, macOS ~/Library/Application Support/<id>, Linux ~/.local/share
    return Path(user_data_dir(APP_ID, appauthor=False, roaming=True)) / "ipc.json"


def clean(text: str) -> str:
    """Satu baris, tanpa karakter kontrol, maksimal MAX_CHARS (Isla menolak yang lain)."""
    text = re.sub(r"\s+", " ", text)
    text = "".join(c for c in text if c.isprintable()).strip()
    return text[:MAX_CHARS]


def notify(cfg: Config, text: str) -> bool:
    """Kirim `text` ke pulau Isla. True bila diterima; False bila nonaktif / Isla tak jalan."""
    if not cfg.island.enabled:
        return False
    msg = clean(text)
    if not msg:
        return False
    try:
        ep = json.loads(ipc_file(cfg).read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", int(ep["port"])), timeout=2) as s:
            s.settimeout(3)
            s.sendall(json.dumps({"token": ep["token"], "notify": msg}).encode() + b"\n")
            reply = s.makefile().readline()
        return bool(reply.strip())
    except (OSError, ValueError, KeyError) as e:
        logger.debug(f"Isla tidak terjangkau: {e}")
        return False


def notify_async(cfg: Config, text: str) -> None:
    """Kirim di thread terpisah supaya pipeline suara tidak menunggu."""
    if cfg.island.enabled:
        threading.Thread(target=notify, args=(cfg, text), daemon=True).start()
