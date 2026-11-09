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
    interruptible: bool = True


class WakewordConfig(_Section):
    engine: Literal["phrase", "openwakeword"] = "phrase"
    phrase: str = "hello"
    phrases: list[str] = []  # nama panggilan tambahan, mis. ["hey teman", "halo jarvis"]
    model: str = "hey_jarvis"
    threshold: float = 0.5
    cooldown_s: float = 2.0
    inference_framework: Literal["onnx", "tflite"] = "onnx"

    @property
    def all_phrases(self) -> list[str]:
        """Frasa utama + tambahan, tanpa duplikat; yang lebih panjang dicoba lebih dulu."""
        seen = dict.fromkeys(p.strip() for p in [self.phrase, *self.phrases] if p.strip())
        return sorted(seen, key=lambda p: -len(p.split()))


class VADConfig(_Section):
    threshold: float = 0.5
    silence_ms: int = 800
    max_record_s: int = 15
    listen_timeout_s: int = 8


class STTConfig(_Section):
    model: str = "small"
    wake_model: str = "base"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = "int8"
    language: str | None = "id"
    beam_size: int = 1
    # Kalimat alami, bukan daftar kata: daftar "buka, tutup" membuat "ibu kota" terdengar "buka ta"
    initial_prompt: str = (
        "Hello. Mengapa langit berwarna biru? Tolong catat bahwa saya punya janji dengan dokter. "
        "Aplikasi saya: Spotify, Chrome, dan VS Code."
    )
    wake_prompt: str = (
        "Hello, buka, tutup, volume, Spotify, Chrome, VS Code"  # khusus deteksi panggilan
    )
    min_logprob: float | None = -0.85  # keyakinan Whisper di bawah ini → minta diulang; null=mati
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


class FishConfig(_Section):
    """Fish Audio (ONLINE). Setiap kalimat yang diucapkan dikirim ke server Fish Audio."""

    voice_id: str | None = (
        None  # suara pria (tts.gender: male); reference_id dari fish.audio/app/discovery
    )
    female_voice_id: str | None = None  # suara wanita (tts.gender: female); kosong = pakai voice_id
    model: str = (
        "s2.1-pro-free"  # s2.1-pro-free = gratis (batas pemakaian wajar); s2.1-pro = berbayar
    )
    api_key_file: str | None = None  # file berisi API key; atau env FISH_API_KEY
    sample_rate: int = 24000
    speed: float = 1.0
    timeout_s: float = 15.0


class TTSConfig(_Section):
    engine: Literal["piper", "system", "edge", "fish"] = "piper"
    fish: FishConfig = FishConfig()
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


class RagConfig(_Section):
    enabled: bool = True
    folders: list[str] = []  # HANYA folder ini yang dibaca; kosong = fitur tidak aktif
    embed_model: str = "qwen3-embedding:0.6b"  # model embedding Ollama (lokal, multibahasa)
    chunk_chars: int = 800
    chunk_overlap: int = 100
    top_k: int = 3
    min_score: float = 0.4  # skor relevan 0.47–0.63; tidak relevan ≤ 0.35
    auto_context: bool = True  # pertanyaan ke LLM otomatis dibekali kutipan dokumen yang relevan
    max_file_mb: int = 5
    extensions: list[str] = [".txt", ".md", ".pdf"]


class OnlineConfig(_Section):
    """Fitur yang butuh internet. Semuanya hanya jalan jika general.offline_only = false."""

    default_city: str = "Jakarta"
    google_credentials: str | None = None  # file client_secret.json buatanmu (Google Cloud)
    google_token: str | None = None  # null = <folder data>/google_token.json
    calendar_id: str = "primary"
    max_items: int = 5


class DeviceConfig(_Section):
    type: Literal["ha", "mqtt"] = "ha"
    entity: str | None = None  # type ha: mis. "light.ruang_tamu" (domain: light/switch/fan/scene)
    topic: str | None = None  # type mqtt: topik perintah
    on: str = "ON"
    off: str = "OFF"


class HomeAssistantConfig(_Section):
    url: str = "http://homeassistant.local:8123"
    token_file: str | None = None  # file berisi long-lived token; atau env JARVIS_HA_TOKEN


class MQTTConfig(_Section):
    host: str | None = None
    port: int = 1883
    username: str | None = None
    password_file: str | None = None  # file berisi password; atau env JARVIS_MQTT_PASSWORD


