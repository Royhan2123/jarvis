"""Pilih mesin TTS; Piper gagal → fallback ke suara OS."""

from __future__ import annotations

from typing import Protocol

from loguru import logger

from jarvis.config import Config


class TTS(Protocol):
    def speak(self, text: str) -> None: ...
    def stop(self) -> None: ...


class BilingualTTS:
    """Pilih suara per kalimat: Inggris bila kalimatnya Inggris dan suara Inggris tersedia."""

    def __init__(self, id_tts: TTS, en_tts: TTS | None) -> None:
        self.id_tts, self.en_tts = id_tts, en_tts

    def _pick(self, text: str) -> TTS:
        from jarvis.brain.language import guess

        return self.en_tts if self.en_tts is not None and guess(text) == "en" else self.id_tts

    def speak(self, text: str) -> None:
        self._pick(text).speak(text)

    def stop(self) -> None:
        self.id_tts.stop()
        if self.en_tts is not None:
            self.en_tts.stop()


def _local_for(cfg: Config, lang: str) -> TTS | None:
    """Piper bila ada, kalau tidak suara OS; untuk Inggris None bila tidak ada suaranya."""
    from jarvis.tts.fallback import SystemTTS

    try:
        from jarvis.tts.piper import PiperTTS

        return PiperTTS(cfg, lang=lang)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Piper ({lang}) tidak bisa dipakai ({e}); memakai suara OS")
    try:
        return SystemTTS(cfg, lang=lang)
    except Exception as e:  # noqa: BLE001 — OS tanpa suara Inggris yang terdaftar
        logger.warning(f"Suara OS ({lang}) tidak tersedia ({e})")
        return None


def _local_tts(cfg: Config) -> TTS:
    """Suara lokal dua bahasa: Indonesia (wajib) + Inggris (bila ada)."""
    from jarvis.tts.fallback import SystemTTS

    id_tts = _local_for(cfg, "id") or SystemTTS(cfg)
    return BilingualTTS(id_tts, _local_for(cfg, "en"))


def build_tts(cfg: Config) -> TTS:
    from jarvis.tts.fallback import SystemTTS

    if cfg.tts.engine == "fish":
        base = _local_tts(cfg)
        try:
            from jarvis.tts.fish import FishTTS

            return FishTTS(cfg, fallback=base)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Fish Audio tidak bisa dipakai ({e}); memakai suara lokal")
        return base
    if cfg.tts.engine == "edge":
        logger.warning("Engine 'edge' belum tersedia (Fase 1); memakai suara OS")
        return SystemTTS(cfg)
    if cfg.tts.engine == "piper":
        return _local_tts(cfg)
    return SystemTTS(cfg)
