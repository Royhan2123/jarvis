"""CLI setup: python -m jarvis.setup {check,list-mics,download-voice,download-models}"""

from __future__ import annotations

import argparse
import sys
import urllib.request

import sounddevice as sd

from jarvis.config import load_config
from jarvis.tts.piper import resolve_voice, voices_dir

_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
_VOICE_PATHS = {
    "id_ID-news_tts-medium": "id/id_ID/news_tts/medium",
    "en_US-ryan-medium": "en/en_US/ryan/medium",  # suara Inggris pria (±63 MB)
    "en_US-amy-medium": "en/en_US/amy/medium",  # suara Inggris wanita (±63 MB)
}


def list_mics() -> None:
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"{i}: {d['name']}")


def download_voice(name: str) -> None:
    sub = _VOICE_PATHS.get(name)
    if sub is None:
        sys.exit(f"Suara '{name}' tidak dikenal. Pilihan: {', '.join(_VOICE_PATHS)}")
    voices_dir().mkdir(parents=True, exist_ok=True)
    target = resolve_voice(name)
    for suffix in (".onnx", ".onnx.json"):
        dest = target.with_name(name + suffix)
        if dest.exists():
            print(f"✓ {dest.name} sudah ada")
            continue
        url = f"{_HF}/{sub}/{name}{suffix}"
        print(f"⬇ {url}")
        urllib.request.urlretrieve(url, dest)  # noqa: S310 — URL tetap (HF rhasspy)
    print(f"✅ Suara tersimpan di {voices_dir()}")


def download_models(config: str) -> None:
    """Unduh model wake word & Whisper sekali di awal (setelah itu 100% offline)."""
    import openwakeword
    from faster_whisper import WhisperModel

    cfg = load_config(config)
    print("⬇ model wake word…")
    openwakeword.utils.download_models([cfg.wakeword.model])
    names = [cfg.stt.wake_model, cfg.stt.model]
    if cfg.stt.language == "auto":
        names.append(cfg.stt.detect_model)  # pendeteksi bahasa Indonesia/Inggris
    for name in dict.fromkeys(names):
        print(f"⬇ Whisper '{name}'…")
        WhisperModel(name, device="cpu", compute_type=cfg.stt.compute_type)
    print("✅ Model siap")


def test_wake(config: str, phrase: str | None, tries: int) -> None:
    """Ucapkan frasa pemanggil beberapa kali; tampilkan apa yang didengar Whisper & cocok/tidak."""
    from jarvis.audio.stream import MicStream
    from jarvis.audio.vad import VAD, record_utterance
    from jarvis.audio.wakeword import match_any
    from jarvis.config import VADConfig
    from jarvis.stt.whisper import WhisperSTT

    cfg = load_config(config)
    phrases = [phrase] if phrase else cfg.wakeword.all_phrases
    stt = WhisperSTT(cfg.stt.model_copy(update={"model": cfg.stt.wake_model, "beam_size": 1}))
    mic, vad = MicStream(cfg.audio), VAD(cfg.vad)
    short = VADConfig(
        threshold=cfg.vad.threshold, silence_ms=400, max_record_s=3, listen_timeout_s=6
    )
    mic.start()
    hits = 0
    try:
        for i in range(1, tries + 1):
            print(f"[{i}/{tries}] Ucapkan: {' / '.join(phrases)} ...")
            mic.flush()
            vad.reset()
            seg = record_utterance(
                (mic.read(timeout=0.5) for _ in iter(int, 1)),
                vad.is_speech,
                short,
                cfg.audio.sample_rate,
                cfg.audio.chunk_ms,
            )
            if seg is None:
                print("   (tidak ada suara)")
                continue
            text = stt.transcribe(seg, fast=True)
            ok = match_any(text, phrases) is not None
            hits += ok
            print(f"   terdengar: '{text}' → {'COCOK ✅' if ok else 'tidak cocok ❌'}")
    finally:
        mic.stop()
    print(
        f"\nBerhasil {hits}/{tries}. Di bawah 4/5? Coba frasa 2 kata atau "
        "tambah variasi di wakeword.phrases."
    )


