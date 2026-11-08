from __future__ import annotations

import shutil
import subprocess

from jarvis.platform.base import PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    name = "linux"

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

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
