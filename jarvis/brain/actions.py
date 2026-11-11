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
    if intent.tool == "agent_auto_approve":
        from jarvis.agent import policy

        what = str(a.get("action", "?"))
        spoken = policy.label(what) if what in {*policy.ACTIONS, "all"} else what
        return f"berhenti bertanya izin sebelum {spoken}, sampai Jarvis dimatikan"
    if intent.tool == "create_file":
        return f"membuat file baru {str(a.get('path', '?'))[-40:]}"
    return CONFIRM_TEXT.get(intent.tool, f"menjalankan {intent.tool}")


class ActionRunner:
    """Menjalankan intent satu per satu. Tool `high` ditahan di `pending` sampai dikonfirmasi."""

    def __init__(
        self,
        local: dict[str, Callable[[dict], str]] | None = None,
        on_error: Callable[[], None] | None = None,
        lang: Callable[[], str] | None = None,
    ) -> None:
        self.lang = lang or (
            lambda: "id"
        )  # bahasa ucapan terakhir; "en" → balasan tool berbahasa Inggris
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
        return self._localize(" ".join(p for p in parts if p))

    def _localize(self, text: str) -> str:
        if self.lang() != "en":
            return text
        from jarvis.brain.replies_en import to_english

        return to_english(text)

    def resolve(self, answer: bool | None) -> str:
        """Selesaikan konfirmasi: True = jalankan, False/None = batalkan (aman bila ragu)."""
        pending, self.pending = self.pending, None
        if pending is None:
            return ""
        if answer is True:
            return self._localize(self.execute(pending, confirmed=True))
        if answer is False:
            return self._localize("Oke, dibatalkan.")
        return "Saya tidak mendengar jawaban yang jelas, jadi saya batalkan."
