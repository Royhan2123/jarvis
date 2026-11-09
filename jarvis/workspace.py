"""Akses file terbatas untuk "baca / perbaiki kode".

Aturan keamanan: hanya folder di `workspace.folders` (path di-resolve, symlink keluar ditolak);
nama sensitif (.env, .ssh, id_rsa, ...) tidak pernah disentuh; hanya ekstensi teks yang diizinkan;
ubah file = risk high (konfirmasi suara) + cadangan `<file>.jarvis-bak`; isi file adalah DATA.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from jarvis.config import Config

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "build", "dist", ".idea"}
MAX_EDIT_CHARS = 4000


class WorkspaceError(RuntimeError):
    """Pesan aman untuk dibacakan."""


def roots(cfg: Config) -> list[Path]:
    return [
        Path(f).expanduser().resolve()
        for f in cfg.workspace.folders
        if Path(f).expanduser().is_dir()
    ]


def is_denied(cfg: Config, path: Path) -> bool:
    deny = {d.lower() for d in cfg.workspace.deny}
    return any(part.lower() in deny for part in path.parts) or path.name.lower().startswith(".env")


def _inside(path: Path, base: Path) -> bool:
    return path == base or base in path.parents


def _check(cfg: Config, path: Path, must_exist: bool = True) -> Path:
    real = path.resolve()
    if not any(_inside(real, r) for r in roots(cfg)):
        raise WorkspaceError("File itu di luar folder kerja yang diizinkan")
    if is_denied(cfg, real):
        raise WorkspaceError("File itu termasuk yang dilindungi, saya tidak menyentuhnya")
    if real.suffix.lower() not in {e.lower() for e in cfg.workspace.extensions}:
        raise WorkspaceError(f"Jenis file {real.suffix or '(tanpa ekstensi)'} tidak diizinkan")
    if must_exist and not real.is_file():
        raise WorkspaceError(f"File {real.name} tidak ada")
    if must_exist and real.stat().st_size > cfg.workspace.max_file_kb * 1024:
        raise WorkspaceError("File terlalu besar")
    return real


def find_file(cfg: Config, ref: str) -> Path:
    """Cocokkan nama/path relatif/absolut ke satu file di folder kerja."""
    ref = ref.strip().strip("\"'")
    if not roots(cfg):
        raise WorkspaceError("Folder kerja belum diatur. Isi workspace.folders di config.yaml")
    p = Path(ref).expanduser()
    if p.is_absolute():
        return _check(cfg, p)
    matches: list[Path] = []
    for root in roots(cfg):
        direct = root / ref
        if direct.is_file():
            matches.append(direct)
            continue
        for f in root.rglob(Path(ref).name):
            if SKIP_DIRS.isdisjoint(f.relative_to(root).parts) and f.is_file():
                if str(f).endswith(ref):
                    matches.append(f)
            if len(matches) > 20:
                break
    matches = sorted({m.resolve() for m in matches})
    if not matches:
        raise WorkspaceError(f"File {ref} tidak ditemukan di folder kerja")
    if len(matches) > 1:
        raise WorkspaceError(
            f"Ada {len(matches)} file bernama {Path(ref).name}, sebutkan folder-nya"
        )
    return _check(cfg, matches[0])


def list_dir(cfg: Config, ref: str = "") -> str:
    rs = roots(cfg)
    if not rs:
        raise WorkspaceError("Folder kerja belum diatur. Isi workspace.folders di config.yaml")
    base = rs[0] if not ref else (rs[0] / ref)
    real = base.resolve()
    if not any(_inside(real, r) for r in rs) or not real.is_dir() or is_denied(cfg, real):
        raise WorkspaceError("Folder itu tidak tersedia")
    names = [
        n.name + ("/" if n.is_dir() else "")
        for n in sorted(real.iterdir())
        if n.name not in SKIP_DIRS and not is_denied(cfg, n) and not n.name.startswith(".")
    ]
    if not names:
        return "Folder kosong"
    shown = names[:25]
    more = f", dan {len(names) - 25} lainnya" if len(names) > 25 else ""
    return f"Isi {real.name}: " + ", ".join(shown) + more


def _spoken_name(text: str) -> str:
    """'app titik py' → 'app.py' (Whisper kadang menulis ejaan, bukan titik)."""
    return re.sub(r"\s+(?:titik|dot)\s+", ".", text, flags=re.I)


def mentioned_files(cfg: Config, text: str) -> list[Path]:
    """File di folder kerja yang disebut dalam ucapan (hanya yang cocok unik)."""
    if not roots(cfg):
        return []
    exts = "|".join(re.escape(e.lstrip(".")) for e in cfg.workspace.extensions)
    found: list[Path] = []
    for m in re.finditer(rf"[\w./-]+\.(?:{exts})\b", _spoken_name(text), re.I):
        try:
            p = find_file(cfg, m.group())
        except WorkspaceError:
            continue
        if p not in found:
            found.append(p)
    return found[:2]


def file_context(cfg: Config, text: str) -> str:
    """Potongan file yang disebut (diberi nomor baris) untuk dibaca LLM; "" jika tidak ada."""
    files = mentioned_files(cfg, text)
    if not files:
        return ""
    limit = cfg.workspace.context_chars // len(files)
    m = re.search(r"baris\s+(\d+)(?:\s*(?:sampai|-|hingga)\s*(\d+))?", text, re.I)
    parts: list[str] = []
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(int(m.group(1)) - 1, 0) if m else 0
        chunk, used = [], 0
        for i in range(start, len(lines)):
            row = f"{i + 1}: {lines[i]}"
            if used + len(row) > limit or (m and m.group(2) and i + 1 > int(m.group(2))):
                break
            chunk.append(row)
            used += len(row) + 1
        tail = (
            ""
            if start + len(chunk) >= len(lines)
            else f"\n... (terpotong, total {len(lines)} baris)"
        )
        parts.append(f"=== {f.name} ===\n" + "\n".join(chunk) + tail)
    header = (
        "Kode proyek pengguna (nomor baris hanya penanda, BUKAN bagian kode; saat memakai "
        "replace_in_file, salin teks lama persis tanpa nomor baris):\n"
    )
    return header + "\n".join(parts)


def replace_in_file(cfg: Config, ref: str, old: str, new: str) -> str:
    if not old or len(old) > MAX_EDIT_CHARS or len(new) > MAX_EDIT_CHARS:
        raise WorkspaceError("Teks yang diganti kosong atau terlalu panjang")
    path = find_file(cfg, ref)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        raise WorkspaceError("Teks yang mau diganti tidak ditemukan persis di file itu")
    if count > 1:
        raise WorkspaceError(f"Teks itu muncul {count} kali; sebutkan bagian yang lebih spesifik")
    shutil.copy2(path, path.with_name(path.name + ".jarvis-bak"))
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"File {path.name} sudah diubah, cadangannya {path.name}.jarvis-bak"


def create_file(cfg: Config, ref: str, content: str) -> str:
    if len(content) > 20_000:
        raise WorkspaceError("Isi file terlalu panjang")
    rs = roots(cfg)
    if not rs:
        raise WorkspaceError("Folder kerja belum diatur. Isi workspace.folders di config.yaml")
    target = Path(ref).expanduser()
    path = _check(cfg, target if target.is_absolute() else rs[0] / ref, must_exist=False)
    if path.exists():
        raise WorkspaceError(f"File {path.name} sudah ada; gunakan ganti teks, bukan buat baru")
    if not path.parent.is_dir():
        raise WorkspaceError("Folder tujuan belum ada")
    path.write_text(content, encoding="utf-8")
    return f"File {path.name} sudah dibuat"
