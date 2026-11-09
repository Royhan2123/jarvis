from __future__ import annotations

import zlib

import numpy as np
import pytest

from jarvis.brain.rag import DocIndex, chunk_text
from jarvis.config import RagConfig


def fake_embed(texts: list[str]) -> np.ndarray:
    """Bag-of-words hashing: teks dengan kata sama → vektor mirip. Tanpa model sungguhan."""
    out = np.zeros((len(texts), 64), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in t.lower().split():
            out[i, zlib.crc32(w.strip(".,?").encode()) % 64] += 1
    return out


@pytest.fixture
def setup(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sewa.txt").write_text(
        "Kontrak sewa rumah berlaku dua tahun. Biaya sewa bulanan lima juta."
    )
    (docs / "resep.md").write_text("Resep nasi goreng: panaskan minyak, masukkan bawang dan nasi.")
    cfg = RagConfig(folders=[str(docs)])
    idx = DocIndex(cfg, fake_embed, tmp_path / "rag.db")
    return idx, docs, cfg


def test_chunking_respects_size() -> None:
    chunks = chunk_text("Kalimat satu. " * 200, 200, 20)
    assert chunks and all(len(c) <= 220 for c in chunks)
    assert chunk_text("   ", 200, 20) == []
    assert all(len(c) <= 200 for c in chunk_text("x" * 1000, 200, 20))


def test_index_and_search(setup) -> None:
    idx, _, _ = setup
    assert idx.index()["added"] == 2
    hit = idx.search("biaya sewa rumah")[0]
    assert hit.path.endswith("sewa.txt")
    assert idx.search("resep nasi goreng")[0].path.endswith("resep.md")


def test_incremental_update_and_removal(setup) -> None:
    idx, docs, _ = setup
    idx.index()
    assert idx.index() == {"added": 0, "skipped": 2, "removed": 0, "failed": 0, "chunks": 0}
    (docs / "resep.md").unlink()
    (docs / "baru.txt").write_text("Catatan rapat proyek hari Senin.")
    s = idx.index()
    assert (s["added"], s["removed"], s["skipped"]) == (1, 1, 1)
    assert idx.count()[0] == 2


def test_ignores_other_extensions_and_outside_symlinks(setup, tmp_path) -> None:
    idx, docs, _ = setup
    (docs / "rahasia.exe").write_text("x")
    outside = tmp_path / "luar.txt"
    outside.write_text("jangan dibaca")
    (docs / "link.txt").symlink_to(outside)
    idx.index()
    paths = {r[0] for r in idx._db.execute("SELECT path FROM docs")}
    assert not any(p.endswith(("rahasia.exe", "luar.txt", "link.txt")) for p in paths)


def test_broken_file_does_not_stop_indexing(setup) -> None:
    idx, docs, _ = setup
    (docs / "rusak.pdf").write_bytes(b"bukan pdf")
    s = idx.index()
    assert s["failed"] == 1 and s["added"] == 2


def test_tool_requires_folders(adapter) -> None:
    from jarvis.tools.registry import ToolError, registry

    with pytest.raises(ToolError, match="rag.folders"):
        registry.call("search_docs", {"query": "kontrak"})
