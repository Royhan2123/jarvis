"""Bunyi notifikasi dibuat prosedural (sine + envelope), tanpa audio berhak cipta."""

from __future__ import annotations

import numpy as np
import sounddevice as sd


def _tone(freqs: list[float], dur: float, rate: int = 16000, gain: float = 0.25) -> np.ndarray:
    n = int(rate * dur)
    t = np.arange(n) / rate
    f = np.linspace(freqs[0], freqs[-1], n)
    wave = np.sin(2 * np.pi * np.cumsum(f) / rate)
    env = np.minimum(1, np.minimum(t / 0.01, (dur - t) / 0.08))
    return (wave * env * gain * 32767).astype(np.int16)


def play_ting(device: int | str | None = None) -> None:
    """'ting' naik, lembut, ~150 ms (non-blocking)."""
    sd.play(_tone([880, 1320], 0.15), 16000, device=device)
