"""Papan persetujuan: izin agen yang bisa dijawab dari luar (tombol di pulau Isla).

Jarvis membuat permintaan (`request`), menampilkannya di Isla, lalu `wait` jawabannya. Isla menjawab
lewat API lokal (`POST /v1/approvals/{id}`). Tak ada jawaban sampai batas waktu = ditolak (aman).
"""

from __future__ import annotations

import threading
import uuid


class ApprovalBoard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._answers: dict[str, bool] = {}

    def request(self) -> str:
        approval_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._pending[approval_id] = threading.Event()
        return approval_id

    def resolve(self, approval_id: str, allow: bool) -> bool:
        """Catat jawaban; False bila permintaannya tak ada (sudah selesai/kedaluwarsa)."""
        with self._lock:
            event = self._pending.get(approval_id)
            if event is None or approval_id in self._answers:
                return False
            self._answers[approval_id] = allow
        event.set()
        return True

    def wait(self, approval_id: str, timeout: float) -> bool:
        """True hanya bila disetujui; timeout atau ditolak = False. Permintaan dibersihkan."""
        with self._lock:
            event = self._pending.get(approval_id)
        if event is None:
            return False
        event.wait(timeout)
        with self._lock:
            self._pending.pop(approval_id, None)
            return self._answers.pop(approval_id, False)

    def pending(self) -> list[str]:
        with self._lock:
            return [i for i in self._pending if i not in self._answers]


BOARD = ApprovalBoard()
