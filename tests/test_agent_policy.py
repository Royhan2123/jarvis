from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jarvis.agent import policy
from jarvis.brain import rules
from jarvis.brain.actions import ActionRunner
from jarvis.brain.rules import Intent
from jarvis.config import Config
from jarvis.tools.registry import ConfirmationRequired, context, registry
from jarvis.ui.dashboard import create_app

ALL = ["edit_file", "write_file", "run_command"]


def test_resolve_action_from_spoken_phrases() -> None:
    assert policy.resolve_action("ubah file") == "edit_file"
    assert policy.resolve_action("mengubah file") == "edit_file"
    assert policy.resolve_action("membuat file baru") == "write_file"
    assert policy.resolve_action("menjalankan perintah") == "run_command"
    assert policy.resolve_action("perintah shell") == "run_command"
    assert policy.resolve_action("semuanya") == "all"
    assert policy.resolve_action("makan nasi") is None


def test_set_asking_loosen_tighten_and_all() -> None:
    cfg = Config()
    assert cfg.agent.confirm_actions == ALL  # default: tanya untuk semua
    assert policy.set_asking(cfg, "edit_file", ask=False) == ["write_file", "run_command"]
    assert policy.set_asking(cfg, "edit_file", ask=True) == ALL  # urutan tetap
    assert policy.set_asking(cfg, "all", ask=False) == []
    assert policy.set_asking(cfg, "all", ask=True) == ALL
    with pytest.raises(ValueError, match="tidak dikenal"):
        policy.set_asking(cfg, "format_disk", ask=False)


def test_summary_sentences() -> None:
    assert "bertanya dulu sebelum" in policy.summary(["edit_file"])
    assert "tetap bertanya" in policy.summary(ALL)
    assert "blokir keras tetap berlaku" in policy.summary([])


@pytest.mark.parametrize(
    ("said", "tool", "action"),
    [
        ("jangan tanya lagi untuk ubah file", "agent_auto_approve", "edit_file"),
        (
            "Jarvis, tidak usah tanya izin lagi buat membuat file baru",
            "agent_auto_approve",
            "write_file",
        ),
        ("gak usah tanya lagi untuk menjalankan perintah", "agent_auto_approve", "run_command"),
        ("jangan tanya lagi untuk semuanya", "agent_auto_approve", "all"),
        ("selalu tanya untuk ubah file", "agent_ask_always", "edit_file"),
        ("tanya dulu sebelum menjalankan perintah", "agent_ask_always", "run_command"),
        ("mulai tanya lagi untuk semuanya", "agent_ask_always", "all"),
    ],
)
def test_voice_rules_for_permissions(said, tool, action) -> None:
    assert rules.match(said) == [Intent(tool, {"action": action})]


def test_unrelated_or_unknown_phrases_do_not_trigger() -> None:
    assert rules.match("jangan tanya lagi untuk makan nasi") is None
    assert rules.match("tanya dulu apa kabar") is None
    assert rules.match("jangan bilang siapa siapa") is None


def test_tools_loosening_needs_voice_confirmation_tightening_does_not(adapter) -> None:
    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    with pytest.raises(ConfirmationRequired):
        registry.call("agent_auto_approve", {"action": "edit_file"})
    assert cfg.agent.confirm_actions == ALL  # belum berubah tanpa "ya"
    out = registry.call("agent_auto_approve", {"action": "edit_file"}, confirmed=True)
    assert "sampai Jarvis dimatikan" in out and cfg.agent.confirm_actions == [
        "write_file",
        "run_command",
    ]
    registry.call("agent_ask_always", {"action": "edit_file"})  # mengetatkan: tanpa konfirmasi
    assert cfg.agent.confirm_actions == ALL


def test_llm_never_sees_the_loosening_tool(adapter) -> None:
    from jarvis.brain.router import Router

    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    for text in ["jangan tanya lagi untuk ubah file", "kerjakan perbaiki bug", "ubah file toko.py"]:
        names = {t["function"]["name"] for t in Router(cfg).tool_schemas(text, escalate=False)}
        assert "agent_auto_approve" not in names, text


