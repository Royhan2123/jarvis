"""CLI setup: python -m jarvis.setup {check,list-mics,download-voice,download-models}"""

from __future__ import annotations

import argparse
import sys
import urllib.request

import sounddevice as sd

from jarvis.config import load_config
from jarvis.tts.piper import resolve_voice, voices_dir

_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
_VOICE_PATHS = {"id_ID-news_tts-medium": "id/id_ID/news_tts/medium"}


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
    for name in dict.fromkeys([cfg.stt.wake_model, cfg.stt.model]):
        print(f"⬇ Whisper '{name}'…")
        WhisperModel(name, device="cpu", compute_type=cfg.stt.compute_type)
    print("✅ Model siap")


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis.setup")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("list-mics")
    sub.add_parser("download-models")
    v = sub.add_parser("download-voice")
    v.add_argument("name", nargs="?", default="id_ID-news_tts-medium")
    args = ap.parse_args()

    if args.cmd == "list-mics":
        list_mics()
    elif args.cmd == "download-voice":
        download_voice(args.name)
    elif args.cmd == "download-models":
        download_models(args.config)
    else:
        from jarvis.__main__ import check

        sys.exit(0 if check(load_config(args.config)) else 1)


if __name__ == "__main__":
    main()
