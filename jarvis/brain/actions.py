"""Eksekusi intent/tool + alur konfirmasi untuk tool berisiko tinggi."""

from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from jarvis.brain.rules import Intent
from jarvis.tools.registry import ConfirmationRequired, ToolError, registry

CONFIRM_TEXT = {
    "shutdown": "mematikan komputer",
    "restart": "merestart komputer",
}


def _confirm_text(intent: Intent) -> str:
    """Kalimat konfirmasi yang menyebut dengan jelas apa yang akan dilakukan."""
    a = intent.args
    if intent.tool == "replace_in_file":
        return f"mengubah file {str(a.get('path', '?'))[-40:]}, cadangannya disimpan"
    if intent.tool == "create_file":
        return f"membuat file baru {str(a.get('path', '?'))[-40:]}"
    return CONFIRM_TEXT.get(intent.tool, f"menjalankan {intent.tool}")


class ActionRunner:
    """Menjalankan intent satu per satu. Tool `high` ditahan di `pending` sampai dikonfirmasi."""

    def __init__(
        self,
        local: dict[str, Callable[[dict], str]] | None = None,
        on_error: Callable[[], None] | None = None,
    ) -> None:
        self.local = local or {}  # aksi internal Jarvis (mis. stop_speaking), bukan tool OS
        self.on_error = on_error or (lambda: None)
        self.pending: Intent | None = None

    def execute(self, intent: Intent, confirmed: bool = False) -> str:
        if intent.tool in self.local:
            return self.local[intent.tool](intent.args)
        try:
            return registry.call(intent.tool, intent.args, confirmed=confirmed)
        except ConfirmationRequired:
            self.pending = intent
            what = _confirm_text(intent)
            return f"Yakin mau {what}? Bilang ya atau tidak."
        except ToolError as e:
            logger.warning(f"tool {intent.tool} gagal: {e}")
            self.on_error()
            return str(e)

    def run(self, intents: list[Intent]) -> str:
        """Jalankan semua intent; berhenti di intent pertama yang butuh konfirmasi."""
        parts: list[str] = []
        for it in intents:
            parts.append(self.execute(it))
            if self.pending:
                break
        return " ".join(p for p in parts if p)

    def resolve(self, answer: bool | None) -> str:
        """Selesaikan konfirmasi: True = jalankan, False/None = batalkan (aman bila ragu)."""
        pending, self.pending = self.pending, None
        if pending is None:
            return ""
        if answer is True:
            return self.execute(pending, confirmed=True)
        if answer is False:
            return "Oke, dibatalkan."
        return "Saya tidak mendengar jawaban yang jelas, jadi saya batalkan."
