"""Plugin: tool buatan pengguna. Taruh file .py di folder plugins/ dan restart Jarvis.

Plugin = kode Python biasa yang dijalankan dengan hak penuh pengguna, jadi pasang hanya plugin yang
kamu percaya. Plugin memakai dekorator yang sama dengan tool bawaan, jadi validasi argumen dan
konfirmasi suara untuk risk `high` tetap berlaku. Gagal dimuat = dilewati, Jarvis tetap jalan.

Kata kunci pemicu (supaya skema tool dikirim ke LLM) bisa diatur lewat `KEYWORDS = [...]` di
plugin; tanpa itu dipakai potongan nama tool.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from loguru import logger
from platformdirs import user_data_dir

from jarvis.config import Config
from jarvis.tools.registry import registry

PLUGIN_CATEGORY = "plugin"
PLUGIN_HINTS: dict[tuple[str, ...], tuple[str, ...]] = {}
LOADED: list[str] = []


def plugins_dir(cfg: Config) -> Path:
    p = cfg.tools.plugins
    return Path(p.dir).expanduser() if p.dir else Path(user_data_dir("jarvis")) / "plugins"


def _candidates(folder: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for item in sorted(folder.iterdir()):
        if item.name.startswith(("_", ".")):
            continue
        if item.is_file() and item.suffix == ".py":
            found.append((item.stem, item))
        elif item.is_dir() and (item / "__init__.py").exists():
            found.append((item.name, item / "__init__.py"))
    return found


def _load_one(name: str, path: Path) -> list[str]:
    before = set(registry.names())
    spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError("bukan modul Python yang valid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        for n in set(registry.names()) - before:  # batalkan tool yang sempat terdaftar
            registry.unregister(n)
        raise
    new = sorted(set(registry.names()) - before)
    keywords = tuple(getattr(module, "KEYWORDS", ()) or ())
    if not keywords:
        keywords = tuple(part for n in new for part in n.split("_") if len(part) > 2)
    for n in new:
        registry.recategorize(n, PLUGIN_CATEGORY)
    if new and keywords:
        PLUGIN_HINTS[keywords] = tuple(new)
    return new


def load_plugins(cfg: Config) -> list[str]:
    """Muat semua plugin yang diizinkan; kembalikan nama tool yang berhasil ditambahkan."""
    conf = cfg.tools.plugins
    if not conf.enabled:
        return []
    folder = plugins_dir(cfg)
    if not folder.is_dir():
        return []
    added: list[str] = []
    for name, path in _candidates(folder):
        if name in LOADED:
            continue
        if conf.allowed and name not in conf.allowed:
            logger.debug(f"Plugin '{name}' tidak ada di tools.plugins.allowed, dilewati")
            continue
        try:
            tools = _load_one(name, path)
        except Exception as e:  # noqa: BLE001 — plugin rusak tidak boleh menjatuhkan Jarvis
            logger.warning(f"Plugin '{name}' gagal dimuat: {type(e).__name__}: {e}")
            continue
        LOADED.append(name)
        added += tools
        logger.info(f"Plugin '{name}' dimuat: {', '.join(tools) or '(tanpa tool)'}")
    return added
