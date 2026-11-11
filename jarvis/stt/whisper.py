"""Speech-to-text dengan faster-whisper (CTranslate2, int8 di CPU)."""

from __future__ import annotations

import re

import numpy as np
from loguru import logger

from jarvis.config import STTConfig


def is_repetitive(text: str) -> bool:
    """Halusinasi Whisper pada noise: kalimat/angka yang diulang puluhan kali → buang."""
    words = re.findall(r"\w+", text.lower())
    if len(words) < 12:
        return False
    return len(set(words)) / len(words) < 0.35


class WhisperSTT:
    def __init__(self, cfg: STTConfig) -> None:
        from faster_whisper import WhisperModel

        self.cfg = cfg
        self.last_logprob = 0.0
        self.last_language = cfg.language if cfg.language in ("id", "en") else "id"
        self.model = WhisperModel(
            cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            cpu_threads=cfg.cpu_threads,
        )
        self.detector = None
        self._detector_failed = False
        from jarvis.brain.language import detect_candidates

        self.candidates = set(detect_candidates(cfg.detect_languages))
        if cfg.language == "auto":
            self._load_detector()

    def _load_detector(self) -> None:
        """Muat model deteksi bahasa (bisa belakangan, mis. setelah 'bahasa otomatis')."""
        if self.detector is not None or self._detector_failed:
            return
        from faster_whisper import WhisperModel

        cfg = self.cfg
        try:
            self.detector = WhisperModel(
                cfg.detect_model,
                device=cfg.device,
                compute_type=cfg.compute_type,
                cpu_threads=cfg.cpu_threads,
            )
        except Exception as e:  # noqa: BLE001 — model belum diunduh/offline: tetap Indonesia
            self._detector_failed = True
            logger.warning(f"Deteksi bahasa dimatikan ({e}); memakai bahasa Indonesia")

    def detect_language(self, samples: np.ndarray) -> str:
        """Kode bahasa ucapan: bahasa non-Indonesia terkuat di `detect_languages` bila yakin
        (≥ detect_min_prob dan mengalahkan Indonesia), selain itu 'id'."""
        self._load_detector()
        if self.detector is None:
            return "id"
        _, _, probs = self.detector.detect_language(samples)
        p = dict(probs)
        others = [c for c in self.candidates if c != "id"]
        best = max(others, key=lambda c: p.get(c, 0.0), default="id")
        if p.get(best, 0.0) >= self.cfg.detect_min_prob and p.get(best, 0.0) > p.get("id", 0.0):
            return best
        return "id"

    def transcribe(self, audio: np.ndarray, fast: bool = False) -> str:
        """audio: int16 mono 16 kHz. fast=True: tanpa fallback suhu (untuk wake)."""
        samples = audio.astype(np.float32) / 32768.0
        if fast:  # wake: frasa pemanggil selalu dikenali sebagai bahasa Indonesia/"Hello"
            lang = self.cfg.language if self.cfg.language in ("id", "en") else "id"
        elif self.cfg.language == "auto":
            lang = self.detect_language(samples)
        else:
            lang = self.cfg.language
        if not fast:
            self.last_language = lang or "id"
        if fast:
            prompt = self.cfg.wake_prompt or None
        else:
            prompts = {"id": self.cfg.initial_prompt, "en": self.cfg.initial_prompt_en}
            prompt = (
                prompts.get(lang or "id") or None
            )  # bahasa lain: tanpa prompt (id/en menyesatkan)
        segments, _ = self.model.transcribe(
            samples,
            language=lang,
            beam_size=self.cfg.beam_size,
            initial_prompt=prompt,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
            **({"temperature": 0.0, "without_timestamps": True} if fast else {}),
        )
        segs = list(segments)
        text = " ".join(s.text.strip() for s in segs).strip()
        # rata-rata keyakinan per segmen (≈ -0.35 untuk ucapan jelas, ≈ -1.0 untuk salah dengar)
        self.last_logprob = sum(s.avg_logprob for s in segs) / len(segs) if segs else 0.0
        if self._is_prompt_echo(text, prompt or "") or is_repetitive(text):
            return ""
        return text

    def _is_prompt_echo(self, text: str, prompt_text: str | None = None) -> bool:
        """Whisper kadang mengulang initial_prompt saat hening/noise → buang."""
        words = set(re.findall(r"\w+", text.lower()))
        prompt = set(re.findall(r"\w+", (prompt_text or self.cfg.initial_prompt or "").lower()))
        return bool(words) and len(words) >= 4 and len(words - prompt) <= 1

    def is_unclear(self) -> bool:
        """True jika transkripsi terakhir terlalu tidak yakin (kemungkinan salah dengar)."""
        floor = self.cfg.min_logprob
        return floor is not None and self.last_logprob < floor
