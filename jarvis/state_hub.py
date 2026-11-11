"""Papan status Jarvis (idle/listening/thinking/speaking/confirming) yang bisa dibaca thread lain.

Ringan (tanpa FastAPI/Ollama) supaya `app.py` boleh mengimpornya. Dipakai API lokal
(`/v1/state`) agar aplikasi lain, mis. Isla Desk, menampilkan status langsung. Isla tidak cocok
diberi status lewat `notify`: pesan setara antre dan tiap pesan tampil 8 detik, sehingga
"Mendengarkan…" muncul setelah interaksinya selesai.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any


class StateHub:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self.state = "loading"
        self.seq = 0  # naik tiap perubahan; klien bisa mendeteksi yang terlewat
        self.at = time.time()

    def publish(self, state: str) -> None:
        with self._cond:
            if state == self.state:
                return
            self.state, self.seq, self.at = state, self.seq + 1, time.time()
            self._cond.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._cond:
            return {"state": self.state, "seq": self.seq, "at": self.at}

    def wait(self, last_seq: int, timeout: float) -> dict[str, Any] | None:
        """Tunggu perubahan setelah `last_seq` (maks `timeout` dtk); None bila tak ada perubahan."""
        with self._cond:
            if self.seq == last_seq:
                self._cond.wait(timeout=timeout)
            if self.seq == last_seq:
                return None
            return {"state": self.state, "seq": self.seq, "at": self.at}

    def stream(
        self, ping_every: float = 15.0, stop: threading.Event | None = None
    ) -> Iterator[dict[str, Any] | None]:
        """Keadaan sekarang, lalu tiap perubahan. `None` = denyut. Berhenti saat `stop` menyala."""
        last_seq, last_ping = -1, time.monotonic()
        while stop is None or not stop.is_set():
            snap = self.wait(last_seq, min(1.0, ping_every))
            if snap is not None:
                last_seq, last_ping = snap["seq"], time.monotonic()
                yield snap
            elif time.monotonic() - last_ping >= ping_every:
                last_ping = time.monotonic()
                yield None


HUB = StateHub()
