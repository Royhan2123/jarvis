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


class AudioConfig(_Section):
    input_device: int | str | None = None
    output_device: int | str | None = None
    sample_rate: int = 16000
    chunk_ms: int = 80
    sounds: bool = True


class WakewordConfig(_Section):
    engine: Literal["phrase", "openwakeword"] = "phrase"
    phrase: str = "hey teman"
    model: str = "hey_jarvis"
    threshold: float = 0.5
    cooldown_s: float = 2.0
    inference_framework: Literal["onnx", "tflite"] = "onnx"


class VADConfig(_Section):
    threshold: float = 0.5
    silence_ms: int = 800
    max_record_s: int = 15
    listen_timeout_s: int = 8


class STTConfig(_Section):
    model: str = "small"
    wake_model: str = "small"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = "int8"
    language: str | None = "id"
    beam_size: int = 1
    initial_prompt: str = "Hey teman, buka, tutup, volume, Spotify, Chrome, VS Code"
    cpu_threads: int = 6


class LLMConfig(_Section):
    host: str = "http://localhost:11434"
    fast_model: str = "qwen3.5:4b"
    smart_model: str = "qwen3.5:9b"
    vision_model: str = "qwen3.5:4b"
    temperature: float = 0.3
    top_p: float = 0.8
    top_k: int = 20
    num_ctx: int = 2048
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


class VoicePair(_Section):
    male: str | None = None
    female: str | None = None


class SystemVoices(_Section):
    macos: VoicePair = VoicePair(female="Damayanti")
    windows: VoicePair = VoicePair(male="Microsoft Andika")
    linux: VoicePair = VoicePair(male="id+m3", female="id+f3")


class TTSVoices(_Section):
    piper: VoicePair = VoicePair(male="id_ID-news_tts-medium", female="custom/jarvis_cewek.onnx")
    system: SystemVoices = SystemVoices()
    edge: VoicePair = VoicePair(male="id-ID-ArdiNeural", female="id-ID-GadisNeural")


class TTSConfig(_Section):
    engine: Literal["piper", "system", "edge"] = "piper"
    gender: Literal["male", "female"] = "male"
    voices: TTSVoices = TTSVoices()
    length_scale: float = 1.0
    noise_scale: float = 0.667
    volume: float = 1.0
    max_spoken_chars: int = 400


class MemoryConfig(_Section):
    enabled: bool = True
    save_conversations: bool = True
    retention_days: int = 30


class AppsConfig(_Section):
    allowed: list[str] = []  # kosong = semua app boleh
    aliases: dict[str, str] = {
        "vs code": "Visual Studio Code",
        "browser": "Google Chrome",
        "musik": "Spotify",
        "kalkulator": "Calculator",
        "kalender": "Calendar",
    }


class ToolsConfig(_Section):
    enabled: list[str] = ["system", "apps", "media", "web", "screen", "keyboard", "notes"]
    confirm_risk_level: Literal["low", "medium", "high"] = "high"
    confirm_timeout_s: int = 6
    apps: AppsConfig = AppsConfig()


class LinuxPlatformConfig(_Section):
    typing_backend: Literal["auto", "pynput", "ydotool", "xdotool"] = "auto"
    screenshot_backend: Literal["auto", "mss", "grim", "portal"] = "auto"
    volume_backend: Literal["auto", "pactl", "wpctl", "amixer"] = "auto"


class PlatformConfig(_Section):
    linux: LinuxPlatformConfig = LinuxPlatformConfig()


class UIConfig(_Section):
    tray: bool = True


class Config(_Section):
    general: GeneralConfig = GeneralConfig()
    audio: AudioConfig = AudioConfig()
    wakeword: WakewordConfig = WakewordConfig()
    vad: VADConfig = VADConfig()
    stt: STTConfig = STTConfig()
    llm: LLMConfig = LLMConfig()
    router: RouterConfig = RouterConfig()
    tts: TTSConfig = TTSConfig()
    tools: ToolsConfig = ToolsConfig()
    memory: MemoryConfig = MemoryConfig()
    platform: PlatformConfig = PlatformConfig()
    ui: UIConfig = UIConfig()


def load_config(path: str | Path = "config.yaml") -> Config:
    """Baca YAML; file tidak ada → default. Nilai salah → ValidationError dengan pesan jelas."""
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None
    return Config.model_validate(data or {})
