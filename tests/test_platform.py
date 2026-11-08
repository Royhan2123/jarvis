"""Uji perintah yang dibentuk adapter (tanpa menjalankan apa pun sungguhan)."""

from __future__ import annotations

import pytest

from jarvis.platform import macos
from jarvis.platform.base import AppNotFound, PlatformError


@pytest.fixture
def mac(monkeypatch):
    calls: list[list[str]] = []
    state = {"running": "true", "fail": False}

    def fake_run(cmd, timeout=10.0):
        calls.append(cmd)
        if state["fail"]:
            raise PlatformError("gagal")
        return state["running"] if "System Events" in " ".join(cmd) else ""

    monkeypatch.setattr(macos, "run", fake_run)
    return macos.MacAdapter(), calls, state


def test_mac_open_app_uses_argument_list(mac) -> None:
    a, calls, _ = mac
    a.open_app("Google Chrome")
    assert calls == [["open", "-a", "Google Chrome"]]


def test_mac_open_missing_app(mac) -> None:
    a, _, state = mac
    state["fail"] = True
    with pytest.raises(AppNotFound):
        a.open_app("Foo")


def test_mac_app_name_never_inside_script(mac) -> None:
    a, calls, _ = mac
    a.close_app('Evil" to quit')
    quit_call = calls[-1]
    assert quit_call[0] == "osascript" and quit_call[-1] == 'Evil" to quit'
    assert "Evil" not in quit_call[2]  # nama hanya lewat argv


def test_mac_close_not_running(mac) -> None:
    a, _, state = mac
    state["running"] = "false"
    with pytest.raises(AppNotFound):
        a.close_app("Spotify")


def test_mac_volume_and_media(mac) -> None:
    a, calls, _ = mac
    a.set_volume(30)
    assert calls[-1][-1] == "set volume output volume 30"
    a.media("next")
    assert "next track" in calls[-1][2] and calls[-1][-1] == "Spotify"


def test_mac_no_player_running(mac) -> None:
    a, _, state = mac
    state["running"] = "false"
    with pytest.raises(PlatformError, match="pemutar musik"):
        a.media("play_pause")
