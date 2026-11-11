"""TTS fallback: suara bawaan OS lewat PlatformAdapter (say / SAPI / espeak-ng)."""

from __future__ import annotations

from jarvis.config import Config
from jarvis.platform import get_adapter
from jarvis.platform.base import PlatformAdapter


class SystemTTS:
    def __init__(
        self, cfg: Config, adapter: PlatformAdapter | None = None, lang: str = "id"
    ) -> None:
        self.adapter = adapter or get_adapter()
        voices = cfg.tts.voices.system_en if lang == "en" else cfg.tts.voices.system
        pair = getattr(voices, self.adapter.name)
        self.voice = getattr(pair, cfg.tts.gender)

    def speak(self, text: str) -> None:
        self.adapter.say(text, self.voice)

    def stop(self) -> None:
        self.adapter.stop_say()
