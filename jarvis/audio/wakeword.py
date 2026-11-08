"""Deteksi wake word 'hey_jarvis' dengan openWakeWord (ONNX)."""

from __future__ import annotations

import time

import numpy as np

from jarvis.config import WakewordConfig


class WakeWord:
    def __init__(self, cfg: WakewordConfig) -> None:
        from openwakeword.model import Model

        self.cfg = cfg
        self.model = Model(wakeword_models=[cfg.model], inference_framework=cfg.inference_framework)
        self._last = 0.0

    def score(self, chunk: np.ndarray) -> float:
        return max(self.model.predict(chunk).values(), default=0.0)

    def process(self, chunk: np.ndarray) -> bool:
        """True jika wake word terdeteksi (dan lewat masa cooldown)."""
        if self.score(chunk) < self.cfg.threshold:
            return False
        now = time.monotonic()
        if now - self._last < self.cfg.cooldown_s:
            return False
        self._last = now
        return True

    def reset(self) -> None:
        self.model.reset()
