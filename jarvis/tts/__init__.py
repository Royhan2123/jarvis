"""Pilih mesin TTS; Piper gagal → fallback ke suara OS."""

from __future__ import annotations

from collections.abc import Callable
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


def _build_local(cfg: Config, lang: str) -> TTS | None:
    """Piper bila ada, kalau tidak suara OS; None bila tidak ada suara untuk bahasa itu."""
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


class LazyTTS:
    """Suara lokal yang baru dimuat saat dipakai pertama kali (Piper ±70 MB RAM per suara; dengan
    Fish aktif, suara cadangan ini jarang terpakai). `fallback` dipakai bila suaranya tak ada."""

    def __init__(self, build: Callable[[], TTS | None], fallback: TTS | None = None) -> None:
        self._build, self._fallback = build, fallback
        self._impl: TTS | None = None
        self._tried = False

    def _get(self) -> TTS | None:
        if not self._tried:
            self._tried, self._impl = True, self._build()
        return self._impl or self._fallback

    def speak(self, text: str) -> None:
        if (tts := self._get()) is not None:
            tts.speak(text)

    def stop(self) -> None:
        if self._impl is not None:
            self._impl.stop()


def _local_tts(cfg: Config) -> TTS:
    """Suara lokal dua bahasa: Indonesia + Inggris, keduanya dimuat malas."""
    from jarvis.tts.fallback import SystemTTS

    id_tts = LazyTTS(lambda: _build_local(cfg, "id") or SystemTTS(cfg))
    en_tts = LazyTTS(lambda: _build_local(cfg, "en"), fallback=id_tts)
    return BilingualTTS(id_tts, en_tts)


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
        local = _local_tts(cfg)
        local.id_tts._get()  # Piper adalah suara utama: muat sekarang supaya ucapan pertama cepat
        return local
    return SystemTTS(cfg)
