from __future__ import annotations

import json
import os
import threading
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from jarvis.config import Config
from jarvis.tools.registry import context
from jarvis.ui.api import ApiBackend, Task, info_path, stream_events, write_info
from jarvis.ui.dashboard import create_app

TOKEN = "t0ken-rahasia"
PORT = 8765
HOST = {"host": f"127.0.0.1:{PORT}"}
AUTH = {**HOST, "authorization": f"Bearer {TOKEN}"}


class FakeLLM:
    """Klien Ollama palsu: mengalirkan potongan teks; `calls` mencatat permintaan."""

    def __init__(self, pieces=("Halo", ", ", "Bos"), fail=False) -> None:
        self.pieces, self.fail, self.calls = pieces, fail, []

    def chat(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("Ollama mati")
        for p in self.pieces:
            yield NS(message=NS(content=p, tool_calls=None))


class FakeAgentClient:
    """Memutar balasan agen: tuple (nama, args) = panggil tool, str = jawaban akhir."""

    def __init__(self, script) -> None:
        self.script = list(script)

    def chat(self, **kw):
        step = self.script.pop(0)
        if isinstance(step, str):
            return NS(message=NS(content=step, tool_calls=None))
        call = NS(function=NS(name=step[0], arguments=step[1]))
        return NS(message=NS(content="", tool_calls=[call]))


@pytest.fixture
def cfg(tmp_path) -> Config:
    c = Config()
    c.ui.api.enabled = True
    c.agent.enabled = True
    c.workspace.folders = [str(tmp_path)]
    (tmp_path / "toko.py").write_text("def total(a, b):\n    return a - b\n", encoding="utf-8")
    return c


def make_client(cfg, tmp_path, llm=None, agent=None):
    backend = ApiBackend(cfg, llm_client=llm or FakeLLM(), agent_client=agent)
    app = create_app(cfg, tmp_path / "config.yaml", TOKEN, PORT, backend=backend)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}"), backend


@pytest.fixture
def api(cfg, tmp_path, adapter):
    context.configure(adapter, cfg, context.memory)
    return make_client(cfg, tmp_path)


def sse_events(client, task_id, on_confirm=None):
    """Baca aliran SSE sampai tugas selesai; `on_confirm(event)` dipanggil saat ada izin."""
    events, name = [], None
    with client.stream("GET", f"/v1/agent/{task_id}/events", headers=AUTH) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev)
                if name == "confirm" and on_confirm:
                    on_confirm(ev)
    return events


# ── otentikasi ──
def test_requires_bearer_token_and_valid_host(api) -> None:
    client, _ = api
    assert client.get("/v1/status", headers=HOST).status_code == 401
    assert (
        client.get("/v1/status", headers={**HOST, "authorization": "Bearer salah"}).status_code
        == 401
    )
    assert (
        client.get("/v1/status", headers={**HOST, "authorization": f"Basic {TOKEN}"}).status_code
        == 401
    )
    assert client.get("/v1/status", headers=AUTH).status_code == 200
    evil = {"host": "evil.example.com", "authorization": f"Bearer {TOKEN}"}
    assert client.get("/v1/status", headers=evil).status_code == 403  # anti DNS-rebinding


def test_api_is_absent_unless_enabled(tmp_path, adapter) -> None:
    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    client = TestClient(
        create_app(cfg, tmp_path / "c.yaml", TOKEN, PORT), base_url=f"http://127.0.0.1:{PORT}"
    )
    assert client.get("/v1/status", headers=AUTH).status_code == 404


def test_status(api, cfg) -> None:
    client, _ = api
    s = client.get("/v1/status", headers=AUTH).json()
    assert s["agent"] == {
        "enabled": True,
        "workspace": True,
        "busy": False,
        "confirm_actions": ["edit_file", "write_file", "run_command"],
    }
    assert s["models"]["fast"] == cfg.llm.fast_model


