"""API lokal berotentikasi (FastAPI) untuk aplikasi lain di komputer yang sama.

Contoh pemakai: aplikasi desktop (Isla Desk) yang ingin bertanya ke Jarvis atau memberi tugas ke
agen kerja dan menyetujui langkahnya lewat tombol, bukan suara. Rute ada di `/v1`:

    GET  /v1/status                      keadaan Jarvis (termasuk state suara)
    GET  /v1/state                       {state, seq, at}: idle/listening/thinking/dst.
    GET  /v1/state/events                SSE `state`: keadaan sekarang, lalu tiap perubahan
    POST /v1/ask            {text}       jawaban (router + LLM yang sama, tanpa suara)
    POST /v1/agent          {task}       mulai tugas agen -> {id}; satu tugas pada satu waktu
    GET  /v1/agent/{id}                  status + hasil
    GET  /v1/agent/{id}/events           SSE: step, result, confirm, confirm_result, done, error
    POST /v1/agent/{id}/confirm          {confirm_id, allow}  jawab pertanyaan izin
    POST /v1/agent/{id}/cancel           batalkan

Keamanan: sama dengan dashboard (hanya 127.0.0.1, header Host divalidasi middleware dashboard)
ditambah token acak per proses lewat `Authorization: Bearer`. Semua pengaman agen tetap berlaku:
blokir keras shell, file rahasia, `workspace.folders`, `agent.confirm_actions`. Pertanyaan izin yang
tak dijawab dalam `ui.api.confirm_timeout_s` dianggap DITOLAK. Aksi berisiko tinggi di `/v1/ask`
tidak dijalankan (butuh konfirmasi suara yang tak ada di sini).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from platformdirs import user_data_dir
from pydantic import BaseModel

from jarvis import workspace
from jarvis.agent import Agent, AgentError
from jarvis.brain.actions import ActionRunner
from jarvis.brain.llm import LLM
from jarvis.brain.router import Router
from jarvis.brain.rules import Intent
from jarvis.config import Config
from jarvis.state_hub import HUB
from jarvis.tools.registry import context

MAX_EVENTS = 1000
PING_EVERY_S = 15.0
FINISHED = {"done", "error", "cancelled"}


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


def info_path() -> Path:
    """Berkas penemuan {port, token, pid, url} untuk aplikasi lain (izin 600)."""
    return Path(user_data_dir("jarvis", appauthor=False)) / "api.json"


def write_info(port: int, token: str, path: Path | None = None) -> Path:
    path = path or info_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"port": port, "token": token, "pid": os.getpid(), "url": f"http://127.0.0.1:{port}"}
    path.write_text(json.dumps(body), encoding="utf-8")
    if os.name != "nt":  # izin POSIX tidak berlaku di Windows
        os.chmod(path, 0o600)
    return path


class Task:
    """Satu tugas agen: daftar event (untuk SSE) dan satu pertanyaan izin yang sedang menunggu."""

    def __init__(self, task_id: str, text: str) -> None:
        self.id, self.text = task_id, text
        self.status = "running"  # running | done | error | cancelled
        self.result: str | None = None
        self.events: list[dict[str, Any]] = []
        self.cond = threading.Condition()
        self.pending: dict[str, Any] | None = None  # {confirm_id, what, event, allow}
        self.agent: Agent | None = None

    def emit(self, event: dict[str, Any]) -> None:
        with self.cond:
            if len(self.events) < MAX_EVENTS or event.get("type") in FINISHED:
                self.events.append(event)
            self.cond.notify_all()

    def finish(self, status: str, text: str) -> None:
        self.status, self.result = status, text
        self.emit({"type": status, "text": text})

    def wait(self, i: int, timeout: float) -> tuple[list[dict[str, Any]], bool]:
        """Tunggu event setelah indeks `i` (maks `timeout` dtk). Mengembalikan (event baru, selesai
        dan semua sudah terbaca)."""
        with self.cond:
            if i >= len(self.events) and self.status == "running":
                self.cond.wait(timeout=timeout)
            batch = self.events[i:]
            return batch, self.status != "running" and i + len(batch) >= len(self.events)

    def answer(self, confirm_id: str, allow: bool) -> bool:
        """Jawab pertanyaan izin; False bila tak ada yang menunggu dengan id itu."""
        with self.cond:
            p = self.pending
            if p is None or p["confirm_id"] != confirm_id:
                return False
            p["allow"] = allow
            p["event"].set()
            return True

    def view(self) -> dict[str, Any]:
        p = self.pending
        return {
            "id": self.id,
            "status": self.status,
            "result": self.result,
            "events": len(self.events),
            "pending_confirm": {"confirm_id": p["confirm_id"], "what": p["what"]} if p else None,
        }


class ApiBackend:
    """Otak tanpa suara: LLM/router sendiri (riwayat terpisah dari suara) dan satu tugas agen."""

    def __init__(self, cfg: Config, llm_client: Any = None, agent_client: Any = None) -> None:
        self.cfg = cfg
        self._llm_client, self._agent_client = llm_client, agent_client
        self._llm: LLM | None = None
        self._ask_lock = threading.Lock()
        self._task_lock = threading.Lock()
        self.task: Task | None = None

    # ── tanya ──
    def ask(self, text: str) -> dict[str, Any]:
        with self._ask_lock:  # LLM menyimpan riwayat; satu pertanyaan pada satu waktu
            if self._llm is None:
                self._llm = LLM(self.cfg, client=self._llm_client, facts=context.memory.facts_text)
            return self._ask(text)

    def _run_intents(self, intents: list[Intent]) -> str:
        runner = ActionRunner()
        reply = runner.run(intents)
        if runner.pending is not None:  # butuh "ya" suara yang tak ada di API: tolak
            runner.pending = None
            return (
                "Aksi itu berisiko tinggi dan butuh konfirmasi suara, tidak dijalankan lewat API."
            )
        return reply

    def _ask(self, text: str) -> dict[str, Any]:
        assert self._llm is not None
        router = Router(self.cfg)
        plan = router.plan(text)
        if plan.intents:
            return {"reply": self._run_intents(plan.intents), "tier": "rule"}
        reply = "".join(
            self._llm.ask(text, model=plan.model, tools=plan.tools, num_ctx=plan.num_ctx)
        )
        calls = list(self._llm.tool_calls)
        tier = plan.tier
        if any(n == "escalate" for n, _ in calls):
            plan, tier = router.escalated(text), "smart"
            reply = "".join(
                self._llm.ask(text, model=plan.model, tools=plan.tools, num_ctx=plan.num_ctx)
            )
            calls = list(self._llm.tool_calls)
        if calls:
            result = self._run_intents([Intent(n, a) for n, a in calls if n != "escalate"])
            self._llm.replace_last_reply(result or "(selesai)")
            reply = result or reply
        return {"reply": reply.strip(), "tier": tier}

    # ── status ──
    def status(self) -> dict[str, Any]:
        c = self.cfg
        t = self.task
        return {
            "name": c.general.name,
            "offline_only": c.general.offline_only,
            "models": {"fast": c.llm.fast_model, "smart": c.llm.smart_model},
            "state": HUB.snapshot()["state"],
            "agent": {
                "enabled": c.agent.enabled,
                "workspace": bool(workspace.roots(c)),
                "busy": t is not None and t.status == "running",
                "confirm_actions": list(c.agent.confirm_actions),
            },
        }

    # ── agen ──
    def start_agent(self, text: str) -> Task:
        c = self.cfg
        if not c.agent.enabled:
            raise ApiError(409, "Agen kerja belum diaktifkan (agent.enabled: true)")
        if not workspace.roots(c):
            raise ApiError(409, "Folder kerja belum diatur (workspace.folders)")
        with self._task_lock:
            if self.task is not None and self.task.status == "running":
                raise ApiError(409, "Agen sedang mengerjakan tugas lain")
            task = Task(secrets.token_hex(6), text)
            self.task = task
        threading.Thread(
            target=self._run_agent, args=(task,), name="api-agent", daemon=True
        ).start()
        return task

    def _confirm(self, task: Task, what: str) -> bool:
        confirm_id = secrets.token_hex(4)
        pending = {
            "confirm_id": confirm_id,
            "what": what,
            "event": threading.Event(),
            "allow": False,
        }
        with task.cond:
            task.pending = pending
        task.emit({"type": "confirm", "confirm_id": confirm_id, "what": what})
        answered = pending["event"].wait(self.cfg.ui.api.confirm_timeout_s)
        with task.cond:
            task.pending = None
        allow = bool(pending["allow"]) and answered
        task.emit(
            {
                "type": "confirm_result",
                "confirm_id": confirm_id,
                "allow": allow,
                "timeout": not answered,
            }
        )
        return allow

    def _run_agent(self, task: Task) -> None:
        agent = Agent(
            self.cfg,
            lambda what: self._confirm(task, what),
            client=self._agent_client,
            on_event=task.emit,
        )
        task.agent = agent
        try:
            result = agent.run(task.text)
            cancelled = agent._cancelled.is_set()  # noqa: SLF001
            task.finish("cancelled" if cancelled else "done", result)
        except AgentError as e:
            task.finish("error", str(e))
        except Exception as e:  # noqa: BLE001 — Ollama mati dsb. jangan menjatuhkan server
            logger.warning(f"[api] agen gagal: {e}")
            task.finish("error", f"Agen gagal: {e}")

    def get_task(self, task_id: str) -> Task:
        t = self.task
        if t is None or t.id != task_id:
            raise ApiError(404, "Tugas tidak ditemukan")
        return t

    def cancel(self, task: Task) -> None:
        if task.status != "running":
            return
        if task.agent is not None:
            task.agent.cancel()
        with task.cond:  # pertanyaan izin yang menunggu dianggap ditolak
            if task.pending is not None:
                task.pending["allow"] = False
                task.pending["event"].set()


def sse(events: Iterator[dict[str, Any] | None]) -> Iterator[str]:
    """Format SSE; `None` = denyut (komentar) agar koneksi tak dianggap mati."""
    for ev in events:
        if ev is None:
            yield ": ping\n\n"
        else:
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"


def stream_events(task: Task, ping_every: float = PING_EVERY_S) -> Iterator[dict[str, Any] | None]:
    """Event tugas sampai selesai (generator sinkron; rute HTTP memakai versi async di bawah)."""
    i, last = 0, time.monotonic()
    while True:
        batch, over = task.wait(i, min(1.0, ping_every))
        i += len(batch)
        yield from batch
        if batch:
            last = time.monotonic()
        if over:
            return
        if not batch and time.monotonic() - last >= ping_every:
            last = time.monotonic()
            yield None


async def sse_stream(request: Request, wait, fmt, ping_every: float = PING_EVERY_S):  # noqa: ANN001, ANN201
    """Aliran SSE asinkron: menunggu di thread dengan jeda 1 dtk dan memeriksa putusnya klien tiap
    putaran, supaya thread dilepas segera (bukan menunggu denyut berikutnya)."""
    last = time.monotonic()
    state: Any = None
    while not await request.is_disconnected():
        chunks, state, over = await asyncio.to_thread(wait, state)
        for chunk in chunks:
            yield fmt(chunk)
        if chunks:
            last = time.monotonic()
        if over:
            return
        if not chunks and time.monotonic() - last >= ping_every:
            last = time.monotonic()
            yield ": ping\n\n"


class AskBody(BaseModel):
    text: str


class AgentBody(BaseModel):
    task: str


class ConfirmBody(BaseModel):
    confirm_id: str
    allow: bool


def build_router(backend: ApiBackend, token: str) -> APIRouter:
    cfg = backend.cfg
    router = APIRouter(prefix="/v1")

    def auth(request: Request) -> None:
        got = request.headers.get("authorization", "")
        scheme, _, value = got.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(value.strip(), token):
            raise HTTPException(401, "Token salah atau tidak ada")

    def check(text: str, field: str) -> str:
        text = text.strip()
        if not text:
            raise HTTPException(422, f"{field} kosong")
        if len(text) > cfg.ui.api.max_text_chars:
            raise HTTPException(413, f"{field} terlalu panjang (maks {cfg.ui.api.max_text_chars})")
        return text

    def guard(fn):  # noqa: ANN001, ANN202 — ubah ApiError jadi respons HTTP
        try:
            return fn()
        except ApiError as e:
            raise HTTPException(e.status, e.message) from e

    @router.get("/status", dependencies=[Depends(auth)])
    def status() -> dict:
        return backend.status()

    @router.get("/state", dependencies=[Depends(auth)])
    def state() -> dict:
        return HUB.snapshot()

    @router.get("/state/events", dependencies=[Depends(auth)])
    def state_events(request: Request) -> StreamingResponse:
        def wait(last):  # noqa: ANN001, ANN202
            snap = HUB.wait(-1 if last is None else last, 1.0)
            return ([snap] if snap else []), (snap["seq"] if snap else last), False

        def fmt(snap: dict) -> str:
            return f"event: state\ndata: {json.dumps(snap)}\n\n"

        return StreamingResponse(
            sse_stream(request, wait, fmt),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/ask", dependencies=[Depends(auth)])
    def ask(body: AskBody) -> dict:
        text = check(body.text, "text")
        try:
            return backend.ask(text)
        except Exception as e:  # noqa: BLE001 — Ollama mati dsb.
            logger.warning(f"[api] ask gagal: {e}")
            raise HTTPException(502, f"Tidak bisa bertanya ke model: {e}") from e

    @router.post("/agent", dependencies=[Depends(auth)], status_code=202)
    def start(body: AgentBody) -> dict:
        task = guard(lambda: backend.start_agent(check(body.task, "task")))
        return {"id": task.id, "status": task.status}

    @router.get("/agent/{task_id}", dependencies=[Depends(auth)])
    def view(task_id: str) -> dict:
        return guard(lambda: backend.get_task(task_id)).view()

    @router.get("/agent/{task_id}/events", dependencies=[Depends(auth)])
    def events(task_id: str, request: Request) -> StreamingResponse:
        task = guard(lambda: backend.get_task(task_id))

        def wait(i):  # noqa: ANN001, ANN202
            batch, over = task.wait(i or 0, 1.0)
            return batch, (i or 0) + len(batch), over

        def fmt(ev: dict) -> str:
            return f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            sse_stream(request, wait, fmt),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/agent/{task_id}/confirm", dependencies=[Depends(auth)])
    def confirm(task_id: str, body: ConfirmBody) -> dict:
        task = guard(lambda: backend.get_task(task_id))
        if not task.answer(body.confirm_id, body.allow):
            raise HTTPException(409, "Tidak ada pertanyaan izin dengan id itu yang menunggu")
        return {"ok": True}

    @router.post("/agent/{task_id}/cancel", dependencies=[Depends(auth)])
    def cancel(task_id: str) -> dict:
        task = guard(lambda: backend.get_task(task_id))
        backend.cancel(task)
        return {"ok": True, "status": task.status}

    return router
