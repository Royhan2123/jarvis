"""Kontrak adapter OS. Semua kode per-OS lewat sini."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

MediaAction = Literal["play_pause", "next", "prev"]


class PlatformError(RuntimeError):
    """Aksi OS gagal. Pesan dalam bahasa Indonesia, aman untuk dibacakan."""


class AppNotFound(PlatformError):
    pass


class PlatformAdapter(ABC):
    name: Literal["macos", "windows", "linux"]

    # ── Suara (TTS fallback) ──
    @abstractmethod
    def say(self, text: str, voice: str | None = None) -> None:
        """Bacakan teks dengan suara bawaan OS. Blocking sampai selesai."""

    @abstractmethod
    def stop_say(self) -> None:
        """Hentikan ucapan yang sedang berjalan (jika ada)."""

    # ── Aplikasi ──
    @abstractmethod
    def open_app(self, name: str) -> None:
        """Buka aplikasi terpasang. Lempar AppNotFound jika tidak ada."""

    @abstractmethod
    def close_app(self, name: str) -> None:
        """Tutup aplikasi dengan sopan. Lempar AppNotFound jika tidak sedang jalan."""

    # ── Audio ──
    @abstractmethod
    def set_volume(self, percent: int) -> None:
        """percent sudah divalidasi 0–100."""

    @abstractmethod
    def mute(self, on: bool) -> None: ...

    @abstractmethod
    def media(self, action: MediaAction) -> None: ...

    # ── Sistem ──
    @abstractmethod
    def lock_screen(self) -> None: ...

    @abstractmethod
    def shutdown(self) -> None:
        """Matikan komputer. HANYA boleh dipanggil lewat tool risk=high yang sudah dikonfirmasi."""

    @abstractmethod
    def restart(self) -> None:
        """Restart komputer. HANYA lewat tool risk=high yang sudah dikonfirmasi."""

    @abstractmethod
    def open_path(self, path: str) -> None:
        """Buka file/folder dengan aplikasi default (mis. config.yaml)."""

    # ── Layar, keyboard, notifikasi ──
    @abstractmethod
    def screenshot(self) -> bytes:
        """Tangkap layar utama sebagai PNG."""

    @abstractmethod
    def type_text(self, text: str) -> None:
        """Ketik teks ke jendela yang sedang aktif. `text` sudah dibersihkan oleh tool."""

    @abstractmethod
    def notify(self, title: str, body: str) -> None: ...
