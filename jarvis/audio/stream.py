"""Input mikrofon 16 kHz mono int16 lewat sounddevice. Callback hanya mengisi queue."""

from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd
from loguru import logger

from jarvis.config import AudioConfig


class MicStream:
    def __init__(self, cfg: AudioConfig) -> None:
        self.cfg = cfg
        self.chunk_samples = cfg.sample_rate * cfg.chunk_ms // 1000
        self._q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._stream: sd.InputStream | None = None

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        if status:
            logger.warning(f"audio status: {status}")
        try:
            self._q.put_nowait(indata[:, 0].copy())
        except queue.Full:  # consumer terlambat: buang chunk, jangan blocking
            pass

    def start(self) -> None:
        self._stream = sd.InputStream(
            device=self.cfg.input_device,
            samplerate=self.cfg.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_samples,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def flush(self) -> None:
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None
