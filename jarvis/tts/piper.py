"""Piper TTS (offline, ONNX). Suara .onnx disimpan di folder data pengguna."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd
from platformdirs import user_data_dir

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

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        parts = [c.audio_int16_array for c in self.voice.synthesize(text, self.syn)]
        audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)
        return audio, self.voice.config.sample_rate

    def speak(self, text: str) -> None:
        audio, rate = self.synthesize(text)
        if audio.size:
            sd.play(audio, rate, device=self.device)
            sd.wait()

    def stop(self) -> None:
        sd.stop()
