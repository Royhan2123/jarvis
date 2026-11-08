"""Adapter Linux (X11 & Wayland). CATATAN: belum diuji di mesin Linux (dev di macOS)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from jarvis.platform._util import run, terminate_user_processes
from jarvis.platform.base import AppNotFound, MediaAction, PlatformAdapter, PlatformError

_APP_DIRS = (
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local" / "share" / "applications",
)


def find_desktop_entry(name: str) -> str | None:
    """Cari id .desktop yang namanya cocok (Name= atau nama file). Return id tanpa .desktop."""
    want = name.lower()
    partial: str | None = None
    for d in _APP_DIRS:
        if not d.is_dir():
            continue
        for f in d.glob("*.desktop"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "NoDisplay=true" in text:
                continue
            label = next(
                (
                    ln.split("=", 1)[1].strip().lower()
                    for ln in text.splitlines()
                    if ln.startswith("Name=")
                ),
                "",
            )
            if want in {label, f.stem.lower()}:
                return f.stem
            if want in label and partial is None:
                partial = f.stem
    return partial


class LinuxAdapter(PlatformAdapter):
    name = "linux"

    def __init__(self, volume_backend: str = "auto") -> None:
        self._proc: subprocess.Popen | None = None
        self.volume_backend = volume_backend

    def say(self, text: str, voice: str | None = None) -> None:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            raise NotImplementedError("espeak-ng belum terpasang (lihat docs/SETUP.md)")
        cmd = [exe, *(["-v", voice] if voice else ["-v", "id"]), "--", text]
        self._proc = subprocess.Popen(cmd)
        self._proc.wait()

    def stop_say(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def open_app(self, name: str) -> None:
        # Hanya aplikasi yang punya .desktop: tidak menjalankan sembarang binary dari PATH.
        entry = find_desktop_entry(name)
        if entry is None:
            raise AppNotFound(f"Aplikasi {name} tidak ditemukan")
        run(["gtk-launch", entry])

    def close_app(self, name: str) -> None:
        if shutil.which("wmctrl") and os.environ.get("DISPLAY"):
            try:
                run(["wmctrl", "-c", name])
                return
            except PlatformError:
                pass
        terminate_user_processes(name)

    def _backend(self) -> str:
        if self.volume_backend != "auto":
            return self.volume_backend
        for b in ("wpctl", "pactl", "amixer"):
            if shutil.which(b):
                return b
        raise PlatformError("Tidak ada wpctl, pactl, atau amixer untuk mengatur volume")

    def set_volume(self, percent: int) -> None:
        b = self._backend()
        if b == "wpctl":
            run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%"])
        elif b == "pactl":
            run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"])
        else:
            run(["amixer", "-q", "set", "Master", f"{percent}%"])

    def mute(self, on: bool) -> None:
        b = self._backend()
        if b == "wpctl":
            run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if on else "0"])
        elif b == "pactl":
            run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if on else "0"])
        else:
            run(["amixer", "-q", "set", "Master", "mute" if on else "unmute"])

    def media(self, action: MediaAction) -> None:
        cmd = {"play_pause": "play-pause", "next": "next", "prev": "previous"}[action]
        run(["playerctl", cmd])

    def lock_screen(self) -> None:
        try:
            run(["loginctl", "lock-session"])
        except PlatformError:
            run(["xdg-screensaver", "lock"])

    def shutdown(self) -> None:
        run(["systemctl", "poweroff"])

    def restart(self) -> None:
        run(["systemctl", "reboot"])

    def open_path(self, path: str) -> None:
        run(["xdg-open", path])
