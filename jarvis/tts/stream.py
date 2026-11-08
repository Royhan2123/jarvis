"""Bicara per kalimat: TTS mulai saat kalimat pertama LLM selesai (latensi terasa lebih kecil)."""

from __future__ import annotations

import queue
import re
import threading
import time

from loguru import logger

from jarvis.tts import TTS

_END = re.compile(r"(?<=[.!?])\s+")


def split_sentences(buf: str) -> tuple[list[str], str]:
    """Pisah teks jadi kalimat lengkap + sisa yang belum selesai."""
    parts = _END.split(buf)
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


class SentenceSpeaker:
    def __init__(self, tts: TTS, max_chars: int) -> None:
        self.tts = tts
        self.budget = max_chars
        self.first_audio_at: float | None = None
        self._q: queue.Queue[str | None] = queue.Queue()
        self._t = threading.Thread(target=self._worker, daemon=True)
        self._t.start()

    def _worker(self) -> None:
        while (s := self._q.get()) is not None:
            if self.first_audio_at is None:
                self.first_audio_at = time.perf_counter()
            try:
                self.tts.speak(s)
            except Exception as e:  # noqa: BLE001 — TTS gagal tidak boleh mematikan app
                logger.error(f"TTS gagal: {e}")

    def say(self, sentence: str) -> None:
        sentence = sentence.strip()
        if not sentence or self.budget <= 0:
            return
        self.budget -= len(sentence)
        self._q.put(sentence)

    def finish(self) -> None:
        self._q.put(None)
        self._t.join()
