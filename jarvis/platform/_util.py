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


def run_bytes(cmd: list[str], timeout: float = 15.0) -> bytes:
    """Seperti run() tetapi mengembalikan stdout mentah (mis. PNG dari grim)."""
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as e:
        raise PlatformError(f"Perintah '{cmd[0]}' tidak ditemukan di komputer ini") from e
    except subprocess.TimeoutExpired as e:
        raise PlatformError(f"Perintah '{cmd[0]}' terlalu lama merespons") from e
    if res.returncode != 0:
        raise PlatformError(res.stderr.decode(errors="ignore").strip() or f"'{cmd[0]}' gagal")
    return res.stdout


def grab_screen_png() -> bytes:
    """Screenshot monitor utama lewat mss (macOS, Windows, Linux X11). Return PNG."""
    import mss
    import mss.tools

    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        png = mss.tools.to_png(shot.rgb, shot.size)
    return png


def is_blank(png: bytes) -> bool:
    """True jika gambar hitam/kosong (macOS tanpa izin Screen Recording menghasilkan ini)."""
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(png)).convert("L").resize((64, 36))
    return img.getextrema()[1] < 8


def type_via_pynput(text: str, paste_modifier: str) -> None:
    """Ketik lewat pynput; teks panjang/berisi emoji lewat clipboard + paste (lebih andal)."""
    import pyperclip
    from pynput.keyboard import Controller, Key

    kb = Controller()
    if len(text) > 200 or any(ord(c) > 0xFFFF for c in text):
        old = pyperclip.paste()
        pyperclip.copy(text)
        mod = Key.cmd if paste_modifier == "cmd" else Key.ctrl
        with kb.pressed(mod):
            kb.tap("v")
        import time

        time.sleep(0.3)
        pyperclip.copy(old)
    else:
        kb.type(text)