class SmartHomeConfig(_Section):
    """Smart home. Default mati. Perangkat HANYA yang terdaftar di `devices` (nama → target)."""

    enabled: bool = False
    home_assistant: HomeAssistantConfig = HomeAssistantConfig()
    mqtt: MQTTConfig = MQTTConfig()
    devices: dict[str, DeviceConfig] = {}


class WorkspaceConfig(_Section):
    """Akses file untuk "baca/perbaiki kode". HANYA folder di `folders`; kosong = fitur mati."""

    folders: list[str] = []
    extensions: list[str] = [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
        ".html", ".css", ".sh", ".java", ".kt", ".dart", ".go", ".rs", ".c", ".cpp", ".h", ".swift",
    ]  # fmt: skip
    # nama file/folder yang tidak pernah dibaca atau diubah (cocok pada tiap bagian path)
    deny: list[str] = [
        ".git", ".ssh", ".env", ".aws", ".gnupg", "node_modules", ".venv",
        "id_rsa", "id_ed25519", "credentials", "secrets", "google_token.json",
    ]  # fmt: skip
    max_file_kb: int = 256
    context_chars: int = 3000  # potongan file yang dikirim ke LLM (num_ctx kecil di CPU)
    context_num_ctx: int = 4096


class AgentConfig(_Section):
    """Agen kerja: Jarvis memikirkan tugas bertahap (baca/ubah file, jalankan perintah shell).

    Butuh `workspace.folders`. Perintah shell & ubah file SELALU dikonfirmasi, kecuali perintah
    baca-saja yang ada di `readonly_commands` (bila `auto_read_only`).
    """

    enabled: bool = False
    model: str = ""  # kosong = llm.smart_model
    max_steps: int = 12
    num_ctx: int = 8192
    command_timeout_s: int = 60
    max_output_chars: int = 4000
    auto_read_only: bool = True
    readonly_commands: list[str] = [
        "ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "find", "tree", "which", "echo",
        "git status", "git diff", "git log", "git branch", "git show",
    ]  # fmt: skip


class MessagingConfig(_Section):
    """Draf pesan WhatsApp: nama panggilan → nomor (format internasional, mis. 62812...)."""

    contacts: dict[str, str] = {}


class AppsConfig(_Section):
    allowed: list[str] = []  # kosong = semua app boleh
    aliases: dict[str, str] = {
        "vs code": "Visual Studio Code",
        "browser": "Google Chrome",
        "musik": "Spotify",
        "kalkulator": "Calculator",
        "kalender": "Calendar",
    }


class PluginsConfig(_Section):
    enabled: bool = True
    dir: str | None = None  # null = <folder data pengguna>/plugins
    allowed: list[str] = []  # kosong = semua plugin di folder dimuat; isi nama file (tanpa .py)


class ToolsConfig(_Section):
    enabled: list[str] = [
        "system", "apps", "media", "web", "screen", "keyboard",
        "notes", "docs", "online", "smarthome", "workspace", "messaging", "agent",
    ]  # fmt: skip
    confirm_risk_level: Literal["low", "medium", "high"] = "high"
    confirm_timeout_s: int = 6
    apps: AppsConfig = AppsConfig()
    plugins: PluginsConfig = PluginsConfig()


class LinuxPlatformConfig(_Section):
    typing_backend: Literal["auto", "pynput", "ydotool", "xdotool"] = "auto"
    screenshot_backend: Literal["auto", "mss", "grim", "portal"] = "auto"
    volume_backend: Literal["auto", "pactl", "wpctl", "amixer"] = "auto"


class PlatformConfig(_Section):
    linux: LinuxPlatformConfig = LinuxPlatformConfig()


class DashboardConfig(_Section):
    enabled: bool = False
    port: int = 8765  # selalu hanya di 127.0.0.1


class UIConfig(_Section):
    tray: bool = True
    dashboard: DashboardConfig = DashboardConfig()


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
    rag: RagConfig = RagConfig()
    online: OnlineConfig = OnlineConfig()
    smarthome: SmartHomeConfig = SmartHomeConfig()
    workspace: WorkspaceConfig = WorkspaceConfig()
    agent: AgentConfig = AgentConfig()
    messaging: MessagingConfig = MessagingConfig()
    platform: PlatformConfig = PlatformConfig()
    ui: UIConfig = UIConfig()


def load_config(path: str | Path = "config.yaml") -> Config:
    """Baca YAML; file tidak ada → default. Nilai salah → ValidationError dengan pesan jelas."""
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None
    return Config.model_validate(data or {})
