"""Setelan AI milik pengguna: penyedia model bahasa, model, dan kunci API.

Disimpan di berkas terpisah (`<data dir>/ai.json`, izin 0600), bukan di config.yaml, supaya kunci
tidak ikut ter-commit dan bisa diubah dari aplikasi lain (Isla Desk) tanpa menyunting YAML.
Perubahan berlaku seketika pada objek `cfg.llm` yang sedang dipakai; tanpa restart.
Kunci tidak pernah dikembalikan ke pemanggil, hanya status "sudah diisi".
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from loguru import logger
from platformdirs import user_data_dir

from jarvis.config import Config

_lock = threading.Lock()
PUBLIC_FIELDS = ("provider", "api_base", "cloud_fast_model", "cloud_smart_model")


def path() -> Path:
    env = os.environ.get("JARVIS_AI_SETTINGS")
    return Path(env) if env else Path(user_data_dir("jarvis", appauthor=False)) / "ai.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(p)
    try:
        p.chmod(0o600)
    except OSError:  # Windows: izin POSIX tidak berlaku
        pass


def get_key(provider: str) -> str:
    """Kunci untuk `provider`: env JARVIS_API_KEY_<NAMA> / JARVIS_API_KEY, lalu berkas setelan."""
    env = os.environ.get(f"JARVIS_API_KEY_{provider.upper()}") or os.environ.get("JARVIS_API_KEY")
    return (env or _load().get("keys", {}).get(provider, "")).strip()


def apply(cfg: Config) -> None:
    """Timpa `cfg.llm` dengan setelan tersimpan (dipanggil saat load_config)."""
    data = _load()
    if not data:
        return
    for name in PUBLIC_FIELDS:
        if name in data:
            setattr(cfg.llm, name, data[name])
    cfg.llm.allow_cloud = bool(data.get("allow_cloud", cfg.llm.allow_cloud))
    if cfg.llm.provider != "ollama" and not cfg.llm.allow_cloud:
        logger.warning("[ai] penyedia online dipilih tanpa izin (allow_cloud); kembali ke Ollama")
        cfg.llm.provider = "ollama"


def view(cfg: Config) -> dict[str, Any]:
    """Keadaan sekarang untuk UI. Tidak memuat kunci."""
    from jarvis.brain.providers import PRESETS

    c = cfg.llm
    return {
        "provider": c.provider,
        "providers": list(PRESETS),
        "api_base": c.api_base,
        "fast_model": c.active_fast_model,
        "smart_model": c.active_smart_model,
        "local_models": {"fast": c.fast_model, "smart": c.smart_model},
        "allow_cloud": c.allow_cloud,
        "has_key": bool(get_key(c.provider)) if c.provider != "ollama" else False,
        "keys_set": [p for p in PRESETS if p != "ollama" and get_key(p)],
        "offline_only": cfg.general.offline_only,
    }


def update(
    cfg: Config,
    provider: str,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
    fast_model: str | None = None,
    smart_model: str | None = None,
) -> dict[str, Any]:
    """Ganti penyedia (dan kunci/model) saat Jarvis berjalan, lalu simpan.

    Memilih penyedia online = izin eksplisit pemilik untuk mengirim pertanyaan ke sana. Pindah ke
    online membongkar model Ollama dari RAM. Lempar ValueError bila isian tidak sah.
    """
    from jarvis.brain import providers

    if provider not in providers.PRESETS:
        raise ValueError(f"Penyedia '{provider}' tidak dikenal")
    cloud = provider != "ollama"
    with _lock:
        data = _load()
        if api_key is not None and api_key.strip():
            data.setdefault("keys", {})[provider] = api_key.strip()
        if cloud:
            base = (api_base if api_base is not None else data.get("api_base", "")).strip()
            if provider == "custom" and not base:
                raise ValueError("Penyedia custom butuh api_base")
            if base and not base.lower().startswith(("https://", "http://")):
                raise ValueError("api_base harus diawali https:// atau http://")
            fast = fast_model if fast_model is not None else data.get("cloud_fast_model", "")
            if not fast.strip():
                raise ValueError("Isi nama model (fast_model) untuk penyedia online")
            data.update(
                provider=provider, api_base=base, allow_cloud=True,
                cloud_fast_model=fast.strip(),
                cloud_smart_model=(
                    smart_model if smart_model is not None else data.get("cloud_smart_model", "")
                ).strip(),
            )  # fmt: skip
            if not get_key(provider) and not data.get("keys", {}).get(provider):
                raise ValueError("Kunci API belum diisi")
        else:
            data.update(provider="ollama", allow_cloud=False)
        _save(data)
    for name in PUBLIC_FIELDS:
        if name in data:
            setattr(cfg.llm, name, data[name])
    cfg.llm.allow_cloud = bool(data.get("allow_cloud"))
    if cloud:
        freed = providers.unload_local_models(cfg)
        logger.info(f"[ai] penyedia: {provider}; {freed} model lokal dibongkar dari RAM")
    else:
        logger.info("[ai] penyedia: Ollama (lokal)")
    return view(cfg)


def test(cfg: Config) -> str:
    """Pertanyaan singkat ke penyedia aktif; mengembalikan jawabannya atau melempar galat aman."""
    from jarvis.brain import providers

    client = providers.client_for(cfg)
    resp = client.chat(
        model=cfg.llm.active_fast_model,
        messages=[{"role": "user", "content": "Balas satu kata: siap"}],
        options={"num_predict": 16, "temperature": 0.0},
    )
    return (resp.message.content or "").strip()[:80]