def test_voice_confirmation_sentence_names_what_is_loosened(adapter) -> None:
    cfg = Config()
    context.configure(adapter, cfg, context.memory)
    runner = ActionRunner()
    out = runner.execute(Intent("agent_auto_approve", {"action": "run_command"}))
    assert "menjalankan perintah" in out and runner.pending is not None
    assert "sampai Jarvis dimatikan" in out
    done = runner.resolve(True)  # "ya" -> dijalankan
    assert "sampai Jarvis dimatikan" in done and cfg.agent.confirm_actions == [
        "edit_file",
        "write_file",
    ]


def test_persist_replaces_only_the_line_and_keeps_comments(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "agent:\n  enabled: true\n  # komentar penting\n"
        '  confirm_actions: ["edit_file", "write_file", "run_command"]   # tanya\n'
        "  max_steps: 12\n",
        encoding="utf-8",
    )
    assert policy.persist(path, ["run_command"])
    text = path.read_text(encoding="utf-8")
    assert 'confirm_actions: ["run_command"]   # tanya' in text
    assert "# komentar penting" in text and "max_steps: 12" in text
    assert (tmp_path / "config.yaml.bak").exists()
    assert Config.model_validate(__import__("yaml").safe_load(text)).agent.confirm_actions == [
        "run_command"
    ]
    assert not policy.persist(tmp_path / "tidak-ada.yaml", ALL)
    other = tmp_path / "lain.yaml"
    other.write_text("general:\n  name: X\n", encoding="utf-8")
    assert not policy.persist(other, ALL)  # barisnya tak ada: tidak menebak


# ── dashboard ──
TOKEN = "t0ken"
HOST = {"host": "127.0.0.1:8765"}
CSRF = {**HOST, "x-requested-with": "jarvis-dashboard"}


@pytest.fixture
def dash(tmp_path, adapter):
    path = tmp_path / "config.yaml"
    path.write_text(
        'agent:\n  confirm_actions: ["edit_file", "write_file", "run_command"]\n', encoding="utf-8"
    )
    cfg = Config()
    client = TestClient(create_app(cfg, path, TOKEN, 8765), base_url="http://127.0.0.1:8765")
    client.get("/", params={"token": TOKEN}, headers=HOST, follow_redirects=False)
    return client, cfg, path


def test_dashboard_reads_and_changes_permissions(dash) -> None:
    client, cfg, _ = dash
    got = client.get("/api/agent", headers=HOST).json()
    assert got["confirm_actions"] == ALL and [a["id"] for a in got["actions"]] == ALL
    r = client.put("/api/agent", headers=CSRF, json={"confirm_actions": ["run_command"]})
    assert r.status_code == 200 and not r.json()["persisted"]
    assert cfg.agent.confirm_actions == [
        "run_command"
    ]  # berlaku seketika di objek config yang dipakai agen


def test_dashboard_can_persist_and_rejects_bad_input(dash) -> None:
    client, cfg, path = dash
    r = client.put(
        "/api/agent", headers=CSRF, json={"confirm_actions": ["edit_file"], "persist": True}
    )
    assert r.json()["persisted"] and 'confirm_actions: ["edit_file"]' in path.read_text(
        encoding="utf-8"
    )
    bad = client.put("/api/agent", headers=CSRF, json={"confirm_actions": ["format_disk"]})
    assert bad.status_code == 422 and cfg.agent.confirm_actions == ["edit_file"]  # tak berubah


def test_dashboard_permission_endpoint_is_protected(dash, tmp_path) -> None:
    client, cfg, _ = dash
    assert (
        client.put("/api/agent", headers=HOST, json={"confirm_actions": []}).status_code == 403
    )  # tanpa CSRF
    anon = TestClient(
        create_app(cfg, tmp_path / "x.yaml", TOKEN, 8765), base_url="http://127.0.0.1:8765"
    )
    assert anon.get("/api/agent", headers=HOST).status_code == 401  # tanpa token
    assert cfg.agent.confirm_actions == ALL
