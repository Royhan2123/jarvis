"""Registry tool: decorator @tool, skema JSON untuk Ollama, validasi pydantic, level risiko.

Aturan keamanan: tidak ada tool shell bebas di registry (shell hanya di jarvis/agent/, terjaga);
argumen SELALU divalidasi sebelum dieksekusi;
tool berisiko >= confirm_risk_level butuh konfirmasi eksplisit (confirmed=True).
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from jarvis.brain.memory import Memory
from jarvis.config import Config
from jarvis.platform import get_adapter
from jarvis.platform.base import PlatformAdapter, PlatformError


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_ORDER = {Risk.LOW: 0, Risk.MEDIUM: 1, Risk.HIGH: 2}


class ToolError(RuntimeError):
    """Tool gagal; pesan aman untuk dibacakan."""


class ConfirmationRequired(ToolError):
    def __init__(self, name: str, risk: Risk) -> None:
        super().__init__(f"Tool '{name}' berisiko {risk.value} dan butuh konfirmasi")
        self.name, self.risk = name, risk


class Context:
    """Dependensi bersama tool: adapter OS + config. Diatur sekali saat startup (atau di test)."""

    def __init__(self) -> None:
        self._adapter: PlatformAdapter | None = None
        self._memory: Memory | None = None
        self.cfg: Config = Config()

    @property
    def adapter(self) -> PlatformAdapter:
        if self._adapter is None:
            self._adapter = get_adapter(self.cfg)
        return self._adapter

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = Memory(self.cfg.memory)
        return self._memory

    def configure(
        self, adapter: PlatformAdapter | None, cfg: Config, memory: Memory | None = None
    ) -> None:
        self._adapter, self.cfg, self._memory = adapter, cfg, memory


context = Context()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: Risk
    category: str
    func: Callable[..., str]
    params: type[BaseModel]

    def schema(self) -> dict[str, Any]:
        js = self.params.model_json_schema()
        for prop in js.get("properties", {}).values():
            prop.pop("title", None)
        js.pop("title", None)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": js},
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' sudah terdaftar")
        self._tools[spec.name] = spec

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def recategorize(self, name: str, category: str) -> None:
        if (spec := self._tools.get(name)) is not None:
            self._tools[name] = replace(spec, category=category)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self, categories: list[str] | None = None) -> list[dict[str, Any]]:
        return [
            t.schema()
            for t in self._tools.values()
            if categories is None or t.category in categories
        ]

    def call(self, name: str, args: dict[str, Any] | None = None, confirmed: bool = False) -> str:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolError(f"Tool '{name}' tidak dikenal")
        try:
            parsed = spec.params.model_validate(args or {})
        except ValidationError as e:
            raise ToolError(f"Argumen untuk '{name}' tidak valid: {_short(e)}") from e
        min_level = Risk(context.cfg.tools.confirm_risk_level)
        if _ORDER[spec.risk] >= _ORDER[min_level] and not confirmed:
            raise ConfirmationRequired(name, spec.risk)
        logger.info(f"tool {name}({parsed.model_dump()}) risk={spec.risk.value}")
        try:
            return spec.func(**parsed.model_dump())
        except PlatformError as e:
            raise ToolError(str(e)) from e
        except NotImplementedError as e:
            raise ToolError(str(e) or "Fitur ini belum didukung di sistem operasi ini") from e


def _short(e: ValidationError) -> str:
    err = e.errors()[0]
    loc = ".".join(str(x) for x in err["loc"]) or "argumen"
    return f"{loc}: {err['msg']}"


registry = ToolRegistry()


def tool(
    name: str, description: str, risk: str = "low", category: str = "system"
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Daftarkan fungsi sebagai tool. Skema argumen diturunkan dari type hint fungsi."""

    def deco(func: Callable[..., str]) -> Callable[..., str]:
        hints = typing.get_type_hints(func)
        fields: dict[str, Any] = {}
        for pname, p in inspect.signature(func).parameters.items():
            default = ... if p.default is inspect.Parameter.empty else p.default
            fields[pname] = (hints[pname], default)
        model = create_model(f"{name}_args", __config__=ConfigDict(extra="forbid"), **fields)
        registry.register(ToolSpec(name, description, Risk(risk), category, func, model))
        return func

    return deco


def load_tools(cfg: Config) -> None:
    """Impor modul tool yang aktif di config (modul yang belum ada dilewati)."""
    import importlib

    for cat in cfg.tools.enabled:
        try:
            importlib.import_module(f"jarvis.tools.{cat}")
        except ModuleNotFoundError as e:
            if e.name != f"jarvis.tools.{cat}":
                raise
            logger.debug(f"Kategori tool '{cat}' belum tersedia")
    from jarvis.tools.plugins import load_plugins

    load_plugins(cfg)
