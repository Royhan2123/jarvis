"""Kontrak adapter OS. Semua kode per-OS lewat sini."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    @abstractmethod
    def say(self, text: str, gender: str) -> None:
        """Bacakan teks dengan suara bawaan OS (fallback TTS Fase 0)."""
