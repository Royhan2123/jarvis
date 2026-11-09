"""Klien smart home: Home Assistant (REST, tanpa dependensi) dan MQTT (paho).

Keamanan: hanya perangkat di `smarthome.devices`; domain Home Assistant dibatasi ke daftar aman
(tidak ada lock, alarm, garasi); host harus alamat lokal kecuali general.offline_only = false;
token/password dibaca dari file/env, bukan dari config. Tidak ada service call bebas.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from jarvis.config import Config, DeviceConfig

ALLOWED_DOMAINS = {"light", "switch", "fan", "scene"}
ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


class SmartHomeError(RuntimeError):
    """Pesan aman untuk dibacakan."""


def is_local_host(host: str) -> bool:
    """True untuk loopback / jaringan rumah (RFC1918, link-local) / nama .local."""
    if host in {"localhost"} or host.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            return False
    return bool(infos)


def require_enabled(cfg: Config) -> None:
    if not cfg.smarthome.enabled:
        raise SmartHomeError("Smart home belum diaktifkan. Set smarthome.enabled di config.yaml")


def _guard(cfg: Config, host: str | None) -> None:
    require_enabled(cfg)
    if not host:
        raise SmartHomeError("Alamat smart home belum diatur di config.yaml")
    if cfg.general.offline_only and not is_local_host(host):
        raise SmartHomeError("Mode offline aktif dan alamat itu bukan jaringan rumah")


def _secret(file: str | None, env: str) -> str:
    if os.environ.get(env):
        return os.environ[env].strip()
    if file and Path(file).expanduser().is_file():
        return Path(file).expanduser().read_text(encoding="utf-8").strip()
    return ""


def resolve(cfg: Config, name: str) -> tuple[str, DeviceConfig]:
    """Cocokkan nama ucapan ke perangkat terdaftar (huruf kecil, spasi dirapikan)."""
    want = " ".join(name.lower().split())
    for key, dev in cfg.smarthome.devices.items():
        if " ".join(key.lower().split()) == want:
            return key, dev
    known = ", ".join(cfg.smarthome.devices) or "(belum ada)"
    raise SmartHomeError(f"Perangkat {name} tidak dikenal. Yang terdaftar: {known}")


def _ha_request(cfg: Config, method: str, path: str, body: dict | None = None) -> object:
    ha = cfg.smarthome.home_assistant
    parsed = urllib.parse.urlparse(ha.url)
    _guard(cfg, parsed.hostname)
    if parsed.scheme not in {"http", "https"}:
        raise SmartHomeError("URL Home Assistant harus http atau https")
    token = _secret(ha.token_file, "JARVIS_HA_TOKEN")
    if not token:
        raise SmartHomeError(
            "Token Home Assistant belum diatur (smarthome.home_assistant.token_file)"
        )
    req = urllib.request.Request(
        ha.url.rstrip("/") + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 — host sudah dijaga
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SmartHomeError(f"Home Assistant menolak permintaan ({e.code})") from e
    except (OSError, ValueError) as e:
        raise SmartHomeError("Tidak bisa terhubung ke Home Assistant") from e


def _check_entity(entity: str | None) -> str:
    if not entity or not ENTITY_RE.match(entity) or entity.split(".")[0] not in ALLOWED_DOMAINS:
        raise SmartHomeError(
            f"Perangkat harus bertipe {', '.join(sorted(ALLOWED_DOMAINS))} (bukan kunci atau alarm)"
        )
    return entity


def _mqtt_publish(cfg: Config, topic: str, payload: str) -> None:
    m = cfg.smarthome.mqtt
    _guard(cfg, m.host)
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    pw = _secret(m.password_file, "JARVIS_MQTT_PASSWORD")
    if m.username:
        client.username_pw_set(m.username, pw or None)
    try:
        client.connect(m.host, m.port, keepalive=10)
        client.loop_start()
        info = client.publish(topic, payload, qos=1)
        info.wait_for_publish(timeout=5)
        ok = info.is_published()
    except (OSError, ValueError) as e:
        raise SmartHomeError("Tidak bisa terhubung ke broker MQTT") from e
    finally:
        client.loop_stop()
        client.disconnect()
    if not ok:
        raise SmartHomeError("Perintah MQTT tidak terkirim")


def control(cfg: Config, name: str, action: str, brightness: int | None = None) -> str:
    require_enabled(cfg)
    key, dev = resolve(cfg, name)
    if action not in {"on", "off", "toggle"}:
        raise SmartHomeError("Aksi harus on, off, atau toggle")
    if dev.type == "mqtt":
        if not dev.topic or action == "toggle":
            raise SmartHomeError(f"{key} (MQTT) hanya mendukung on dan off dan butuh topic")
        _mqtt_publish(cfg, dev.topic, dev.on if action == "on" else dev.off)
    else:
        entity = _check_entity(dev.entity)
        domain = entity.split(".")[0]
        service = {"on": "turn_on", "off": "turn_off", "toggle": "toggle"}[action]
        if domain == "scene":
            service = "turn_on"
        body: dict = {"entity_id": entity}
        if brightness is not None and domain == "light" and action == "on":
            body["brightness_pct"] = max(1, min(100, brightness))
        _ha_request(cfg, "POST", f"/api/services/{domain}/{service}", body)
    label = {"on": "dinyalakan", "off": "dimatikan", "toggle": "dibalik"}[action]
    return f"{key} sudah {label}"


def state(cfg: Config, name: str) -> str:
    require_enabled(cfg)
    key, dev = resolve(cfg, name)
    if dev.type != "ha":
        raise SmartHomeError(f"Status {key} tidak tersedia (perangkat MQTT)")
    entity = _check_entity(dev.entity)
    data = _ha_request(cfg, "GET", f"/api/states/{entity}")
    st = data.get("state", "tidak diketahui") if isinstance(data, dict) else "tidak diketahui"
    return f"{key} sedang {({'on': 'menyala', 'off': 'mati'}).get(st, st)}"
