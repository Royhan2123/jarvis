from __future__ import annotations

import http.server
import json
import threading

import pytest

from jarvis import smarthome
from jarvis.brain.rules import Intent, match_devices
from jarvis.config import Config, DeviceConfig
from jarvis.tools.registry import ToolError, context, registry

SEEN: list[tuple[str, str, dict | None, str]] = []


class FakeHA(http.server.BaseHTTPRequestHandler):
    def _reply(self, obj: object, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(("POST", self.path, body, self.headers.get("Authorization", "")))
        self._reply([])

    def do_GET(self) -> None:  # noqa: N802
        SEEN.append(("GET", self.path, None, self.headers.get("Authorization", "")))
        self._reply({"state": "on"})

    def log_message(self, *a) -> None:  # noqa: ANN002
        pass


@pytest.fixture
def home(adapter, tmp_path):
    SEEN.clear()
    server = http.server.HTTPServer(("127.0.0.1", 0), FakeHA)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    token = tmp_path / "token"
    token.write_text("rahasia123\n")
    cfg = Config()
    s = cfg.smarthome
    s.enabled = True
    s.home_assistant.url = f"http://127.0.0.1:{server.server_port}"
    s.home_assistant.token_file = str(token)
    s.devices = {
        "lampu ruang tamu": DeviceConfig(type="ha", entity="light.ruang_tamu"),
        "pintu depan": DeviceConfig(type="ha", entity="lock.front_door"),
        "kipas": DeviceConfig(type="mqtt", topic="home/kipas/set"),
    }
    context.configure(adapter, cfg, context.memory)
    yield cfg
    server.shutdown()


def test_turn_on_light_with_brightness(home) -> None:
    out = registry.call(
        "device_control", {"name": "Lampu  Ruang Tamu", "action": "on", "brightness": 40}
    )
    assert out == "lampu ruang tamu sudah dinyalakan"
    method, path, body, auth = SEEN[-1]
    assert (method, path) == ("POST", "/api/services/light/turn_on")
    assert body == {"entity_id": "light.ruang_tamu", "brightness_pct": 40}
    assert auth == "Bearer rahasia123"


def test_state(home) -> None:
    assert (
        registry.call("device_state", {"name": "lampu ruang tamu"})
        == "lampu ruang tamu sedang menyala"
    )
    assert SEEN[-1][:2] == ("GET", "/api/states/light.ruang_tamu")


def test_lock_domain_is_refused(home) -> None:
    with pytest.raises(ToolError, match="bukan kunci"):
        registry.call("device_control", {"name": "pintu depan", "action": "off"})
    assert not SEEN


def test_unknown_device_and_bad_action(home) -> None:
    with pytest.raises(ToolError, match="tidak dikenal"):
        registry.call("device_control", {"name": "oven", "action": "on"})
    with pytest.raises(ToolError, match="Aksi"):
        registry.call("device_control", {"name": "lampu ruang tamu", "action": "hapus"})


def test_disabled_by_default(adapter) -> None:
    with pytest.raises(ToolError, match="belum diaktifkan"):
        registry.call("device_control", {"name": "x", "action": "on"})


def test_offline_only_blocks_public_host(home) -> None:
    home.smarthome.home_assistant.url = "http://8.8.8.8:8123"
    with pytest.raises(ToolError, match="bukan jaringan rumah"):
        registry.call("device_state", {"name": "lampu ruang tamu"})
    assert not SEEN


def test_mqtt_publish(home, monkeypatch) -> None:
    sent: list = []
    monkeypatch.setattr(smarthome, "_mqtt_publish", lambda cfg, t, p: sent.append((t, p)))
    registry.call("device_control", {"name": "kipas", "action": "off"})
    assert sent == [("home/kipas/set", "OFF")]
    with pytest.raises(ToolError, match="MQTT"):
        registry.call("device_state", {"name": "kipas"})


def test_is_local_host() -> None:
    assert smarthome.is_local_host("127.0.0.1") and smarthome.is_local_host("192.168.1.5")
    assert smarthome.is_local_host("homeassistant.local")
    assert not smarthome.is_local_host("8.8.8.8")


def test_voice_rule_only_for_registered_devices() -> None:
    names = ["lampu ruang tamu", "lampu"]
    assert match_devices("Nyalakan lampu ruang tamu", names) == [
        Intent("device_control", {"name": "lampu ruang tamu", "action": "on"})
    ]
    assert match_devices("matikan lampu", names)[0].args["name"] == "lampu"
    assert match_devices("apakah lampu ruang tamu menyala", names)[0].tool == "device_state"
    assert match_devices("matikan komputer", names) is None
    assert match_devices("matikan oven", names) is None
