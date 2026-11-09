"""Fish Audio TTS (online, berbayar/gratis terbatas). Gagal → otomatis pakai suara cadangan (Piper).

Privasi: teks tiap kalimat yang diucapkan dikirim ke api.fish.audio. Hanya aktif jika
`tts.engine: fish` DAN `general.offline_only: false`. API key dibaca dari file/env, bukan config.
"""

from __future__ import annotations

import json
import os
import struct
import threading
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from loguru import logger

from jarvis.config import Config
from jarvis.tts import TTS
from jarvis.tts.piper import play_int16

API_URL = "https://api.fish.audio/v1/tts"


class FishError(RuntimeError):
    pass


def api_key(cfg: Config) -> str:
    if os.environ.get("FISH_API_KEY"):
        return os.environ["FISH_API_KEY"].strip()
    f = cfg.tts.fish.api_key_file
    if f and Path(f).expanduser().is_file():
        return Path(f).expanduser().read_text(encoding="utf-8").strip()
    return ""


def parse_wav(data: bytes) -> tuple[np.ndarray, int]:
    """WAV hasil streaming bisa punya panjang palsu di header → cari chunk 'data' manual."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise FishError("Respons bukan audio WAV")
    channels, rate = struct.unpack("<HI", data[22:24] + data[24:28])
    idx = data.find(b"data")
    if idx < 0:
        raise FishError("Audio WAV tidak lengkap")
    pcm = data[idx + 8 :]
    pcm = pcm[: len(pcm) // 2 * 2]
    audio = np.frombuffer(pcm, dtype="<i2")
    if channels > 1:
        audio = audio[::channels]
    return audio.astype(np.int16), int(rate)


class FishTTS:
    def __init__(self, cfg: Config, fallback: TTS | None = None) -> None:
        fish = cfg.tts.fish
        if cfg.general.offline_only:
            raise FishError("Fish Audio butuh internet: set general.offline_only: false")
        if not fish.voice_id:
            raise FishError("tts.fish.voice_id belum diisi (ambil dari fish.audio/app/discovery)")
        self.key = api_key(cfg)
        if not self.key:
            raise FishError(
                "API key Fish Audio belum ada (env FISH_API_KEY atau tts.fish.api_key_file)"
            )
        self.cfg, self.fish, self.fallback = cfg, fish, fallback
        self.device = cfg.audio.output_device
        self._stop = threading.Event()

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        body = {
            "text": text,
            "reference_id": self.fish.voice_id,
            "format": "wav",
            "sample_rate": self.fish.sample_rate,
            "latency": "balanced",
            "prosody": {"speed": self.fish.speed},
        }
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "model": self.fish.model,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.fish.timeout_s) as r:  # noqa: S310
                return parse_wav(r.read())
        except urllib.error.HTTPError as e:
            hint = {401: "API key salah", 402: "saldo/model tidak tersedia", 429: "terlalu sering"}
            raise FishError(f"Fish Audio {e.code}: {hint.get(e.code, 'ditolak')}") from e
        except OSError as e:
            raise FishError(f"tidak bisa terhubung ke Fish Audio ({e})") from e

    def speak(self, text: str) -> None:
        try:
            audio, rate = self.synthesize(text)
        except FishError as e:
            logger.warning(f"{e}; memakai suara cadangan")
            if self.fallback:
                self.fallback.speak(text)
            return
        if not audio.size:
            return
        self._stop.clear()
        play_int16(audio, rate, self.device, self._stop)

    def stop(self) -> None:
        self._stop.set()
        if self.fallback:
            self.fallback.stop()
