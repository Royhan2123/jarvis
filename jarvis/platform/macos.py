from __future__ import annotations

import shutil
import subprocess

from jarvis.platform._util import grab_screen_png, is_blank, run, type_via_pynput
from jarvis.platform.base import AppNotFound, MediaAction, PlatformAdapter, PlatformError

_PLAYERS = ("Spotify", "Music")
_APP_DIRS = ("/Applications", "/System/Applications", "/Applications/Utilities",
             "/System/Applications/Utilities")  # fmt: skip


def installed_apps() -> list[str]:
    """Nama aplikasi terpasang (tanpa .app) dari folder Aplikasi standar dan ~/Applications."""
    import os

    names: list[str] = []
    for d in (*_APP_DIRS, os.path.expanduser("~/Applications")):
        try:
            names += [f[:-4] for f in os.listdir(d) if f.endswith(".app")]
        except OSError:
            continue
    return names


def closest_app(name: str, apps: list[str]) -> str | None:
    """Nama aplikasi terpasang yang paling mirip dengan yang terdengar (rasio ≥ 0.75)."""
    import difflib

    lowered = {a.lower(): a for a in apps}
    near = difflib.get_close_matches(name.lower().strip(), list(lowered), n=1, cutoff=0.75)
    return lowered[near[0]] if near else None


_MEDIA_CMD = {"play_pause": "playpause", "next": "next track", "prev": "previous track"}


class MacAdapter(PlatformAdapter):
    name = "macos"

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    def say(self, text: str, voice: str | None = None) -> None:
        if not shutil.which("say"):
            raise NotImplementedError("Perintah 'say' tidak ditemukan di macOS ini")
        cmd = ["say", "-r", "185", *(["-v", voice] if voice else []), "--", text]
        self._proc = subprocess.Popen(cmd)
        self._proc.wait()

    def stop_say(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _osascript(self, script: str, *args: str) -> str:
        # Nama aplikasi dikirim sebagai argumen (argv), bukan disisipkan ke teks script.
        return run(["osascript", "-e", script, *args])

    def _is_running(self, app: str) -> bool:
        out = self._osascript(
            'on run argv\ntell application "System Events" to '
            "return (name of processes) contains (item 1 of argv)\nend run",
            app,
        )
        return out == "true"

    def open_app(self, name: str) -> None:
        try:
            run(["open", "-a", name])
            return
        except PlatformError as e:
            guess = closest_app(name, installed_apps())  # "Savari" → "Safari"
            if guess is None:
                raise AppNotFound(f"Aplikasi {name} tidak ditemukan") from e
        try:
            run(["open", "-a", guess])
        except PlatformError as e:
            raise AppNotFound(f"Aplikasi {name} tidak ditemukan") from e

    def close_app(self, name: str) -> None:
        if not self._is_running(name):
            raise AppNotFound(f"{name} tidak sedang berjalan")
        self._osascript("on run argv\ntell application (item 1 of argv) to quit\nend run", name)

    def set_volume(self, percent: int) -> None:
        self._osascript(f"set volume output volume {int(percent)}")

    def mute(self, on: bool) -> None:
        self._osascript(f"set volume output muted {'true' if on else 'false'}")

    def media(self, action: MediaAction) -> None:
        for app in _PLAYERS:
            if self._is_running(app):
                verb = _MEDIA_CMD[action]
                self._osascript(
                    f"on run argv\ntell application (item 1 of argv) to {verb}\nend run", app
                )
                return
        raise PlatformError(
            "Tidak ada pemutar musik (Spotify atau Music) yang sedang jalan. "
            "Coba bilang: putar judul lagu di YouTube"
        )

    def lock_screen(self) -> None:
        run(["pmset", "displaysleepnow"])

    def shutdown(self) -> None:
        self._osascript('tell application "System Events" to shut down')

    def restart(self) -> None:
        self._osascript('tell application "System Events" to restart')

    def open_path(self, path: str) -> None:
        run(["open", path])

    @staticmethod
    def _screen_permission() -> bool:
        """Tanpa izin Screen Recording macOS hanya memberi wallpaper (tanpa error) → cek dulu."""
        try:
            import Quartz
        except ImportError:  # pyobjc tidak ada: biarkan pengecekan gambar kosong yang bekerja
            return True
        if Quartz.CGPreflightScreenCaptureAccess():
            return True
        Quartz.CGRequestScreenCaptureAccess()  # memunculkan dialog izin sistem
        return False

    def screenshot(self) -> bytes:
        if not self._screen_permission():
            raise PlatformError(
                "Izin Screen Recording belum diberikan. Aktifkan untuk aplikasi ini di System "
                "Settings, Privacy dan Security, lalu buka ulang aplikasinya"
            )
        png = grab_screen_png()
        if is_blank(png):
            raise PlatformError(
                "Layar tidak bisa dibaca. Izinkan Screen Recording untuk aplikasi ini di "
                "System Settings, Privacy dan Security"
            )
        return png

    def type_text(self, text: str) -> None:
        try:
            type_via_pynput(text, "cmd")
        except Exception as e:  # noqa: BLE001 — izin Accessibility belum diberikan, dll
            raise PlatformError(
                "Tidak bisa mengetik. Izinkan Accessibility untuk aplikasi ini di System Settings"
            ) from e

    def notify(self, title: str, body: str) -> None:
        self._osascript(
            "on run argv\ndisplay notification (item 1 of argv) "
            "with title (item 2 of argv)\nend run",
            body,
            title,
        )
