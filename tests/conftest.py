from __future__ import annotations

import pytest

from jarvis.config import Config
from jarvis.platform.base import AppNotFound, PlatformAdapter
from jarvis.tools.registry import context, load_tools


class MockAdapter(PlatformAdapter):
    """Adapter palsu: mencatat panggilan, tidak menyentuh sistem sungguhan."""

    name = "macos"

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.running = {"Spotify"}

    def _rec(self, *a) -> None:
        self.calls.append(a)

    def say(self, text, voice=None) -> None:
        self._rec("say", text)

    def stop_say(self) -> None:
        self._rec("stop_say")

    def open_app(self, name) -> None:
        if name == "Tidak Ada":
            raise AppNotFound("Aplikasi Tidak Ada tidak ditemukan")
        self._rec("open_app", name)

    def close_app(self, name) -> None:
        self._rec("close_app", name)

    def set_volume(self, percent) -> None:
        self._rec("set_volume", percent)

    def mute(self, on) -> None:
        self._rec("mute", on)

    def media(self, action) -> None:
        self._rec("media", action)

    def lock_screen(self) -> None:
        self._rec("lock_screen")

    def shutdown(self) -> None:
        self._rec("shutdown")

    def restart(self) -> None:
        self._rec("restart")

    def open_path(self, path) -> None:
        self._rec("open_path", path)


@pytest.fixture
def adapter() -> MockAdapter:
    a = MockAdapter()
    context.configure(a, Config())
    load_tools(Config())
    return a
