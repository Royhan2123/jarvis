"""Kebijakan izin agen: aksi mana yang harus ditanyakan dulu ke pengguna.

Dipakai bersama oleh perintah suara dan dashboard. Perubahan berlaku seketika pada `cfg.agent`
(objek config yang sama dengan yang dipakai agen) dan hanya sampai Jarvis dimatikan, kecuali
disimpan permanen ke config.yaml. Blokir keras shell dan file rahasia tidak ikut longgar.
"""

from __future__ import annotations

import re
from pathlib import Path

from jarvis.config import Config

ACTIONS: tuple[str, ...] = ("edit_file", "write_file", "run_command")

LABELS = {
    "edit_file": "mengubah file",
    "write_file": "membuat file baru",
    "run_command": "menjalankan perintah",
}

# Kata ucapan -> aksi. Kunci terpanjang menang ("membuat file baru" sebelum "file").
SPOKEN = {
    "ubah file": "edit_file",
    "mengubah file": "edit_file",
    "edit file": "edit_file",
    "mengedit file": "edit_file",
    "perubahan file": "edit_file",
    "buat file": "write_file",
    "membuat file": "write_file",
    "file baru": "write_file",
    "buat file baru": "write_file",
    "membuat file baru": "write_file",
    "perintah": "run_command",
    "jalankan perintah": "run_command",
    "menjalankan perintah": "run_command",
    "perintah shell": "run_command",
    "semua": "all",
    "semuanya": "all",
    "semua aksi": "all",
}


def resolve_action(spoken: str) -> str | None:
    """Ucapan ("mengubah file") -> aksi (`edit_file`) atau "all"; None bila tak dikenali."""
    spoken = spoken.strip()
    if spoken in SPOKEN:
        return SPOKEN[spoken]
    for key in sorted(SPOKEN, key=len, reverse=True):
        if key in spoken:
            return SPOKEN[key]
    return None


def targets(action: str) -> tuple[str, ...]:
    """ "all" -> semua aksi; selain itu satu aksi. Aksi asing -> ValueError."""
    if action == "all":
        return ACTIONS
    if action not in ACTIONS:
        raise ValueError(f"aksi tidak dikenal: {action}")
    return (action,)


def label(action: str) -> str:
    return (
        "semua aksi (ubah file, buat file, perintah shell)" if action == "all" else LABELS[action]
    )


def set_asking(cfg: Config, action: str, ask: bool) -> list[str]:
    """Atur apakah `action` ditanyakan dulu; mengembalikan `confirm_actions` baru (berurutan)."""
    wanted = set(targets(action))
    current = set(cfg.agent.confirm_actions)
    current = current | wanted if ask else current - wanted
    cfg.agent.confirm_actions = [a for a in ACTIONS if a in current]  # type: ignore[assignment]
    return list(cfg.agent.confirm_actions)


def summary(actions: list[str]) -> str:
    """Kalimat keadaan sekarang untuk dibacakan."""
    asked = [LABELS[a] for a in actions]
    free = [LABELS[a] for a in ACTIONS if a not in actions]
    if not free:
        return "Saya tetap bertanya sebelum melakukan apa pun."
    if not asked:
        return "Saya tidak bertanya lagi untuk aksi apa pun; blokir keras tetap berlaku."
    return f"Saya bertanya dulu sebelum {', '.join(asked)}."


_LINE = re.compile(r"^(?P<head>\s*confirm_actions\s*:\s*)\[[^\]\n]*\](?P<tail>.*)$", re.M)


def persist(path: Path, actions: list[str]) -> bool:
    """Tulis `confirm_actions` ke config.yaml dengan mengganti barisnya (komentar tetap utuh),
    setelah mencadangkan ke .bak. False bila berkasnya tak ada atau barisnya tak ditemukan."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    rendered = "[" + ", ".join(f'"{a}"' for a in actions) + "]"
    new, n = _LINE.subn(lambda m: f"{m['head']}{rendered}{m['tail']}", text, count=1)
    if n == 0:
        return False
    path.with_suffix(".yaml.bak").write_text(text, encoding="utf-8")
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(new, encoding="utf-8")
    tmp.replace(path)
    return True
