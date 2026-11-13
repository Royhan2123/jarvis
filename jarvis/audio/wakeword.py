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

    Mengembalikan sisa ucapan ASLI setelah frasa ("" jika tidak ada), atau None jika tidak cocok.
    """
    spans = [(m.group().lower(), m.end()) for m in re.finditer(r"\w+", text)]
    words = [w for w, _ in spans]
    target = _norm(phrase)
    n = len(target)

    def rest(k: int) -> str:
        """Teks asli setelah k kata pertama."""
        if k >= len(spans):
            return ""
        return text[spans[k - 1][1] :].lstrip(" \t,.:;!?-")

    # frasa 1 kata yang sangat umum ("hello") hanya sah di kata pertama → kurangi salah picu
    for i in range(min(1 if n == 1 else 2, len(words) - n + 1)):
        if all(_word_match(w, t) for w, t in zip(words[i : i + n], target, strict=True)):
            return rest(i + n)
    want = "".join(target)
    for k in range(1, n + 1) if n > 1 else []:  # Whisper kadang menyambung: "heyteman"
        if SequenceMatcher(None, "".join(words[:k]), want).ratio() >= 0.85:
            return rest(k)
    return None


def plausible_wake(text: str, phrases: list[str]) -> bool:
    """Penyaring murah: ada kata yang agak mirip (≥0.6) dengan kata pemanggil mana pun? Longgar
    sengaja (salah-positif hanya memicu pemeriksaan lebih teliti); kosong = bukan."""
    heard = _norm(text)
    wanted = {w for p in phrases for w in _norm(p)} | _GREETINGS
    return any(SequenceMatcher(None, h, w).ratio() >= 0.6 for h in heard for w in wanted)


def match_any(text: str, phrases: list[str]) -> str | None:
    """Coba semua frasa pemanggil; kembalikan sisa ucapan dari frasa pertama yang cocok."""
    for phrase in phrases:
        if (rest := match_phrase(text, phrase)) is not None:
            return rest
    return None
