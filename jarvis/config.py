"""Load & validasi config.yaml (pydantic). Satu-satunya pintu baca config."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneralConfig(_Section):
    name: str = "Jarvis"
    user_title: str = "Bos"
    language: Literal["id", "en", "auto"] = "id"
    log_level: Literal["DEBUG", "INFO", "WARNING"] = "INFO"
    offline_only: bool = True


class LLMConfig(_Section):
    host: str = "http://localhost:11434"
    fast_model: str = "qwen3.5:4b"
    smart_model: str = "qwen3.5:9b"
    vision_model: str = "qwen3.5:4b"
    temperature: float = 0.3
    top_p: float = 0.8
    top_k: int = 20
    num_ctx: int = 4096
    num_predict: int = 200
    num_thread: int = 8
    keep_alive: int | str = -1
    think: bool = False
    history_turns: int = 6


class RouterConfig(_Section):
    enable_rules: bool = True
    enable_smart_model: bool = True
    complex_min_words: int = 25
    complex_keywords: list[str] = [
        "jelaskan", "analisis", "bandingkan", "kenapa", "mengapa", "buatkan", "rangkum",
    ]  # fmt: skip
    preload_smart_model: bool = False


class TTSConfig(_Section):
    engine: Literal["piper", "system", "edge"] = "piper"
    gender: Literal["male", "female"] = "male"
    max_spoken_chars: int = 400


class MemoryConfig(_Section):
    enabled: bool = True
    save_conversations: bool = True
    retention_days: int = 30


class Config(_Section):
    general: GeneralConfig = GeneralConfig()
    llm: LLMConfig = LLMConfig()
    router: RouterConfig = RouterConfig()
    tts: TTSConfig = TTSConfig()
    memory: MemoryConfig = MemoryConfig()


def load_config(path: str | Path = "config.yaml") -> Config:
    """Baca YAML; file tidak ada → default. Nilai salah → ValidationError dengan pesan jelas."""
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None
    return Config.model_validate(data or {})