# ── tanya ──
def test_ask_goes_through_rules_then_llm_with_history(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    llm = FakeLLM()
    client, _ = make_client(cfg, tmp_path, llm=llm)
    rule = client.post("/v1/ask", headers=AUTH, json={"text": "jam berapa sekarang"}).json()
    assert rule["tier"] == "rule" and rule["reply"] and not llm.calls  # Tier 0: tanpa LLM
    chat = client.post(
        "/v1/ask", headers=AUTH, json={"text": "ceritakan sesuatu yang menarik"}
    ).json()
    assert chat == {"reply": "Halo, Bos", "tier": "fast"}
    client.post("/v1/ask", headers=AUTH, json={"text": "lanjutkan ceritanya"})
    roles = [m["role"] for m in llm.calls[-1]["messages"]]
    assert roles.count("user") >= 2  # riwayat percakapan API tersimpan antar permintaan


def test_ask_validates_input(api, cfg) -> None:
    client, _ = api
    assert client.post("/v1/ask", headers=AUTH, json={"text": "   "}).status_code == 422
    long = "x" * (cfg.ui.api.max_text_chars + 1)
    assert client.post("/v1/ask", headers=AUTH, json={"text": long}).status_code == 413
    assert client.post("/v1/ask", headers=AUTH, json={}).status_code == 422


def test_ask_refuses_high_risk_actions_that_need_voice_confirmation(api, adapter) -> None:
    client, _ = api
    r = client.post("/v1/ask", headers=AUTH, json={"text": "matikan komputer"}).json()
    assert "konfirmasi suara" in r["reply"]
    assert not [c for c in adapter.calls if c[0] in {"shutdown", "restart"}]


def test_ask_reports_model_failure_as_502(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    client, _ = make_client(cfg, tmp_path, llm=FakeLLM(fail=True))
    r = client.post("/v1/ask", headers=AUTH, json={"text": "ceritakan sesuatu"})
    assert r.status_code == 502 and "Ollama mati" in r.json()["detail"]


# ── agen ──
EDIT = [
    ("read_file", {"path": "toko.py"}),
    ("edit_file", {"path": "toko.py", "old": "a - b", "new": "a + b"}),
    "Sudah diperbaiki.",
]


def start(client, task="perbaiki toko.py"):
    r = client.post("/v1/agent", headers=AUTH, json={"task": task})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_agent_flow_with_approval_over_sse(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    client, _ = make_client(cfg, tmp_path, agent=FakeAgentClient(EDIT))
    tid = start(client)

    def approve(ev):
        assert "toko.py" in ev["what"]
        assert client.post(
            f"/v1/agent/{tid}/confirm",
            headers=AUTH,
            json={"confirm_id": ev["confirm_id"], "allow": True},
        ).json() == {"ok": True}

    events = sse_events(client, tid, approve)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "step" and kinds[-1] == "done"
    assert {"step", "result", "confirm", "confirm_result", "done"} <= set(kinds)
    assert next(e for e in events if e["type"] == "confirm_result")["allow"] is True
    assert events[-1]["text"] == "Sudah diperbaiki."
    assert "a + b" in (tmp_path / "toko.py").read_text(encoding="utf-8")
    view = client.get(f"/v1/agent/{tid}", headers=AUTH).json()
    assert (
        view["status"] == "done"
        and view["result"] == "Sudah diperbaiki."
        and view["pending_confirm"] is None
    )


def test_denied_approval_leaves_file_untouched(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    client, _ = make_client(
        cfg, tmp_path, agent=FakeAgentClient(EDIT[:2] + ["Dibatalkan pengguna."])
    )
    tid = start(client)

    def deny(ev):
        client.post(
            f"/v1/agent/{tid}/confirm",
            headers=AUTH,
            json={"confirm_id": ev["confirm_id"], "allow": False},
        )

    events = sse_events(client, tid, deny)
    assert next(e for e in events if e["type"] == "confirm_result")["allow"] is False
    assert "a - b" in (tmp_path / "toko.py").read_text(encoding="utf-8")


def test_unanswered_approval_times_out_as_denied(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    cfg.ui.api.confirm_timeout_s = 0.1  # type: ignore[assignment]
    client, _ = make_client(cfg, tmp_path, agent=FakeAgentClient(EDIT[:2] + ["Tak ada jawaban."]))
    events = sse_events(client, start(client))
    res = next(e for e in events if e["type"] == "confirm_result")
    assert res == {**res, "allow": False, "timeout": True}
    assert "a - b" in (tmp_path / "toko.py").read_text(encoding="utf-8")


def test_only_one_task_at_a_time_and_cancel(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    client, backend = make_client(cfg, tmp_path, agent=FakeAgentClient(EDIT[:2] + ["dihentikan"]))
    tid = start(client)
    task = backend.get_task(tid)
    for _ in range(200):  # tunggu sampai pertanyaan izin muncul
        if task.pending:
            break
        threading.Event().wait(0.01)
    assert task.pending is not None
    busy = client.post("/v1/agent", headers=AUTH, json={"task": "tugas kedua"})
    assert busy.status_code == 409 and "sedang mengerjakan" in busy.json()["detail"]
    assert client.get("/v1/status", headers=AUTH).json()["agent"]["busy"] is True
    assert client.post(f"/v1/agent/{tid}/cancel", headers=AUTH).json()["ok"] is True
    events = sse_events(client, tid)
    assert events[-1]["type"] == "cancelled"
    assert "a - b" in (tmp_path / "toko.py").read_text(
        encoding="utf-8"
    )  # izin tertunda dianggap ditolak
    assert (
        client.post("/v1/agent", headers=AUTH, json={"task": "lagi"}).status_code == 202
    )  # bebas lagi


def test_agent_preconditions_and_wrong_ids(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)
    cfg.agent.enabled = False
    client, _ = make_client(cfg, tmp_path)
    assert client.post("/v1/agent", headers=AUTH, json={"task": "x"}).status_code == 409
    cfg.agent.enabled = True
    cfg.workspace.folders = []
    r = client.post("/v1/agent", headers=AUTH, json={"task": "x"})
    assert r.status_code == 409 and "Folder kerja" in r.json()["detail"]
    assert client.get("/v1/agent/tidak-ada", headers=AUTH).status_code == 404
    assert client.get("/v1/agent/tidak-ada/events", headers=AUTH).status_code == 404
    cfg.workspace.folders = [str(tmp_path)]
    tid = start(client)
    bad = client.post(
        f"/v1/agent/{tid}/confirm", headers=AUTH, json={"confirm_id": "salah", "allow": True}
    )
    assert bad.status_code == 409


def test_agent_model_failure_becomes_error_event(cfg, tmp_path, adapter) -> None:
    context.configure(adapter, cfg, context.memory)

    class Broken:
        def chat(self, **kw):
            raise RuntimeError("Ollama mati")

    client, _ = make_client(cfg, tmp_path, agent=Broken())
    events = sse_events(client, start(client))
    assert events[-1]["type"] == "error" and "Ollama mati" in events[-1]["text"]


# ── aliran dan berkas penemuan ──
def test_stream_sends_heartbeat_when_idle() -> None:
    task = Task("t1", "x")
    gen = stream_events(task, ping_every=0.05)
    assert next(gen) is None  # denyut, bukan menunggu selamanya
    task.emit({"type": "step", "n": 1})
    assert next(gen) == {"type": "step", "n": 1}
    task.finish("done", "ok")
    assert [e["type"] for e in gen] == ["done"]


def test_event_list_is_capped_but_terminal_event_always_kept() -> None:
    task = Task("t2", "x")
    for i in range(2000):
        task.emit({"type": "step", "n": i})
    task.finish("done", "ok")
    assert len(task.events) == 1001 and task.events[-1]["type"] == "done"


def test_discovery_file_has_port_token_and_private_mode(tmp_path) -> None:
    path = write_info(PORT, TOKEN, tmp_path / "x" / "api.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (
        data["port"] == PORT
        and data["token"] == TOKEN
        and data["url"] == f"http://127.0.0.1:{PORT}"
    )
    assert data["pid"] == os.getpid()
    if os.name != "nt":  # izin POSIX tidak berlaku di Windows
        assert path.stat().st_mode & 0o077 == 0
    assert info_path().name == "api.json"
