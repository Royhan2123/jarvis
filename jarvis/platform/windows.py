"""Adapter Windows. CATATAN: belum diuji di mesin Windows (dev di macOS)."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.platform._util import grab_screen_png, run, terminate_user_processes, type_via_pynput
from jarvis.platform.base import AppNotFound, MediaAction, PlatformAdapter, PlatformError


def _start_menu_dirs() -> list[Path]:
    dirs = []
    for env in ("ProgramData", "AppData"):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return dirs


def find_shortcut(name: str) -> Path | None:
    """Cari shortcut .lnk di Start Menu: nama persis dulu, lalu yang mengandung nama."""
    want = name.lower()
    best: Path | None = None
    for d in _start_menu_dirs():
        for lnk in d.rglob("*.lnk"):
            stem = lnk.stem.lower()
            if stem == want:
                return lnk
            if want in stem and best is None:
                best = lnk
    return best


class WindowsAdapter(PlatformAdapter):
    name = "windows"

    def __init__(self) -> None:
        self._engine = None

    def say(self, text: str, voice: str | None = None) -> None:
        import pyttsx3  # dependensi khusus Windows, di-import di sini saja

        self._engine = pyttsx3.init()
        if voice:
            for v in self._engine.getProperty("voices"):
                if voice.lower() in v.name.lower():
                    self._engine.setProperty("voice", v.id)
                    break
        self._engine.say(text)
        self._engine.runAndWait()

    def stop_say(self) -> None:
        if self._engine is not None:
            self._engine.stop()

    def open_app(self, name: str) -> None:
        # Hanya shortcut Start Menu: tidak menjalankan sembarang executable dari PATH.
        lnk = find_shortcut(name)
        if lnk is None:
            raise AppNotFound(f"Aplikasi {name} tidak ditemukan di Start Menu")
        os.startfile(lnk)  # type: ignore[attr-defined]  # noqa: S606

    def close_app(self, name: str) -> None:
        terminate_user_processes(name)

    def _endpoint(self):
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(iface, POINTER(IAudioEndpointVolume))

    def set_volume(self, percent: int) -> None:
        self._endpoint().SetMasterVolumeLevelScalar(percent / 100, None)

    def mute(self, on: bool) -> None:
        self._endpoint().SetMute(1 if on else 0, None)

    def media(self, action: MediaAction) -> None:
        from pynput.keyboard import Controller, Key

        key = {
            "play_pause": Key.media_play_pause,
            "next": Key.media_next,
            "prev": Key.media_previous,
        }[action]
        Controller().tap(key)

    def lock_screen(self) -> None:
        import ctypes

        if not ctypes.windll.user32.LockWorkStation():  # type: ignore[attr-defined]
            raise PlatformError("Gagal mengunci layar")

    def shutdown(self) -> None:
        run(["shutdown", "/s", "/t", "0"])

    def restart(self) -> None:
        run(["shutdown", "/r", "/t", "0"])

    def open_path(self, path: str) -> None:
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606

    def screenshot(self) -> bytes:
        return grab_screen_png()

    def type_text(self, text: str) -> None:
        type_via_pynput(text, "ctrl")

    def trim_memory(self) -> None:
        import ctypes

        try:  # kecilkan working set; Windows memuat ulang halaman yang dibutuhkan
            kernel, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            psapi.EmptyWorkingSet(kernel.GetCurrentProcess())
        except (OSError, AttributeError):
            pass

    def notify(self, title: str, body: str) -> None:
        from win11toast import notify  # dependensi khusus Windows

        notify(title, body)
