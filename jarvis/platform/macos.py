from __future__ import annotations

import shutil
import subprocess

from jarvis.platform.base import PlatformAdapter

_VOICES = {"female": "Damayanti", "male": None}


class MacAdapter(PlatformAdapter):
    def say(self, text: str, gender: str) -> None:
        if not shutil.which("say"):
            raise NotImplementedError("Perintah 'say' tidak ditemukan di macOS ini")
        voice = _VOICES.get(gender)
        cmd = ["say", "-r", "185", *(["-v", voice] if voice else []), text]
        subprocess.run(cmd, check=False)
