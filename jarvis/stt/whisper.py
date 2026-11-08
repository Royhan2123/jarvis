"""Speech-to-text dengan faster-whisper (CTranslate2, int8 di CPU)."""

from __future__ import annotations

import numpy as np

from jarvis.config import STTConfig


class WhisperSTT:
    def __init__(self, cfg: STTConfig) -> None:
        from faster_whisper import WhisperModel

        self.cfg = cfg
        self.model = WhisperModel(
            cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            cpu_threads=cfg.cpu_threads,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        """audio: int16 mono 16 kHz."""
        samples = audio.astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            samples,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            initial_prompt=self.cfg.initial_prompt or None,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
