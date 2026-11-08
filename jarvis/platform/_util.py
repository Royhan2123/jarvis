"""Helper bersama adapter. Tanpa shell: selalu list argumen."""

from __future__ import annotations

import getpass
import subprocess

from jarvis.platform.base import AppNotFound, PlatformError


def run(cmd: list[str], timeout: float = 10.0) -> str:
    """Jalankan perintah (tanpa shell). Gagal → PlatformError dengan pesan jelas."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as e:
        raise PlatformError(f"Perintah '{cmd[0]}' tidak ditemukan di komputer ini") from e
    except subprocess.TimeoutExpired as e:
        raise PlatformError(f"Perintah '{cmd[0]}' terlalu lama merespons") from e
    if res.returncode != 0:
        raise PlatformError(res.stderr.strip() or f"Perintah '{cmd[0]}' gagal")
    return res.stdout.strip()


def terminate_user_processes(name: str) -> int:
    """Tutup proses milik user saat ini yang namanya cocok (nama persis, tanpa huruf besar/kecil).

    Return jumlah proses yang dihentikan; AppNotFound jika tidak ada.
    """
    import psutil

    want = name.lower().removesuffix(".exe")
    me = getpass.getuser()
    count = 0
    for proc in psutil.process_iter(["name", "username"]):
        try:
            pname = (proc.info["name"] or "").lower().removesuffix(".exe")
            if pname == want and proc.info["username"].split("\\")[-1] == me:
                proc.terminate()
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue
    if count == 0:
        raise AppNotFound(f"{name} tidak sedang berjalan")
    return count
