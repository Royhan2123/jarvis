from __future__ import annotations

import pytest

from jarvis.config import Config
from jarvis.tools import plugins
from jarvis.tools.registry import ToolError, context, registry

GOOD = """
from jarvis.tools.registry import tool
KEYWORDS = ["sapa"]

@tool(name="plug_hello", description="Menyapa", risk="low")
def plug_hello(name: str) -> str:
    return f"Halo {name}"
"""


@pytest.fixture
def cfg(tmp_path, adapter):
    c = Config()
    c.tools.plugins.dir = str(tmp_path)
    context.configure(adapter, c, context.memory)
    yield c
    for n in [n for n in registry.names() if n.startswith("plug_")]:
        registry.unregister(n)
    plugins.LOADED.clear()
    plugins.PLUGIN_HINTS.clear()


def test_loads_plugin_and_registers_tool(cfg, tmp_path) -> None:
    (tmp_path / "hello.py").write_text(GOOD)
    assert plugins.load_plugins(cfg) == ["plug_hello"]
    assert registry.get("plug_hello").category == plugins.PLUGIN_CATEGORY
    assert registry.call("plug_hello", {"name": "Bos"}) == "Halo Bos"
    assert plugins.PLUGIN_HINTS[("sapa",)] == ("plug_hello",)


def test_args_are_validated(cfg, tmp_path) -> None:
    (tmp_path / "hello.py").write_text(GOOD)
    plugins.load_plugins(cfg)
    with pytest.raises(ToolError):
        registry.call("plug_hello", {"nama": "x"})


def test_broken_plugin_is_skipped_and_rolled_back(cfg, tmp_path) -> None:
    (tmp_path / "bad.py").write_text(
        GOOD.replace("plug_hello", "plug_bad") + "\nraise RuntimeError('x')\n"
    )
    (tmp_path / "ok.py").write_text(GOOD)
    assert plugins.load_plugins(cfg) == ["plug_hello"]
    assert registry.get("plug_bad") is None


def test_name_clash_with_builtin_is_rejected(cfg, tmp_path) -> None:
    (tmp_path / "clash.py").write_text(GOOD.replace("plug_hello", "get_time"))
    assert plugins.load_plugins(cfg) == []
    assert registry.get("get_time").category != plugins.PLUGIN_CATEGORY


def test_allowlist_and_disable(cfg, tmp_path) -> None:
    (tmp_path / "hello.py").write_text(GOOD)
    cfg.tools.plugins.allowed = ["lain"]
    assert plugins.load_plugins(cfg) == []
    cfg.tools.plugins.allowed = []
    cfg.tools.plugins.enabled = False
    assert plugins.load_plugins(cfg) == []


def test_ignores_underscore_files_and_missing_dir(cfg, tmp_path) -> None:
    (tmp_path / "_private.py").write_text(GOOD)
    assert plugins.load_plugins(cfg) == []
    cfg.tools.plugins.dir = str(tmp_path / "tidak_ada")
    assert plugins.load_plugins(cfg) == []
