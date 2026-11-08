"""State machine & orkestrasi: IDLE → LISTENING → THINKING → SPEAKING."""

from __future__ import annotations

import re
import time
from enum import StrEnum

from loguru import logger

from jarvis.audio.sounds import play_ting
from jarvis.audio.stream import MicStream
from jarvis.audio.vad import VAD, record_utterance
from jarvis.audio.wakeword import WakeWord, match_phrase
from jarvis.brain.llm import LLM
from jarvis.config import Config, VADConfig
from jarvis.stt.whisper import WhisperSTT
from jarvis.tts import TTS, build_tts
from jarvis.tts.stream import SentenceSpeaker, split_sentences


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
        self.wake = WakeWord(cfg.wakeword) if cfg.wakeword.engine == "openwakeword" else None
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
        self._set(State.THINKING)
        t0 = time.perf_counter()
        text = self.stt.transcribe(audio)
        if not text:
            logger.info("(tidak ada teks terdengar)")
            return None
        return self.handle_text(text, t0)

    def handle_text(self, text: str, t0: float | None = None) -> str | None:
        """LLM → TTS (per kalimat, berjalan paralel dengan LLM) untuk teks perintah."""
        self._set(State.THINKING)
        t_start = time.perf_counter()
        t0 = t0 or t_start
        t_stt = t_start
        print(f"Kamu: {text}")
        print(f"{self.cfg.general.name}: ", end="", flush=True)
        speaker = SentenceSpeaker(self.tts, self.cfg.tts.max_spoken_chars)
        reply, buf, t_first_token = "", "", None
        try:
            for piece in self.llm.ask(text):
                t_first_token = t_first_token or time.perf_counter()
                print(piece, end="", flush=True)
                reply += piece
                buf += piece
                done, buf = split_sentences(buf)
                for sentence in done:
                    self._set(State.SPEAKING)
                    speaker.say(sentence)
        except Exception as e:  # noqa: BLE001
            logger.error(f"LLM gagal: {e}")
        print()
        speaker.say(buf)
        t_llm = time.perf_counter()
        speaker.finish()
        t_end = time.perf_counter()
        first = (speaker.first_audio_at or t_end) - t0
        logger.debug(
            f"[latency] stt={t_stt - t0:.2f}s "
            f"llm_first_token={((t_first_token or t_llm) - t_start):.2f}s "
            f"llm_total={t_llm - t_start:.2f}s mulai_bicara={first:.2f}s total={t_end - t0:.2f}s"
        )
        return reply.strip() or None

    def _wait_wake_phrase(self) -> str | None:
        """Mode frasa: dengarkan ucapan pendek, transkripsi, cocokkan frasa.

        Return sisa ucapan setelah frasa ("" jika hanya frasa), None jika belum terdengar.
        """
        c, v = self.cfg, self.cfg.vad
        short = VADConfig(threshold=v.threshold, silence_ms=500, max_record_s=5, listen_timeout_s=1)
        self.vad.reset()
        seg = record_utterance(
            self._chunks(), self.vad.is_speech, short, c.audio.sample_rate, c.audio.chunk_ms
        )
        if seg is None or len(seg) < c.audio.sample_rate * 0.4:
            return None
        t0 = time.perf_counter()
        text = self.stt.transcribe(seg)
        rest = match_phrase(text, c.wakeword.phrase)
        logger.debug(
            f"[wake] '{text}' → {'COCOK' if rest is not None else 'abaikan'} "
            f"({time.perf_counter() - t0:.2f}s)"
        )
        return rest

    def run(self) -> None:
        phrase_mode = self.wake is None
        self.mic.start()
        name = self.cfg.wakeword.phrase if phrase_mode else self.cfg.wakeword.model
        print(f'🎙️  Katakan "{name}" (Ctrl+C untuk berhenti)')
        try:
            while True:
                remainder = ""
                if phrase_mode:
                    rest = self._wait_wake_phrase()
                    if rest is None:
                        continue
                    remainder = rest
                else:
                    chunk = self.mic.read()
                    if chunk is None or not self.wake.process(chunk):
                        continue
                logger.info("Wake word terdeteksi")
                if self.cfg.audio.sounds:
                    play_ting(self.cfg.audio.output_device)
                    time.sleep(0.25)  # tunggu 'ting' selesai agar tidak terekam mic
                if len(remainder) >= 3:  # perintah diucapkan satu napas: "hey teman, jam berapa"
                    self.handle_text(remainder)
                else:
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
                if self.wake:
                    self.wake.reset()
                self._set(State.IDLE)
        except KeyboardInterrupt:
            print()
        finally:
            self.mic.stop()
