"""Bicara per kalimat: TTS mulai saat kalimat pertama LLM selesai (latensi terasa lebih kecil)."""

from __future__ import annotations

import queue
import re
import threading
import time

from loguru import logger

from jarvis.tts import TTS

_END = re.compile(r"(?<=[.!?])\s+")


_LONG_DECIMAL = re.compile(r"(\d+)([.,])(\d{2})\d{2,}")


def speakable(text: str) -> str:
    """Rapikan untuk diucapkan: desimal panjang (3,141592653…) dibulatkan ke 2 angka di belakang
    koma, lalu semua angka dieja (kalimat Indonesia; Inggris dibiarkan, mesin suara membacanya
    sendiri). Digit mentah dibaca ngawur oleh Fish."""
    from jarvis.brain.language import guess

    text = _LONG_DECIMAL.sub(r"\1\2\3", text)
    if guess(text) == "en":
        return text
    from jarvis.tts.numbers import spell_numbers

    return spell_numbers(text)


def split_sentences(buf: str) -> tuple[list[str], str]:
    """Pisah teks jadi kalimat lengkap + sisa yang belum selesai."""
    parts = _END.split(buf)
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


class SentenceSpeaker:
    def __init__(self, tts: TTS, max_chars: int) -> None:
        self.tts = tts
        self.budget = max_chars
        self.first_audio_at: float | None = None
        self._cancelled = False
        self._q: queue.Queue[str | None] = queue.Queue()
        self._t = threading.Thread(target=self._worker, daemon=True)
        self._t.start()

    def _worker(self) -> None:
        while (s := self._q.get()) is not None:
            if self._cancelled:
                continue
            if self.first_audio_at is None:
                self.first_audio_at = time.perf_counter()
            try:
                self.tts.speak(s)
            except Exception as e:  # noqa: BLE001 — TTS gagal tidak boleh mematikan app
                logger.error(f"TTS gagal: {e}")

    def cancel(self) -> None:
        """Interupsi: hentikan kalimat yang sedang diucapkan dan buang antrean."""
        self._cancelled = True
        self.tts.stop()

    def say(self, sentence: str) -> None:
        sentence = speakable(sentence.strip())
        if not sentence or self.budget <= 0 or self._cancelled:
            return
        self.budget -= len(sentence)
        self._q.put(sentence)

    def finish(self) -> None:
        self._q.put(None)
        self._t.join()
