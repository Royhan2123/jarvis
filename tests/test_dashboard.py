from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jarvis.config import Config
from jarvis.ui.dashboard import create_app

TOKEN = "t0ken"
HOST = {"host": "127.0.0.1:8765"}
CSRF = {**HOST, "x-requested-with": "jarvis-dashboard"}


@pytest.fixture
def env(tmp_path, adapter):
    path = tmp_path / "config.yaml"
    path.write_text("general:\n  name: Tes\n", encoding="utf-8")
    client = TestClient(create_app(Config(), path, TOKEN, 8765), base_url="http://127.0.0.1:8765")
    return client, path


def login(client) -> None:
    r = client.get("/", params={"token": TOKEN}, headers=HOST, follow_redirects=False)
    assert r.status_code == 303


def test_requires_token(env) -> None:
    client, _ = env
    assert client.get("/api/status", headers=HOST).status_code == 401
    assert client.get("/", params={"token": "salah"}, headers=HOST).status_code == 401


def test_rejects_foreign_host(env) -> None:
    client, _ = env
    login(client)
    assert client.get("/api/status", headers={"host": "evil.com"}).status_code == 403


def test_status_tools_logs(env) -> None:
    client, _ = env
    login(client)
    assert client.get("/api/status", headers=HOST).json()["name"] == "Jarvis"
    names = {t["name"] for t in client.get("/api/tools", headers=HOST).json()["tools"]}
    assert "get_time" in names
    assert "lines" in client.get("/api/logs", headers=HOST).json()


def test_save_config_validates_and_needs_csrf(env) -> None:
    client, path = env
    login(client)
    body = {"yaml": "general:\n  name: Baru\n"}
    assert client.put("/api/config", json=body, headers=HOST).status_code == 403
    assert client.put("/api/config", json=body, headers=CSRF).status_code == 200
    assert "Baru" in path.read_text(encoding="utf-8")
    assert (path.parent / "config.yaml.bak").exists()


def test_invalid_config_not_saved(env) -> None:
    client, path = env
    login(client)
    bad = {"yaml": "llm:\n  num_ctx: banyak\n"}
    assert client.put("/api/config", json=bad, headers=CSRF).status_code == 422
    assert "Tes" in path.read_text(encoding="utf-8")
