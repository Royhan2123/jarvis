from __future__ import annotations

import pytest

from jarvis.brain.memory import Memory
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
        # Aplikasi sungguhan hanya yang terpasang: nama berawalan "Tidak"/memuat "kalo" tidak ada.
        if name.split()[0] == "Tidak" or "kalo" in name.lower():
            raise AppNotFound(f"Aplikasi {name} tidak ditemukan")
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

    def screenshot(self) -> bytes:
        self._rec("screenshot")
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (64, 36), (120, 200, 90)).save(buf, "PNG")
        return buf.getvalue()

    def type_text(self, text) -> None:
        self._rec("type_text", text)

    def notify(self, title, body) -> None:
        self._rec("notify", title, body)


@pytest.fixture
def adapter(tmp_path) -> MockAdapter:
    a = MockAdapter()
    context.configure(a, Config(), Memory(path=tmp_path / "test.db"))
    load_tools(Config())
    return a