def test_stt(config: str, tries: int, save_dir: str | None) -> None:
    """Rekam ucapanmu, bandingkan hasil transkripsi beberapa pengaturan pada audio yang SAMA."""
    import time
    import wave
    from pathlib import Path

    import numpy as np

    from jarvis.audio.stream import MicStream
    from jarvis.audio.vad import VAD, record_utterance
    from jarvis.stt.whisper import WhisperSTT

    cfg = load_config(config)
    base = cfg.stt
    variants = {
        "small b1 (sekarang)": base,
        "small b5": base.model_copy(update={"beam_size": 5}),
        "small b5 tanpa prompt": base.model_copy(update={"beam_size": 5, "initial_prompt": ""}),
        "medium b1": base.model_copy(update={"model": "medium"}),
    }
    engines: dict[str, WhisperSTT] = {}
    for v in variants.values():
        engines.setdefault(v.model, WhisperSTT(v))
    mic, vad = MicStream(cfg.audio), VAD(cfg.vad)
    mic.start()
    out_dir = Path(save_dir) if save_dir else None
    try:
        for i in range(1, tries + 1):
            print(f"\n[{i}/{tries}] Ucapkan satu kalimat (mis. 'apa ibu kota Jepang') ...")
            mic.flush()
            vad.reset()
            seg = record_utterance(
                (mic.read(timeout=0.5) for _ in iter(int, 1)),
                vad.is_speech,
                cfg.vad,
                cfg.audio.sample_rate,
                cfg.audio.chunk_ms,
            )
            if seg is None:
                print("   (tidak ada suara)")
                continue
            peak = int(np.abs(seg).max())
            rms = float(np.sqrt(np.mean(seg.astype(np.float32) ** 2)))
            dur = len(seg) / cfg.audio.sample_rate
            print(f"   durasi {dur:.1f}s, puncak {peak}/32767, rms {rms:.0f}")
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                with wave.open(str(out_dir / f"ucapan_{i}.wav"), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(cfg.audio.sample_rate)
                    w.writeframes(seg.tobytes())
            for name, v in variants.items():
                eng = engines[v.model]
                eng.cfg = v
                t0 = time.perf_counter()
                text = eng.transcribe(seg)
                print(f"   {name:<24} {time.perf_counter() - t0:4.1f}s  '{text}'")
    finally:
        mic.stop()


def set_ai(args: argparse.Namespace) -> None:
    """Ganti penyedia AI; kunci dibaca lewat prompt tersembunyi (tidak lewat argumen/riwayat)."""
    import getpass

    from jarvis import ai_settings

    cfg = load_config(args.config)
    if args.provider:
        key = None
        if args.provider != "ollama" and not ai_settings.get_key(args.provider):
            key = getpass.getpass(f"Kunci API {args.provider} (tidak ditampilkan): ")
        try:
            ai_settings.update(
                cfg, args.provider, api_key=key, api_base=args.api_base,
                fast_model=args.model, smart_model=args.smart_model,
            )  # fmt: skip
        except ValueError as e:
            sys.exit(str(e))
    v = ai_settings.view(cfg)
    print(f"Penyedia: {v['provider']} | cepat: {v['fast_model']} | pintar: {v['smart_model']}")
    if args.test:
        try:
            print("Balasan uji:", ai_settings.test(cfg))
        except Exception as e:  # noqa: BLE001
            sys.exit(f"Gagal: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis.setup")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("list-mics")
    sub.add_parser("download-models")
    v = sub.add_parser("download-voice")
    v.add_argument("name", nargs="?", default="id_ID-news_tts-medium")
    sub.add_parser("index-docs")
    sub.add_parser("google-login")
    a = sub.add_parser("ai", help="pilih penyedia model bahasa (ollama bawaan, atau API online)")
    a.add_argument("provider", nargs="?", help="ollama | openai | anthropic | gemini | groq | ...")
    a.add_argument("--model", help="model cepat (online)")
    a.add_argument("--smart-model", help="model pintar (online, opsional)")
    a.add_argument("--api-base", help="alamat API (wajib untuk custom)")
    a.add_argument("--test", action="store_true", help="coba kirim satu pertanyaan uji")
    t = sub.add_parser("test-stt")
    t.add_argument("-n", "--tries", type=int, default=3)
    t.add_argument("--save", help="folder untuk menyimpan rekaman .wav")
    w = sub.add_parser("test-wake")
    w.add_argument("phrase", nargs="?", help="frasa yang diuji (default: dari config)")
    w.add_argument("-n", "--tries", type=int, default=5)
    args = ap.parse_args()

    if args.cmd == "list-mics":
        list_mics()
    elif args.cmd == "download-voice":
        download_voice(args.name)
    elif args.cmd == "google-login":
        from jarvis.online import google

        try:
            print(google.login(load_config(args.config)))
        except google.GoogleError as e:
            sys.exit(str(e))
    elif args.cmd == "ai":
        set_ai(args)
    elif args.cmd == "index-docs":
        from jarvis.brain.rag import DocIndex, ollama_embedder

        cfg = load_config(args.config)
        if not cfg.rag.folders:
            sys.exit("Isi rag.folders di config.yaml dulu")
        idx = DocIndex(cfg.rag, ollama_embedder(cfg))
        print(idx.index(), "| total (dokumen, potongan):", idx.count())
    elif args.cmd == "test-stt":
        test_stt(args.config, args.tries, args.save)
    elif args.cmd == "test-wake":
        test_wake(args.config, args.phrase, args.tries)
    elif args.cmd == "download-models":
        download_models(args.config)
    else:
        from jarvis.__main__ import check

        sys.exit(0 if check(load_config(args.config)) else 1)


if __name__ == "__main__":
    main()
