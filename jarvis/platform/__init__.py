"""Pilih adapter sesuai OS. Satu-satunya tempat yang boleh membaca sys.platform."""

from __future__ import annotations

import sys

from jarvis.platform.base import PlatformAdapter


def get_adapter() -> PlatformAdapter:
    if sys.platform == "darwin":
        from jarvis.platform.macos import MacAdapter

        return MacAdapter()
    if sys.platform == "win32":
        from jarvis.platform.windows import WindowsAdapter

        return WindowsAdapter()
    from jarvis.platform.linux import LinuxAdapter

    return LinuxAdapter()
