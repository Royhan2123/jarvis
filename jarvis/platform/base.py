"""Kontrak adapter OS. Semua kode per-OS lewat sini."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal


class PlatformAdapter(ABC):
    name: Literal["macos", "windows", "linux"]

    @abstractmethod
    def say(self, text: str, voice: str | None = None) -> None:
        """Bacakan teks dengan suara bawaan OS (fallback TTS). Blocking sampai selesai."""

    @abstractmethod
    def stop_say(self) -> None:
        """Hentikan ucapan yang sedang berjalan (jika ada)."""
