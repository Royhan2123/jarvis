"""VAD bawaan faster_whisper (Silero ONNX, tanpa PyTorch) + perekam satu ucapan."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import numpy as np

from jarvis.config import VADConfig

WINDOW = 512  # sampel per jendela Silero @16 kHz
TAIL_WINDOWS = 8  # konteks yang dievaluasi tiap chunk (~0.26 s)


class VAD:
    """Menilai apakah chunk terbaru berisi suara manusia (stateless per panggilan)."""

    def __init__(self, cfg: VADConfig) -> None:
        from faster_whisper.vad import get_vad_model

        self.cfg = cfg
        self.model = get_vad_model()
        self._tail = np.zeros(0, dtype=np.float32)

    def is_speech(self, chunk: np.ndarray) -> bool:
        audio = chunk.astype(np.float32) / 32768.0
        self._tail = np.concatenate([self._tail, audio])[-WINDOW * TAIL_WINDOWS :]
        n = (len(self._tail) // WINDOW) * WINDOW
        if n == 0:
            return False
        probs = np.asarray(self.model(self._tail[-n:].copy())).reshape(-1)
        return bool(probs[-2:].max() >= self.cfg.threshold)

    def reset(self) -> None:
        self._tail = np.zeros(0, dtype=np.float32)

    def speech_stats(self, samples: np.ndarray) -> tuple[float, float]:
        """(detik berbicara, porsi berbicara 0..1) pada satu segmen utuh; ±15 ms untuk 3 detik."""
        audio = samples.astype(np.float32) / 32768.0
        n = (len(audio) // WINDOW) * WINDOW
        if n == 0:
            return 0.0, 0.0
        probs = np.asarray(self.model(audio[:n].copy())).reshape(-1)
        voiced = float((probs >= self.cfg.threshold).sum()) * WINDOW / 16000
        return voiced, voiced / (n / 16000)


def record_utterance(
    chunks: Iterator[np.ndarray | None],
    is_speech: Callable[[np.ndarray], bool],
    cfg: VADConfig,
    sample_rate: int,
    chunk_ms: int,
    preroll_chunks: int = 3,
) -> np.ndarray | None:
    """Rekam sampai diam `silence_ms`. None jika tidak ada suara dalam `listen_timeout_s`."""
    silence_limit = cfg.silence_ms // chunk_ms
    timeout_chunks = cfg.listen_timeout_s * 1000 // chunk_ms
    max_chunks = cfg.max_record_s * 1000 // chunk_ms
    preroll: list[np.ndarray] = []
    voiced: list[np.ndarray] = []
    started = False
    silent = 0
    waited = 0
    for chunk in chunks:
        if chunk is None:
            continue
        speech = is_speech(chunk)
        if not started:
            preroll = [*preroll, chunk][-preroll_chunks:]
            waited += 1
            if speech:
                started = True
                voiced = [*preroll]
            elif waited >= timeout_chunks:
                return None
            continue
        voiced.append(chunk)
        silent = 0 if speech else silent + 1
        if silent >= silence_limit or len(voiced) >= max_chunks:
            break
    return np.concatenate(voiced) if voiced else None
