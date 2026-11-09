"""CLI agen (mode teks): `uv run python -m jarvis.agent "perbaiki bug di toko.py"`."""

from __future__ import annotations

import argparse

from jarvis.agent.loop import Agent, AgentError
from jarvis.config import load_config


def _confirm(what: str) -> bool:
    return input(f"\n⚠️  Jarvis ingin {what}\n   Izinkan? [y/N] ").strip().lower() in {"y", "ya"}


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis.agent")
    ap.add_argument("task")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    try:
        print("\n" + Agent(cfg, _confirm).run(args.task))
    except AgentError as e:
        print(f"❌ {e}")


if __name__ == "__main__":
    main()
