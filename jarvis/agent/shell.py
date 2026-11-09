"""Shell terjaga untuk agen: SEMUA perintah dikonfirmasi pengguna kecuali daftar baca-saja.

Lapisan pengaman (berurutan): panjang & karakter, daftar blokir keras (tak bisa dikonfirmasi),
jaringan diblokir saat `offline_only`, folder kerja harus di `workspace.folders`, env tanpa rahasia,
timeout, keluaran dipotong. Keluaran perintah adalah DATA, bukan instruksi.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

from jarvis import workspace
from jarvis.config import Config

MAX_COMMAND_CHARS = 300

# Diblokir keras: tidak bisa dikonfirmasi karena terlalu merusak / mencuri / naik hak akses.
_HARD_BLOCK = [
    (r"\bsudo\b|\bsu\b\s|\bdoas\b", "naik hak akses (sudo) tidak diizinkan"),
    (r"\brm\b[^|;&]*\s(-\w*r\w*f|-\w*f\w*r|--recursive)\b[^|;&]*(\s/(\s|$)|\s~|\s\*|\$HOME)",
     "hapus massal di folder induk/home diblokir"),
    (r"\bmkfs\b|\bdd\b\s+[^|;&]*\bof=|\bdiskutil\s+(erase|partition)|\bformat\b\s+[a-z]:",
     "perintah disk berbahaya diblokir"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "matikan/restart lewat tool khusus, bukan shell"),
    (r":\(\)\s*\{", "fork bomb diblokir"),
    (r"(curl|wget)[^|;&]*\|\s*(sudo\s+)?(ba|z)?sh\b", "unduh-lalu-jalankan diblokir"),
    (r"\bchmod\b[^|;&]*-R[^|;&]*\s/(\s|$)|\bchown\b[^|;&]*-R[^|;&]*\s/(\s|$)",
     "ubah izin seluruh sistem diblokir"),
    (r"\bcrontab\b|\blaunchctl\b|\bsystemctl\b|\bschtasks\b|\breg\s+(add|delete)\b",
     "mengubah layanan/jadwal sistem diblokir"),
]  # fmt: skip

_NETWORK = re.compile(
    r"\b(curl|wget|ssh|scp|sftp|rsync|nc|ncat|telnet|ftp)\b"
    r"|\bgit\s+(push|pull|fetch|clone)\b|\b(pip3?|uv\s+pip)\s+install\b|\buv\s+(add|sync)\b"
    r"|\b(npm|pnpm|yarn)\s+(install|add|i)\b|\bbrew\b",
    re.I,
)
_META = re.compile(r"[;&|<>`$\n\\]|\$\(")


class ShellError(RuntimeError):
    """Pesan aman untuk dibacakan / dikirim balik ke model."""


def workdir(cfg: Config, cwd: str = "") -> Path:
    rs = workspace.roots(cfg)
    if not rs:
        raise ShellError("Folder kerja belum diatur. Isi workspace.folders di config.yaml")
    base = (rs[0] / cwd).resolve() if cwd and not Path(cwd).is_absolute() else Path(cwd or rs[0])
    base = base.expanduser().resolve()
    if not any(workspace._inside(base, r) for r in rs) or not base.is_dir():
        raise ShellError("Folder kerja perintah harus di dalam folder kerja yang diizinkan")
    return base


def check_command(cfg: Config, command: str) -> None:
    """Lempar ShellError jika perintah tidak boleh dijalankan sama sekali."""
    cmd = command.strip()
    if not cmd:
        raise ShellError("Perintah kosong")
    if len(cmd) > MAX_COMMAND_CHARS:
        raise ShellError(f"Perintah terlalu panjang (maks {MAX_COMMAND_CHARS} karakter)")
    for pat, why in _HARD_BLOCK:
        if re.search(pat, cmd, re.I):
            raise ShellError(f"Diblokir: {why}")
    deny = [d for d in cfg.workspace.deny if d.lower() not in {".git", "node_modules", ".venv"}]
    low = cmd.lower()
    for d in deny:
        if re.search(rf"(^|[\s/\"'=]){re.escape(d.lower())}($|[\s/\"'])", low):
            raise ShellError(f"Diblokir: menyentuh '{d}' yang dilindungi")
    if cfg.general.offline_only and _NETWORK.search(cmd):
        raise ShellError("Diblokir: perintah jaringan tidak boleh saat offline_only aktif")


def is_read_only(cfg: Config, command: str) -> bool:
    """Perintah baca-saja yang boleh jalan tanpa konfirmasi (tanpa pipa/redirect/substitusi)."""
    if not cfg.agent.auto_read_only or _META.search(command):
        return False
    try:
        toks = shlex.split(command)
    except ValueError:
        return False
    if not toks:
        return False
    if toks[0] == "find" and any(t in {"-exec", "-delete", "-ok", "-execdir"} for t in toks):
        return False
    for allowed in cfg.agent.readonly_commands:
        parts = allowed.split()
        if toks[: len(parts)] == parts:
            return _args_inside(cfg, toks[len(parts) :])
    return False


def _args_inside(cfg: Config, args: list[str]) -> bool:
    """Argumen yang terlihat seperti path harus di dalam folder kerja (mis. `ls /` → tanya dulu)."""
    try:
        wd = workdir(cfg)
    except ShellError:
        return False
    for a in args:
        if a.startswith("-") or not re.search(r"[/~.]|^\.\.", a):
            continue  # opsi atau kata biasa (pola grep)
        if a.startswith("~"):
            return False
        p = Path(a)
        real = (p if p.is_absolute() else wd / p).resolve()
        if not workspace._inside(real, wd):
            return False
    return True


def _clean_env() -> dict[str, str]:
    secret = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)
    return {k: v for k, v in os.environ.items() if not secret.search(k)}


def run(cfg: Config, command: str, cwd: str = "") -> str:
    """Jalankan perintah (SUDAH dikonfirmasi pemanggil). Keluaran dipotong dari tengah."""
    check_command(cfg, command)
    wd = workdir(cfg, cwd)
    a = cfg.agent
    try:
        proc = subprocess.run(  # noqa: S602 — shell bebas disengaja; dijaga konfirmasi + pemblokir
            command,
            shell=True,
            cwd=wd,
            env=_clean_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=a.command_timeout_s,
            start_new_session=os.name != "nt",
        )
    except subprocess.TimeoutExpired:
        raise ShellError(f"Perintah dihentikan setelah {a.command_timeout_s} detik") from None
    out = (
        proc.stdout + (("\n" + proc.stderr) if proc.stderr else "")
    ).strip() or "(tanpa keluaran)"
    if len(out) > a.max_output_chars:
        half = a.max_output_chars // 2
        out = (
            out[:half]
            + f"\n... (dipotong {len(out) - a.max_output_chars} karakter) ...\n"
            + out[-half:]
        )
    return f"[exit {proc.returncode}]\n{out}"
