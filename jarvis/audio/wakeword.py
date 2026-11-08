"""Deteksi wake word 'hey_jarvis' dengan openWakeWord (ONNX)."""

from __future__ import annotations

import re
import time
from difflib import SequenceMatcher

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


_GREETINGS = {"hey", "hei", "hai", "hay", "he", "hi", "hello", "halo"}


def _norm(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def _word_match(heard: str, target: str) -> bool:
    if target in _GREETINGS and heard in _GREETINGS:
        return True
    return SequenceMatcher(None, heard, target).ratio() >= 0.75


def match_phrase(text: str, phrase: str) -> str | None:
    """Cari `phrase` (toleran salah dengar) di awal `text`.

    Mengembalikan sisa ucapan setelah frasa ("" jika tidak ada), atau None jika tidak cocok.
    """
    words, target = _norm(text), _norm(phrase)
    n = len(target)
    # frasa harus muncul di awal ucapan (maks 1 kata sebelumnya, mis. "oke hey teman")
    for i in range(min(2, len(words) - n + 1)):
        if all(_word_match(w, t) for w, t in zip(words[i : i + n], target, strict=True)):
            return " ".join(words[i + n :])
    want = "".join(target)
    for k in range(1, n + 1):  # Whisper kadang menyambung: "heyteman"
        if SequenceMatcher(None, "".join(words[:k]), want).ratio() >= 0.85:
            return " ".join(words[k:])
    return None
