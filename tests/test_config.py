from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from jarvis.config import load_config


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg.llm.fast_model == "qwen3.5:4b"
    assert cfg.general.offline_only is True


def test_repo_config_is_valid() -> None:
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.llm.num_ctx == 2048


def test_override(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("llm:\n  num_ctx: 2048\n", encoding="utf-8")
    assert load_config(p).llm.num_ctx == 2048


def test_unknown_key_rejected(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("llm:\n  typo_key: 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(p)
