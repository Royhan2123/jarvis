"""Memori SQLite lokal: riwayat percakapan, fakta pengguna, catatan, pengingat."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

from jarvis.config import MemoryConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facts (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY, due REAL NOT NULL, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0);
"""


def data_dir() -> Path:
    d = Path(user_data_dir("jarvis"))
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass(frozen=True)
class Reminder:
    id: int
    due: float
    text: str


class Memory:
    def __init__(self, cfg: MemoryConfig | None = None, path: Path | str | None = None) -> None:
        self.cfg = cfg or MemoryConfig()
        self.path = Path(path) if path else data_dir() / "jarvis.db"
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self.purge_old()

    # ── percakapan ──
    def add_message(self, role: str, text: str) -> None:
        if not (self.cfg.enabled and self.cfg.save_conversations) or not text.strip():
            return
        with self._db:
            self._db.execute(
                "INSERT INTO conversations(ts, role, text) VALUES (?,?,?)",
                (time.time(), role, text),
            )

    def recent(self, n: int) -> list[dict[str, str]]:
        if not self.cfg.enabled or n <= 0:
            return []
        rows = self._db.execute(
            "SELECT role, text FROM conversations ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [{"role": r, "content": t} for r, t in reversed(rows)]

    def purge_old(self) -> None:
        cutoff = time.time() - self.cfg.retention_days * 86400
        with self._db:
            self._db.execute("DELETE FROM conversations WHERE ts < ?", (cutoff,))

    # ── fakta ──
    def set_fact(self, key: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO facts(key, value, ts) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
                (key.strip().lower(), value.strip(), time.time()),
            )

    def facts(self) -> dict[str, str]:
        return dict(self._db.execute("SELECT key, value FROM facts ORDER BY key").fetchall())

    def facts_text(self) -> str:
        f = self.facts() if self.cfg.enabled else {}
        return "; ".join(f"{k}: {v}" for k, v in f.items()) or "belum ada"

    # ── catatan ──
    def add_note(self, text: str) -> int:
        with self._db:
            cur = self._db.execute(
                "INSERT INTO notes(ts, text) VALUES (?,?)", (time.time(), text.strip())
            )
        return int(cur.lastrowid or 0)

    def notes(self, limit: int = 5) -> list[str]:
        rows = self._db.execute("SELECT text FROM notes ORDER BY id DESC LIMIT ?", (limit,))
        return [r[0] for r in rows.fetchall()]

    # ── pengingat ──
    def add_reminder(self, due: float, text: str) -> int:
        with self._db:
            cur = self._db.execute("INSERT INTO reminders(due, text) VALUES (?,?)", (due, text))
        return int(cur.lastrowid or 0)

    def due_reminders(self, now: float | None = None) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT id, due, text FROM reminders WHERE done=0 AND due<=? ORDER BY due",
            (now if now is not None else time.time(),),
        ).fetchall()
        return [Reminder(*r) for r in rows]

    def mark_done(self, reminder_id: int) -> None:
        with self._db:
            self._db.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))

    def pending_reminders(self) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT id, due, text FROM reminders WHERE done=0 ORDER BY due"
        ).fetchall()
        return [Reminder(*r) for r in rows]

    def close(self) -> None:
        self._db.close()
