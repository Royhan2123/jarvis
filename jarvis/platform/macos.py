from __future__ import annotations

import shutil
import subprocess

from jarvis.platform._util import run
from jarvis.platform.base import AppNotFound, MediaAction, PlatformAdapter, PlatformError

_PLAYERS = ("Spotify", "Music")
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
        raise PlatformError("Tidak ada pemutar musik (Spotify atau Music) yang sedang jalan")

    def lock_screen(self) -> None:
        run(["pmset", "displaysleepnow"])

    def shutdown(self) -> None:
        self._osascript('tell application "System Events" to shut down')

    def restart(self) -> None:
        self._osascript('tell application "System Events" to restart')

    def open_path(self, path: str) -> None:
        run(["open", path])
