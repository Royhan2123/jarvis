from __future__ import annotations

from jarvis.platform.base import PlatformAdapter


class WindowsAdapter(PlatformAdapter):
    def say(self, text: str, gender: str) -> None:
        raise NotImplementedError("Suara Windows (SAPI/pyttsx3) menyusul di Fase 1")
