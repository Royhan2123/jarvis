"""CLI uji manual tool lewat registry (bukan shell bebas).

uv run python -m jarvis.tools list
uv run python -m jarvis.tools call set_volume percent=30
uv run python -m jarvis.tools call close_app name=Spotify --yes
"""

from __future__ import annotations

import argparse
import json
import sys

from loguru import logger

from jarvis.config import load_config
from jarvis.tools.registry import ConfirmationRequired, ToolError, context, load_tools, registry


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis.tools")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("call")
    c.add_argument("name")
    c.add_argument("args", nargs="*", help="kunci=nilai (nilai bisa JSON: on=true percent=30)")
    c.add_argument("--yes", action="store_true", help="setuju untuk tool berisiko tinggi")
    a = ap.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    cfg = load_config(a.config)
    context.configure(None, cfg)
    load_tools(cfg)

    if a.cmd == "list":
        for n in registry.names():
            spec = registry.get(n)
            print(f"{n:<14} [{spec.risk.value:<6}] {spec.description}")
        return
    args: dict = {}
    for kv in a.args:
        k, _, v = kv.partition("=")
        try:
            args[k] = json.loads(v)
        except json.JSONDecodeError:
            args[k] = v
    try:
        print(registry.call(a.name, args, confirmed=a.yes))
    except ConfirmationRequired as e:
        sys.exit(f"{e}. Ulangi dengan --yes jika yakin.")
    except ToolError as e:
        sys.exit(f"❌ {e}")


if __name__ == "__main__":
    main()
