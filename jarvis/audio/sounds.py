"""Bunyi notifikasi dibuat prosedural (sine + envelope), tanpa audio berhak cipta.

Dimainkan pada sample rate asli perangkat dengan buffer besar dan sedikit hening di awal/akhir:
membuka perangkat di 16 kHz dengan buffer kecil membuat bunyi pecah/berdetak di Mac saat CPU
dipakai Whisper/LLM, dan awal bunyi terpotong saat perangkat (speaker/Bluetooth) baru bangun.
"""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

LEAD_S = 0.01  # hening singkat di awal (stream selalu terbuka, jadi perangkat sudah bangun)
TAIL_S = 0.10  # hening di akhir supaya ekor bunyi tidak terpotong


def _tone(
    freqs: list[float],
    dur: float,
    rate: int = 48000,
    gain: float = 0.25,
    decay: float = 5.0,
) -> np.ndarray:
    """Nada meluncur dari freqs[0] ke freqs[-1] + dua harmonik lembut (terdengar seperti lonceng),
    attack berbentuk cosinus 8 ms dan peluruhan eksponensial; float32 di rentang -1..1."""
    n = int(rate * dur)
    t = np.arange(n) / rate
    phase = 2 * np.pi * np.cumsum(np.linspace(freqs[0], freqs[-1], n)) / rate
    wave = np.sin(phase) + 0.30 * np.sin(2 * phase) + 0.10 * np.sin(3 * phase)
    attack_n = max(1, int(rate * 0.008))
    attack = 0.5 * (1 - np.cos(np.pi * np.minimum(np.arange(n), attack_n) / attack_n))
    release_n = max(1, int(rate * min(0.03, dur / 3)))
    release = np.ones(n)
    release[-release_n:] = 0.5 * (1 + np.cos(np.pi * np.arange(release_n) / release_n))
    env = attack * np.exp(-decay * t / dur) * release
    return (wave / 1.4 * env * gain).astype(np.float32)


def _pad(wave: np.ndarray, rate: int) -> np.ndarray:
    return np.concatenate(
        [np.zeros(int(rate * LEAD_S), np.float32), wave, np.zeros(int(rate * TAIL_S), np.float32)]
    )


class _Beeper:
    """Satu stream keluaran yang selalu terbuka: bunyi tinggal dimasukkan ke buffer, jadi tanpa
    jeda membuka perangkat (±0.3 dtk di Mac) dan perangkat tetap "bangun" (awal bunyi utuh)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None
        self._device: int | str | None = None
        self._rate = 0
        self._buf = np.zeros(0, np.float32)

    def _callback(self, outdata, frames, _time, _status) -> None:  # noqa: ANN001
        with self._lock:
            chunk, self._buf = self._buf[:frames], self._buf[frames:]
        outdata[: len(chunk), 0] = chunk
        outdata[len(chunk) :, 0] = 0.0

    def _ensure(self, device: int | str | None) -> int:
        if self._stream is not None and device == self._device:
            return self._rate
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        rate = int(sd.query_devices(device, "output")["default_samplerate"])
        self._stream = sd.OutputStream(
            samplerate=rate,
            channels=1,
            dtype="float32",
            device=device,
            latency=0.1,
            callback=self._callback,
        )
        self._stream.start()
        self._device, self._rate = device, rate
        return rate

    def play(self, make, device: int | str | None) -> None:  # noqa: ANN001
        try:
            with self._lock:
                rate = self._ensure(device)
            wave = _pad(make(rate), rate)
            with self._lock:
                self._buf = wave  # bunyi baru menggantikan yang belum selesai
        except Exception:  # noqa: BLE001 — tak ada perangkat keluaran: bunyi notifikasi opsional
            self._stream = None


_BEEPER = _Beeper()


def warm(device: int | str | None = None) -> None:
    """Buka stream di awal (di thread sendiri) supaya "ting" pertama pun tanpa jeda."""
    threading.Thread(
        target=lambda: _BEEPER.play(lambda r: np.zeros(1, np.float32), device), daemon=True
    ).start()


def _play(make, device: int | str | None) -> None:  # noqa: ANN001
    _BEEPER.play(make, device)


def play_ting(device: int | str | None = None) -> None:
    """'ting' naik, lembut seperti lonceng kecil, ~250 ms."""
    _play(lambda r: _tone([880, 1320], 0.25, r, gain=0.30, decay=4.0), device)


def play_done(device: int | str | None = None) -> None:
    """Klik pendek: selesai mendengar."""
    _play(lambda r: _tone([1000, 800], 0.07, r, gain=0.22, decay=3.0), device)


def play_error(device: int | str | None = None) -> None:
    """Nada turun rendah."""
    _play(lambda r: _tone([400, 220], 0.28, r, gain=0.28, decay=2.5), device)


def play_confirm(device: int | str | None = None) -> None:
    """Dua nada pendek: butuh konfirmasi."""

    def make(rate: int) -> np.ndarray:
        gap = np.zeros(int(rate * 0.07), np.float32)
        tone = _tone([700], 0.12, rate, gain=0.28, decay=3.0)
        return np.concatenate([tone, gap, tone])

    _play(make, device)
