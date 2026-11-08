from __future__ import annotations

import shutil
import subprocess

from jarvis.platform.base import PlatformAdapter


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
