from __future__ import annotations

import json
import socketserver
import threading

import pytest

from jarvis import island
from jarvis.brain import rules
from jarvis.config import Config
from jarvis.tools.registry import ToolError, context, registry

GOT: list[dict] = []


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        GOT.append(json.loads(self.rfile.readline()))
        self.wfile.write(b'{"allow": true, "message": ""}\n')


@pytest.fixture
def isla(tmp_path):
    GOT.clear()
    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    f = tmp_path / "ipc.json"
    f.write_text(json.dumps({"port": srv.server_address[1], "token": "t0ken"}))
    cfg = Config()
    cfg.island.enabled = True
    cfg.island.ipc_file = str(f)
    yield cfg
    srv.shutdown()


def test_notify_sends_token_and_clean_text(isla) -> None:
    assert island.notify(isla, "Halo\nBos\x00  ini   tes")
    assert GOT == [{"token": "t0ken", "notify": "Halo Bos ini tes"}]


def test_text_is_truncated_to_isla_limit(isla) -> None:
    island.notify(isla, "x" * 500)
    assert len(GOT[0]["notify"]) == island.MAX_CHARS


def test_disabled_missing_or_dead_isla_is_silent_false(isla, tmp_path) -> None:
    isla.island.enabled = False
    assert not island.notify(isla, "a") and not GOT
    isla.island.enabled = True
    isla.island.ipc_file = str(tmp_path / "tidak-ada.json")
    assert not island.notify(isla, "a")  # Isla tak jalan → bukan error
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"port": 1, "token": "x"}))
    isla.island.ipc_file = str(bad)
    assert not island.notify(isla, "a")


def test_default_ipc_path_uses_tauri_identifier() -> None:
    assert island.ipc_file(Config()).parts[-2:] == ("com.royhan.isladesk", "ipc.json")


def test_tool_and_rule(isla, adapter) -> None:
    context.configure(adapter, isla, context.memory)
    assert (
        registry.call("show_on_island", {"text": "Selamat pagi"})
        == "Sudah saya kirim ke pulau Isla"
    )
    assert GOT[-1]["notify"] == "Selamat pagi"
    it = rules.match("Jarvis, tampilkan di pulau selamat pagi bos")
    assert it and it[0].tool == "show_on_island" and it[0].args["text"] == "selamat pagi bos"
    isla.island.enabled = False
    with pytest.raises(ToolError, match="belum diaktifkan"):
        registry.call("show_on_island", {"text": "x"})


def test_send_voice_maps_states_and_respects_flags(tmp_path) -> None:
    import socket
    import threading

    from jarvis.config import Config

    received: list[dict] = []
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve() -> None:
        conn, _ = srv.accept()
        with conn:
            received.append(json.loads(conn.makefile().readline()))
            conn.sendall(b'{"allow":true,"message":""}\n')

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    f = tmp_path / "ipc.json"
    f.write_text(json.dumps({"port": srv.getsockname()[1], "token": "k"}), encoding="utf-8")
    cfg = Config()
    cfg.island.enabled, cfg.island.ipc_file = True, str(f)
    assert island.send_voice(cfg, "confirming")
    t.join(2)
    srv.close()
    assert received == [{"token": "k", "voice": "listening"}]
    cfg.island.show_voice = False
    assert not island.send_voice(cfg, "speaking")  # dimatikan lewat config
