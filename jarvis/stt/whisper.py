"""Speech-to-text dengan faster-whisper (CTranslate2, int8 di CPU)."""

from __future__ import annotations

import re

import numpy as np

from jarvis.config import STTConfig


def is_repetitive(text: str) -> bool:
    """Halusinasi Whisper pada noise: kalimat/angka yang diulang puluhan kali → buang."""
    words = re.findall(r"\w+", text.lower())
    if len(words) < 12:
        return False
    return len(set(words)) / len(words) < 0.35


class WhisperSTT:
    def __init__(self, cfg: STTConfig) -> None:
        from faster_whisper import WhisperModel

        self.cfg = cfg
        self.last_logprob = 0.0
        self.model = WhisperModel(
            cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            cpu_threads=cfg.cpu_threads,
        )

    def transcribe(self, audio: np.ndarray, fast: bool = False) -> str:
        """audio: int16 mono 16 kHz. fast=True: tanpa fallback suhu (untuk wake)."""
        samples = audio.astype(np.float32) / 32768.0
        prompt = (self.cfg.wake_prompt if fast else self.cfg.initial_prompt) or None
        segments, _ = self.model.transcribe(
            samples,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            initial_prompt=prompt,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
            **({"temperature": 0.0, "without_timestamps": True} if fast else {}),
        )
        segs = list(segments)
        text = " ".join(s.text.strip() for s in segs).strip()
        # rata-rata keyakinan per segmen (≈ -0.35 untuk ucapan jelas, ≈ -1.0 untuk salah dengar)
        self.last_logprob = sum(s.avg_logprob for s in segs) / len(segs) if segs else 0.0
        if self._is_prompt_echo(text, prompt or "") or is_repetitive(text):
            return ""
        return text

    def _is_prompt_echo(self, text: str, prompt_text: str | None = None) -> bool:
        """Whisper kadang mengulang initial_prompt saat hening/noise → buang."""
        words = set(re.findall(r"\w+", text.lower()))
        prompt = set(re.findall(r"\w+", (prompt_text or self.cfg.initial_prompt or "").lower()))
        return bool(words) and len(words) >= 4 and len(words - prompt) <= 1

    def is_unclear(self) -> bool:
        """True jika transkripsi terakhir terlalu tidak yakin (kemungkinan salah dengar)."""
        floor = self.cfg.min_logprob
        return floor is not None and self.last_logprob < floor
