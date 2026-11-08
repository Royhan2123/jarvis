"""Pilih mesin TTS; Piper gagal → fallback ke suara OS."""

from __future__ import annotations

from typing import Protocol

from loguru import logger

from jarvis.config import Config


class TTS(Protocol):
    def speak(self, text: str) -> None: ...
    def stop(self) -> None: ...


def build_tts(cfg: Config) -> TTS:
    from jarvis.tts.fallback import SystemTTS

    if cfg.tts.engine == "edge":
        logger.warning("Engine 'edge' belum tersedia (Fase 1); memakai suara OS")
    elif cfg.tts.engine == "piper":
        try:
            from jarvis.tts.piper import PiperTTS

            return PiperTTS(cfg)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Piper tidak bisa dipakai ({e}); memakai suara OS")
    return SystemTTS(cfg)
