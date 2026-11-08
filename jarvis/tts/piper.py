"""Piper TTS (offline, ONNX). Suara .onnx disimpan di folder data pengguna."""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from platformdirs import user_data_dir
from scipy.signal import resample_poly

from jarvis.config import Config


def voices_dir() -> Path:
    return Path(user_data_dir("jarvis")) / "voices"


def resolve_voice(name: str) -> Path:
    """'id_ID-news_tts-medium' → <voices>/id_ID-news_tts-medium.onnx; '*.onnx' = path."""
    p = Path(name)
    if p.suffix == ".onnx":
        return p if p.is_absolute() else voices_dir() / p
    return voices_dir() / f"{name}.onnx"


class PiperTTS:
    def __init__(self, cfg: Config) -> None:
        from piper import PiperVoice, SynthesisConfig

        name = getattr(cfg.tts.voices.piper, cfg.tts.gender)
        path = resolve_voice(name) if name else None
        if path is None or not path.exists():
            raise FileNotFoundError(f"Suara Piper belum ada: {path}. Jalankan setup download-voice")
        self.voice = PiperVoice.load(path)
        self.syn = SynthesisConfig(
            length_scale=cfg.tts.length_scale,
            noise_scale=cfg.tts.noise_scale,
            volume=cfg.tts.volume,
        )
        self.device = cfg.audio.output_device
        self._stop = threading.Event()

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        parts = [c.audio_int16_array for c in self.voice.synthesize(text, self.syn)]
        audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)
        return audio, self.voice.config.sample_rate

    def speak(self, text: str) -> None:
        """Putar dengan buffer besar (300 ms) pada sample rate native perangkat.

        Buffer bawaan (~11 ms) mudah kosong saat CPU dipakai Whisper/LLM → suara pecah.
        """
        audio, rate = self.synthesize(text)
        if not audio.size:
            return
        dev = sd.query_devices(self.device, "output")
        out_rate = int(dev["default_samplerate"])
        if out_rate != rate:
            g = np.gcd(out_rate, rate)
            audio = resample_poly(audio.astype(np.float32), out_rate // g, rate // g)
            audio = np.clip(audio, -32768, 32767).astype(np.int16)
        self._stop.clear()
        with sd.OutputStream(
            samplerate=out_rate, channels=1, dtype="int16", device=self.device, latency=0.3
        ) as stream:
            block = out_rate // 10
            for i in range(0, len(audio), block):
                if self._stop.is_set():
                    break
                stream.write(audio[i : i + block].reshape(-1, 1))

    def stop(self) -> None:
        self._stop.set()
