from __future__ import annotations

from jarvis.platform.base import PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    def say(self, text: str, gender: str) -> None:
        raise NotImplementedError("Suara Linux (espeak-ng) menyusul di Fase 1")
