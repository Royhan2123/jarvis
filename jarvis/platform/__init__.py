"""Pilih adapter sesuai OS. Satu-satunya tempat yang boleh membaca sys.platform."""

from __future__ import annotations

import sys

from jarvis.config import Config
from jarvis.platform.base import PlatformAdapter


def get_adapter(cfg: Config | None = None) -> PlatformAdapter:
    if sys.platform == "darwin":
        from jarvis.platform.macos import MacAdapter

        return MacAdapter()
    if sys.platform == "win32":
        from jarvis.platform.windows import WindowsAdapter

        return WindowsAdapter()
    from jarvis.platform.linux import LinuxAdapter

    if cfg is None:
        return LinuxAdapter()
    lc = cfg.platform.linux
    return LinuxAdapter(lc.volume_backend, lc.typing_backend, lc.screenshot_backend)
