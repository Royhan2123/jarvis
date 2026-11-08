"""Ukur latensi tiap tahap (STT, LLM, TTS). Jalankan: uv run python -m jarvis.bench

Contoh override sementara: --set llm.num_ctx=2048 --set stt.model=small
"""

from __future__ import annotations

import argparse
import statistics
import time
import wave
from pathlib import Path

import numpy as np

from jarvis.config import Config, load_config
from jarvis.tts.stream import split_sentences

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pertanyaan.wav"
QUESTION = "Apa ibu kota Jepang?"


def ensure_fixture(cfg: Config) -> np.ndarray:
    """Audio contoh 16 kHz: dibuat sekali dari Piper, lalu dipakai ulang."""
    if not FIXTURE.exists():
        from scipy.signal import resample_poly

        from jarvis.tts.piper import PiperTTS

        audio, rate = PiperTTS(cfg).synthesize(QUESTION)
        pcm = resample_poly(audio.astype(np.float32), 16000, rate).astype(np.int16)
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(FIXTURE), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm.tobytes())
    with wave.open(str(FIXTURE), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def apply_overrides(cfg: Config, sets: list[str]) -> Config:
    for item in sets:
        key, _, raw = item.partition("=")
        section, _, field = key.partition(".")
        target = getattr(cfg, section)
        current = getattr(target, field)
        value: object = raw
        if isinstance(current, bool):
            value = raw.lower() in {"1", "true", "yes"}
        elif isinstance(current, int):
            value = int(raw)
        elif isinstance(current, float):
            value = float(raw)
        setattr(target, field, value)
    return cfg


def med(xs: list[float]) -> float:
    return statistics.median(xs)


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis.bench")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--set", action="append", default=[], metavar="seksi.kunci=nilai")
    ap.add_argument("--skip", action="append", default=[], choices=["stt", "llm", "tts"])
    args = ap.parse_args()
    cfg = apply_overrides(load_config(args.config), args.set)

    audio = ensure_fixture(cfg)
    res: dict[str, list[float]] = {
        "stt": [],
        "llm_token1": [],
        "llm_sentence1": [],
        "llm_total": [],
    }
    res["tts_synth"] = []

    if "stt" not in args.skip:
        from jarvis.stt.whisper import WhisperSTT

        stt = WhisperSTT(cfg.stt)
        stt.transcribe(audio)  # pemanasan
        for _ in range(args.runs):
            t = time.perf_counter()
            text = stt.transcribe(audio)
            res["stt"].append(time.perf_counter() - t)
        print(f"STT terbaca: '{text}'")

    first_sentence = "Ibu kota Jepang adalah Tokyo."
    if "llm" not in args.skip:
        from jarvis.brain.llm import LLM

        list(LLM(cfg).ask("Halo"))  # pemanasan: model sudah di RAM
        for _ in range(args.runs):
            llm = LLM(cfg)  # riwayat kosong
            t = time.perf_counter()
            t1 = ts = None
            buf = ""
            for piece in llm.ask(QUESTION):
                now = time.perf_counter()
                t1 = t1 or now
                buf += piece
                if ts is None and split_sentences(buf)[0]:
                    ts = now
                    first_sentence = split_sentences(buf)[0][0]
            end = time.perf_counter()
            res["llm_token1"].append((t1 or end) - t)
            res["llm_sentence1"].append((ts or end) - t)
            res["llm_total"].append(end - t)

    if "tts" not in args.skip:
        from jarvis.tts.piper import PiperTTS

        tts = PiperTTS(cfg)
        tts.synthesize(first_sentence)
        for _ in range(args.runs):
            t = time.perf_counter()
            tts.synthesize(first_sentence)
            res["tts_synth"].append(time.perf_counter() - t)

    print(f"\nMedian dari {args.runs} kali (detik)  — override: {args.set or '-'}")
    print(f"{'tahap':<22}{'median':>8}   target")
    targets = {"stt": "≤ 1.0", "llm_token1": "≤ 1.5", "tts_synth": "≤ 0.4"}
    for k, v in res.items():
        if v:
            print(f"{k:<22}{med(v):>8.2f}   {targets.get(k, '')}")
    if all(res[k] for k in ("stt", "llm_sentence1", "tts_synth")):
        total = med(res["stt"]) + med(res["llm_sentence1"]) + med(res["tts_synth"])
        print(f"{'MULAI BICARA (est.)':<22}{total:>8.2f}   ≤ 5.0")


if __name__ == "__main__":
    main()
