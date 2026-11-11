from __future__ import annotations

import numpy as np
import pytest

from jarvis.audio import sounds


@pytest.mark.parametrize("rate", [16000, 44100, 48000])
@pytest.mark.parametrize(
    ("freqs", "dur"), [([880, 1320], 0.25), ([1000, 800], 0.07), ([400, 220], 0.28), ([700], 0.12)]
)
def test_tone_is_clickless_and_not_clipping(freqs, dur, rate) -> None:
    w = sounds._tone(freqs, dur, rate)
    assert w.dtype == np.float32 and len(w) == int(rate * dur)
    assert np.isfinite(w).all() and np.abs(w).max() < 0.5  # tidak clipping, tidak keras
    assert abs(w[0]) < 1e-3 and abs(w[-1]) < 1e-3  # mulai/akhir di nol: tanpa klik
    # lompatan antar sampel kecil (tanpa diskontinuitas yang terdengar sebagai "berdetak")
    assert np.abs(np.diff(w)).max() < 0.1


def test_pad_adds_silence_around_the_tone() -> None:
    w = sounds._tone([880], 0.1, 48000)
    p = sounds._pad(w, 48000)
    assert len(p) == len(w) + int(48000 * sounds.LEAD_S) + int(48000 * sounds.TAIL_S)
    assert not p[: int(48000 * sounds.LEAD_S)].any() and not p[-int(48000 * sounds.TAIL_S) :].any()


def test_play_never_raises_without_an_output_device(monkeypatch) -> None:
    def boom(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("tidak ada perangkat")

    monkeypatch.setattr(sounds.sd, "query_devices", boom)
    beeper = sounds._Beeper()
    beeper.play(lambda r: np.zeros(10, np.float32), None)  # tidak melempar


def test_beeper_callback_streams_the_buffer_then_silence() -> None:
    beeper = sounds._Beeper()
    beeper._buf = np.array([0.1, 0.2, 0.3], np.float32)
    out = np.ones((5, 1), np.float32)
    beeper._callback(out, 5, None, None)
    assert out[:, 0].tolist() == pytest.approx([0.1, 0.2, 0.3, 0.0, 0.0])
    assert len(beeper._buf) == 0
