"""Ikon system tray (pystray): status, bisukan mic, buka config, keluar.

pystray di macOS wajib jalan di thread utama; loop Jarvis berjalan di thread lain.
"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image, ImageDraw

COLORS = {
    "loading": (150, 150, 150),
    "idle": (70, 130, 220),
    "listening": (60, 190, 90),
    "thinking": (240, 180, 40),
    "speaking": (150, 90, 220),
    "confirming": (240, 120, 40),
    "muted": (210, 60, 60),
}
LABELS = {
    "loading": "Memuat model…",
    "idle": "Siap",
    "listening": "Mendengarkan",
    "thinking": "Berpikir",
    "speaking": "Berbicara",
    "confirming": "Menunggu konfirmasi",
    "muted": "Mikrofon dibisukan",
}


def make_icon(state: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 58, 58), fill=COLORS.get(state, COLORS["idle"]) + (255,))
    d.ellipse((24, 24, 40, 40), fill=(255, 255, 255, 230))
    return img


class Tray:
    def __init__(
        self,
        name: str,
        on_quit: Callable[[], None],
        on_toggle_mute: Callable[[bool], None],
        on_open_config: Callable[[], None],
    ) -> None:
        import pystray

        self._pystray = pystray
        self._on_quit, self._on_mute, self._on_cfg = on_quit, on_toggle_mute, on_open_config
        self.muted = False
        self.state = "loading"
        self.icon = pystray.Icon(name.lower(), make_icon("loading"), name, self._menu())

    def _menu(self):
        P = self._pystray
        return P.Menu(
            P.MenuItem(lambda _i: LABELS[self._shown()], None, enabled=False),
            P.MenuItem("Bisukan mikrofon", self._toggle_mute, checked=lambda _i: self.muted),
            P.MenuItem("Buka config", lambda _i, _it: self._on_cfg()),
            P.MenuItem("Keluar", self._quit),
        )

    def _shown(self) -> str:
        return "muted" if self.muted else self.state

    def _refresh(self) -> None:
        self.icon.icon = make_icon(self._shown())
        self.icon.title = f"{self.icon.name.title()} — {LABELS[self._shown()]}"
        self.icon.update_menu()

    def _toggle_mute(self, _icon, _item) -> None:
        self.muted = not self.muted
        self._on_mute(self.muted)
        self._refresh()

    def _quit(self, _icon, _item) -> None:
        self._on_quit()
        self.icon.stop()

    def set_state(self, state: str) -> None:
        self.state = state
        self._refresh()

    def run(self) -> None:
        """Blocking; panggil dari thread utama."""
        self.icon.run()

    def stop(self) -> None:
        self.icon.stop()
