"""RAG dokumen pribadi: potong dokumen → embedding lokal (Ollama) → SQLite → cari kemiripan.

Vektor disimpan sebagai float32 di SQLite dan dicari dengan numpy (ratusan ribu potongan masih
cepat; tidak perlu vector DB eksternal). Hanya folder di `rag.folders` yang dibaca. Isi dokumen
adalah DATA: hasil pencarian tidak boleh diperlakukan sebagai perintah.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger

from jarvis.brain.memory import data_dir
from jarvis.config import Config, RagConfig

Embedder = Callable[[list[str]], np.ndarray]

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (path TEXT PRIMARY KEY, mtime REAL, size INTEGER, model TEXT);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, path TEXT NOT NULL REFERENCES docs(path) ON DELETE CASCADE,
  pos INTEGER, text TEXT, vec BLOB
);
CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
"""


@dataclass(frozen=True)
class Hit:
    path: str
    text: str
    score: float


def ollama_embedder(cfg: Config) -> Embedder:
    from jarvis.brain import providers

    client = providers.local_client(cfg)  # embedding selalu lokal

    def embed(texts: list[str]) -> np.ndarray:
        out = client.embed(model=cfg.rag.embed_model, input=texts)
        return np.asarray(out.embeddings, dtype=np.float32)

    return embed


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Potong per paragraf/kalimat ke potongan ≤ size karakter dengan sedikit tumpang tindih."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    pieces = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?])\s+", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        while len(p) > size:  # paragraf tanpa titik: potong paksa
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(p[:size])
            p = p[size - overlap :]
        if cur and len(cur) + len(p) + 1 > size:
            chunks.append(cur)
            cur = cur[-overlap:] + " " + p if overlap else p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def read_document(path: Path, max_bytes: int) -> str:
    if path.stat().st_size > max_bytes:
        raise ValueError("file terlalu besar")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


class DocIndex:
    def __init__(self, cfg: RagConfig, embedder: Embedder, path: Path | str | None = None) -> None:
        self.cfg, self.embed = cfg, embedder
        self.path = Path(path) if path else data_dir() / "rag.db"
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def _files(self) -> list[Path]:
        exts = {e.lower() for e in self.cfg.extensions}
        found: list[Path] = []
        for folder in self.cfg.folders:
            root = Path(folder).expanduser().resolve()
            if not root.is_dir():
                logger.warning(f"Folder RAG tidak ada: {root}")
                continue
            for f in sorted(root.rglob("*")):
                real = f.resolve()  # symlink keluar dari folder diabaikan
                if f.is_file() and f.suffix.lower() in exts and real.is_relative_to(root):
                    found.append(real)
        return found

    def index(self) -> dict[str, int]:
        """Indeks ulang file yang baru/berubah, hapus yang sudah hilang. Mengembalikan ringkasan."""
        stats = {"added": 0, "skipped": 0, "removed": 0, "failed": 0, "chunks": 0}
        files = self._files()
        known = {r[0]: r for r in self._db.execute("SELECT path, mtime, size, model FROM docs")}
        for f in files:
            st = f.stat()
            old = known.get(str(f))
            if (
                old
                and old[1] == st.st_mtime
                and old[2] == st.st_size
                and old[3] == self.cfg.embed_model
            ):
                stats["skipped"] += 1
                continue
            try:
                chunks = chunk_text(
                    read_document(f, self.cfg.max_file_mb * 1_000_000),
                    self.cfg.chunk_chars,
                    self.cfg.chunk_overlap,
                )
                vecs = self._embed_all(chunks)
            except Exception as e:  # noqa: BLE001 — satu file rusak tidak boleh menghentikan semua
                logger.warning(f"Gagal mengindeks {f.name}: {type(e).__name__}: {e}")
                stats["failed"] += 1
                continue
            with self._db:
                self._db.execute("DELETE FROM docs WHERE path = ?", (str(f),))
                self._db.execute(
                    "INSERT INTO docs VALUES (?,?,?,?)",
                    (str(f), st.st_mtime, st.st_size, self.cfg.embed_model),
                )
                self._db.executemany(
                    "INSERT INTO chunks (path, pos, text, vec) VALUES (?,?,?,?)",
                    [
                        (str(f), i, t, v.tobytes())
                        for i, (t, v) in enumerate(zip(chunks, vecs, strict=True))
                    ],
                )
            stats["added"] += 1
            stats["chunks"] += len(chunks)
        live = {str(f) for f in files}
        for path in set(known) - live:
            with self._db:
                self._db.execute("DELETE FROM docs WHERE path = ?", (path,))
            stats["removed"] += 1
        return stats

    def _embed_all(self, chunks: list[str], batch: int = 16) -> np.ndarray:
        if not chunks:
            return np.zeros((0, 1), dtype=np.float32)
        parts = [self.embed(chunks[i : i + batch]) for i in range(0, len(chunks), batch)]
        return _normalize(np.vstack(parts))

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        rows = self._db.execute("SELECT path, text, vec FROM chunks").fetchall()
        if not rows or not query.strip():
            return []
        q = _normalize(self.embed([query]))[0]
        mat = np.vstack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
        scores = mat @ q
        top = np.argsort(-scores)[: k or self.cfg.top_k]
        return [Hit(rows[i][0], rows[i][1], float(scores[i])) for i in top]

    def count(self) -> tuple[int, int]:
        d = self._db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        c = self._db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return d, c


def _normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.maximum(n, 1e-9)
