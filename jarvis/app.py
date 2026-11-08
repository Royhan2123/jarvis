"""State machine & orkestrasi: IDLE → LISTENING → THINKING → SPEAKING."""

from __future__ import annotations

import re
import time
from enum import StrEnum

from loguru import logger

from jarvis.audio.sounds import play_ting
from jarvis.audio.stream import MicStream
from jarvis.audio.vad import VAD, record_utterance
from jarvis.audio.wakeword import WakeWord
from jarvis.brain.llm import LLM
from jarvis.config import Config
from jarvis.stt.whisper import WhisperSTT
from jarvis.tts import TTS, build_tts


class State(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


def shorten_for_speech(text: str, max_chars: int) -> str:
    """Potong di batas kalimat agar tidak melebihi max_chars."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > 0 else cut.rstrip() + "."


class Jarvis:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.state = State.IDLE
        logger.info("Memuat model (wake word, VAD, STT, TTS)…")
        self.mic = MicStream(cfg.audio)
        self.wake = WakeWord(cfg.wakeword)
        self.vad = VAD(cfg.vad)
        self.stt = WhisperSTT(cfg.stt)
        self.llm = LLM(cfg)
        self.tts: TTS = build_tts(cfg)

    def _set(self, state: State) -> None:
        self.state = state
        logger.debug(f"state → {state.value}")

    def _chunks(self):
        while True:
            yield self.mic.read(timeout=0.5)

    def handle_utterance(self, audio) -> str | None:
        """STT → LLM → TTS untuk satu ucapan. Mengembalikan jawaban (atau None)."""
        t0 = time.perf_counter()
        self._set(State.THINKING)
        text = self.stt.transcribe(audio)
        t_stt = time.perf_counter()
        if not text:
            logger.info("(tidak ada teks terdengar)")
            return None
        print(f"Kamu: {text}")
        reply = "".join(self.llm.ask(text)).strip()
        t_llm = time.perf_counter()
        print(f"{self.cfg.general.name}: {reply}")
        if reply:
            self._set(State.SPEAKING)
            try:
                self.tts.speak(shorten_for_speech(reply, self.cfg.tts.max_spoken_chars))
            except Exception as e:  # noqa: BLE001 — TTS gagal tidak boleh mematikan app
                logger.error(f"TTS gagal: {e}")
        t_tts = time.perf_counter()
        logger.debug(
            f"[latency] stt={t_stt - t0:.2f}s llm={t_llm - t_stt:.2f}s "
            f"tts={t_tts - t_llm:.2f}s total={t_tts - t0:.2f}s"
        )
        return reply

    def run(self) -> None:
        self.mic.start()
        print('🎙️  Katakan "Hey Jarvis" (Ctrl+C untuk berhenti)')
        try:
            while True:
                chunk = self.mic.read()
                if chunk is None or not self.wake.process(chunk):
                    continue
                logger.info("Wake word terdeteksi")
                if self.cfg.audio.sounds:
                    play_ting(self.cfg.audio.output_device)
                self._set(State.LISTENING)
                self.mic.flush()
                self.vad.reset()
                audio = record_utterance(
                    self._chunks(),
                    self.vad.is_speech,
                    self.cfg.vad,
                    self.cfg.audio.sample_rate,
                    self.cfg.audio.chunk_ms,
                )
                if audio is not None:
                    self.handle_utterance(audio)
                else:
                    logger.info("Tidak ada suara, kembali idle")
                self.mic.flush()
                self.wake.reset()
                self._set(State.IDLE)
        except KeyboardInterrupt:
            print()
        finally:
            self.mic.stop()
