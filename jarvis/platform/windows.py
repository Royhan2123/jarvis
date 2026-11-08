from __future__ import annotations

from jarvis.platform.base import PlatformAdapter


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
