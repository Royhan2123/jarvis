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


def _play(wave: np.ndarray, device: int | str | None) -> None:
    sd.play(wave, 16000, device=device)


def play_done(device: int | str | None = None) -> None:
    """Klik pendek: selesai mendengar."""
    _play(_tone([1000, 800], 0.05, gain=0.2), device)


def play_error(device: int | str | None = None) -> None:
    """Nada turun rendah."""
    _play(_tone([400, 220], 0.25), device)


def play_confirm(device: int | str | None = None) -> None:
    """Dua nada pendek: butuh konfirmasi."""
    gap = np.zeros(int(16000 * 0.06), dtype=np.int16)
    _play(np.concatenate([_tone([700], 0.1), gap, _tone([700], 0.1)]), device)
