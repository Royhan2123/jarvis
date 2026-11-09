"""Entry point: python -m jarvis

--check   cek mic & Ollama
(default) mode teks: ketik pertanyaan, jawaban LLM tampil di terminal
--voice   mode teks + jawaban dibacakan
"""

from __future__ import annotations

import argparse
import sys

import ollama
from loguru import logger
from pydantic import ValidationError

from jarvis.brain.llm import LLM
from jarvis.config import Config, load_config
from jarvis.platform import get_adapter


def check(cfg: Config) -> bool:
    ok = True
    print("── Mikrofon & speaker ──")
    try:
        import sounddevice as sd

        print(sd.query_devices())
    except Exception as e:  # noqa: BLE001
        print(f"❌ Audio bermasalah: {e}")
        ok = False

    print("\n── Ollama ──")
    try:
        models = [m.model for m in ollama.Client(host=cfg.llm.host).list().models]
        print("Model terpasang:", ", ".join(models) or "(kosong)")
        if cfg.llm.fast_model not in models:
            m = cfg.llm.fast_model
            print(f"⚠️  Model {m} belum ada. Jalankan: ollama pull {m}")
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"❌ Tidak bisa terhubung ke Ollama: {e}")
        print("   Buka aplikasi Ollama, atau jalankan: ollama serve")
        ok = False

    print("\n✅ Semua siap!" if ok else "\n⚠️  Ada yang perlu dibereskan dulu.")
    return ok


def chat(cfg: Config, voice: bool) -> None:
    llm = LLM(cfg)
    adapter = get_adapter() if voice else None
    print(
        f"🤖 {cfg.general.name} siap (model: {cfg.llm.fast_model}). Ketik 'keluar' untuk berhenti."
    )
    while True:
        try:
            text = input("\nKamu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in {"keluar", "exit", "quit"}:
            return
        if not text:
            continue
        print(f"{cfg.general.name}: ", end="", flush=True)
        reply = ""
        try:
            for piece in llm.ask(text):
                reply += piece
                print(piece, end="", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"\n❌ Gagal bicara dengan Ollama: {e}")
            continue
        print()
        if adapter and reply.strip():
            try:
                adapter.say(
                    reply, getattr(getattr(cfg.tts.voices.system, adapter.name), cfg.tts.gender)
                )
            except NotImplementedError as e:
                logger.warning(str(e))
                adapter = None


def run_listen(cfg: Config, tray: bool, config_path: str) -> None:
    from pathlib import Path

    from jarvis.app import Jarvis

    if cfg.ui.dashboard.enabled:
        from jarvis.ui.dashboard import start_dashboard

        start_dashboard(cfg, config_path)
    if tray:
        try:
            from jarvis.app import start_in_thread
            from jarvis.tools.registry import context
            from jarvis.ui.tray import Tray

            holder: dict[str, Jarvis] = {}
            ui = Tray(
                cfg.general.name,
                on_quit=lambda: holder["j"].stop() if "j" in holder else None,
                on_toggle_mute=lambda m: holder["j"].set_mic_muted(m) if "j" in holder else None,
                on_open_config=lambda: context.adapter.open_path(str(Path(config_path).resolve())),
            )

            def ready(j: Jarvis) -> None:
                holder["j"] = j
                j.listeners.append(lambda st: ui.set_state(st.value))
                ui.set_state(j.state.value)

            start_in_thread(lambda: Jarvis(cfg), ready)
            ui.run()  # blocking di thread utama sampai "Keluar"
            if "j" in holder:
                holder["j"].stop()
            return
        except Exception as e:  # noqa: BLE001 — tray tidak tersedia (mis. Linux headless)
            logger.warning(f"System tray tidak bisa dipakai ({e}); lanjut tanpa tray")
    Jarvis(cfg).run()


def main() -> None:
    import multiprocessing

    multiprocessing.freeze_support()  # wajib di app PyInstaller
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("--check", action="store_true", help="cek mic & Ollama")
    ap.add_argument("--text", action="store_true", help="mode teks (default)")
    ap.add_argument("--voice", action="store_true", help="mode teks + jawaban dibacakan")
    ap.add_argument("--listen", action="store_true", help="pipeline suara penuh (frasa pemanggil)")
    ap.add_argument("--no-tray", action="store_true", help="tanpa ikon system tray")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING"])
    args = ap.parse_args()

    try:
        cfg = load_config(args.config)
    except ValidationError as e:
        sys.exit(f"Config tidak valid:\n{e}")

    logger.remove()
    logger.add(sys.stderr, level=args.log_level or cfg.general.log_level)

    if args.check:
        sys.exit(0 if check(cfg) else 1)
    if args.listen:
        run_listen(cfg, tray=cfg.ui.tray and not args.no_tray, config_path=args.config)
        return
    chat(cfg, voice=args.voice)


if __name__ == "__main__":
    main()
