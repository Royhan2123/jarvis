from __future__ import annotations

from datetime import datetime

import pytest

from jarvis.config import Config
from jarvis.tools.registry import (
    ConfirmationRequired,
    Risk,
    ToolError,
    ToolRegistry,
    context,
    registry,
)
from jarvis.tools.system import format_date_id, format_time_id
from jarvis.tools.web import normalize_url


def test_all_p0_tools_registered(adapter) -> None:
    expected = {
        "open_app", "close_app", "set_volume", "mute", "media",
        "open_url", "web_search", "get_time", "system_info", "lock_screen",
    }  # fmt: skip
    assert expected <= set(registry.names())


def test_schema_is_ollama_compatible(adapter) -> None:
    sch = {s["function"]["name"]: s for s in registry.schemas()}
    vol = sch["set_volume"]["function"]
    assert sch["set_volume"]["type"] == "function"
    assert vol["parameters"]["properties"]["percent"]["type"] == "integer"
    assert vol["parameters"]["required"] == ["percent"]
    assert sch["media"]["function"]["parameters"]["properties"]["action"]["enum"] == [
        "play_pause", "next", "prev",
    ]  # fmt: skip


def test_volume_is_clamped(adapter) -> None:
    registry.call("set_volume", {"percent": 250})
    registry.call("set_volume", {"percent": -5})
    assert adapter.calls == [("set_volume", 100), ("set_volume", 0)]


def test_bad_arguments_rejected_before_execution(adapter) -> None:
    for name, args in [
        ("set_volume", {"percent": "keras"}),
        ("set_volume", {}),
        ("set_volume", {"percent": 10, "extra": 1}),
        ("media", {"action": "format_disk"}),
    ]:
        with pytest.raises(ToolError):
            registry.call(name, args)
    assert adapter.calls == []


def test_unknown_tool(adapter) -> None:
    with pytest.raises(ToolError):
        registry.call("run_shell", {"cmd": "rm -rf /"})


def test_no_shell_tool_exists(adapter) -> None:
    banned = {"run_shell", "shell", "exec", "eval", "run_command"}
    assert not banned & set(registry.names())


@pytest.mark.parametrize(
    "name", ["Spotify; rm -rf /", "a$(whoami)", 'x" & quit', "../../etc", "a|b", "", "x" * 80]
)
def test_app_name_injection_rejected(adapter, name) -> None:
    with pytest.raises(ToolError):
        registry.call("open_app", {"name": name})
    assert adapter.calls == []


def test_app_alias_and_allowlist(adapter) -> None:
    registry.call("open_app", {"name": "VS Code"})
    assert adapter.calls[-1] == ("open_app", "Visual Studio Code")
    context.cfg.tools.apps.allowed = ["Spotify"]
    registry.call("open_app", {"name": "spotify"})
    with pytest.raises(ToolError):
        registry.call("open_app", {"name": "Chrome"})


def test_platform_error_becomes_tool_error(adapter) -> None:
    with pytest.raises(ToolError, match="tidak ditemukan"):
        registry.call("open_app", {"name": "Tidak Ada"})


def test_high_risk_requires_confirmation() -> None:
    reg = ToolRegistry()
    from jarvis.tools import registry as r

    called: list[int] = []
    old = r.registry
    r.registry = reg
    try:

        @r.tool(name="danger", description="x", risk="high")
        def danger() -> str:
            called.append(1)
            return "ok"

    finally:
        r.registry = old
    context.configure(None, Config())
    with pytest.raises(ConfirmationRequired):
        reg.call("danger")
    assert called == []
    assert reg.call("danger", confirmed=True) == "ok"
    assert reg.get("danger").risk is Risk.HIGH


def test_media_and_mute_and_lock(adapter) -> None:
    registry.call("media", {"action": "next"})
    registry.call("mute", {})
    registry.call("mute", {"on": False})
    registry.call("lock_screen")
    assert adapter.calls == [
        ("media", "next"), ("mute", True), ("mute", False), ("lock_screen",),
    ]  # fmt: skip


def test_url_validation() -> None:
    assert normalize_url("youtube.com") == "https://youtube.com"
    assert normalize_url("http://a.com/x") == "http://a.com/x"
    for bad in [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,x",
        "a b.com",
        "ftp://x.com",
    ]:
        with pytest.raises(ToolError):
            normalize_url(bad)


def test_web_search_opens_google(adapter, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u) or True)
    registry.call("web_search", {"query": "resep rendang & sambal"})
    assert opened == ["https://www.google.com/search?q=resep+rendang+%26+sambal"]


def test_time_and_date_format() -> None:
    dt = datetime(2026, 11, 8, 14, 5)  # Minggu
    assert format_time_id(dt) == "Sekarang jam 14.05"
    assert format_date_id(dt) == "Hari ini Minggu, 8 November 2026"


def test_system_info_runs(adapter) -> None:
    out = registry.call("system_info", {"kind": "ram"})
    assert out.startswith("RAM terpakai") and "persen" in out
