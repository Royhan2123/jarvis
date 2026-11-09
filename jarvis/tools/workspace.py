"""Tool folder kerja: lihat isi folder, ganti teks di file, buat file baru (konfirmasi suara)."""

from __future__ import annotations

from jarvis import workspace
from jarvis.tools.registry import ToolError, context, tool


def _wrap(fn, *args):  # noqa: ANN001, ANN002, ANN202
    try:
        return fn(context.cfg, *args)
    except workspace.WorkspaceError as e:
        raise ToolError(str(e)) from e


@tool(
    name="list_files",
    description="Menyebutkan isi folder kerja proyek pengguna",
    risk="low",
    category="workspace",
)
def list_files(folder: str = "") -> str:
    return _wrap(workspace.list_dir, folder)


@tool(
    name="replace_in_file",
    description=(
        "Mengubah kode: mengganti teks lama (harus persis ada satu kali di file) dengan teks baru. "
        "Isi file sudah diberikan di konteks"
    ),
    risk="high",
    category="workspace",
)
def replace_in_file(path: str, old: str, new: str) -> str:
    return _wrap(workspace.replace_in_file, path, old, new)


@tool(
    name="create_file",
    description="Membuat file baru di folder kerja, tanpa menimpa file yang sudah ada",
    risk="high",
    category="workspace",
)
def create_file(path: str, content: str) -> str:
    return _wrap(workspace.create_file, path, content)
