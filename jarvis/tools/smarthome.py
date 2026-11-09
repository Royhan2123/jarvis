"""Tool smart home: nyalakan/matikan perangkat terdaftar, cek statusnya."""

from __future__ import annotations

from jarvis import smarthome
from jarvis.tools.registry import ToolError, context, tool


def _wrap(fn, *args):  # noqa: ANN001, ANN002, ANN202
    try:
        return fn(context.cfg, *args)
    except smarthome.SmartHomeError as e:
        raise ToolError(str(e)) from e


@tool(
    name="device_control",
    description="Menyalakan atau mematikan perangkat rumah (lampu, kipas, saklar) berdasarkan nama",
    risk="medium",
    category="smarthome",
)
def device_control(name: str, action: str, brightness: int | None = None) -> str:
    return _wrap(smarthome.control, name, action, brightness)


@tool(
    name="device_state",
    description="Mengecek apakah perangkat rumah (lampu, kipas) sedang menyala",
    risk="low",
    category="smarthome",
)
def device_state(name: str) -> str:
    return _wrap(smarthome.state, name)


@tool(
    name="list_devices",
    description="Menyebutkan perangkat rumah yang bisa dikontrol",
    risk="low",
    category="smarthome",
)
def list_devices() -> str:
    _wrap(lambda cfg: smarthome.require_enabled(cfg))
    names = list(context.cfg.smarthome.devices)
    if not names:
        return "Belum ada perangkat terdaftar di config"
    return "Perangkat: " + ", ".join(names)
