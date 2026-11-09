# Arsitektur Jarvis

## 1. Gambaran Besar

```
┌──────────────────────────────────────────────────────────────────────┐
│                              JARVIS                                  │
│                                                                      │
│  🎙️ Mic                                                              │
│   │                                                                  │
│   ▼                                                                  │
│ ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌───────────────────┐  │
│ │ Wake Word│──►│ Recorder │──►│    STT    │──►│      ROUTER       │  │
│ │openWake- │   │  + VAD   │   │  faster-  │   │ (rule → 4B → 9B)  │  │
│ │  Word    │   │ (Silero) │   │  whisper  │   └─────────┬─────────┘  │
│ └──────────┘   └──────────┘   └───────────┘             │            │
│                                              ┌──────────┼─────────┐  │
│                                              ▼          ▼         ▼  │
│                                         ┌────────┐ ┌────────┐ ┌──────┐│
│                                         │ Rules  │ │Qwen 4B │ │Qwen  ││
│                                         │(regex) │ │(Ollama)│ │ 9B   ││
│                                         └───┬────┘ └───┬────┘ └──┬───┘│
│                                             └──────────┼─────────┘   │
│                                                        ▼             │
│                                         ┌──────────────────────────┐ │
│                                         │      TOOL REGISTRY       │ │
│                                         │ (whitelist + konfirmasi) │ │
│                                         └────────────┬─────────────┘ │
│                                                      ▼               │
│                                         ┌──────────────────────────┐ │
│                                         │    PLATFORM ADAPTER      │ │
│                                         │  macos / windows / linux │ │
│                                         └────────────┬─────────────┘ │
│                                                      ▼               │
│  🔊 Speaker ◄──────── TTS (Piper / fallback OS) ◄── Jawaban           │
│                                                                      │
│  Pendukung: Memory (SQLite) · Config (YAML) · Logger · System Tray   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. State Machine

Jarvis selalu berada di salah satu state berikut:

```
        ┌────────────────────────────────────────────┐
        ▼                                            │
   ┌─────────┐  wake word  ┌───────────┐  diam      ┌┴──────────┐
   │  IDLE   │────────────►│ LISTENING │──────────► │ THINKING  │
   └─────────┘             └───────────┘            └─────┬─────┘
        ▲                       │ timeout 8s              │
        │◄──────────────────────┘                         ▼
        │                                           ┌───────────┐
        │◄───────────── selesai bicara ─────────────│ SPEAKING  │
        │                                           └─────┬─────┘
        │                                                 │ butuh konfirmasi
        │                                           ┌─────▼──────┐
        └────────────── "tidak" / timeout ──────────│ CONFIRMING │
                                                    └────────────┘
```

- **IDLE**: hanya wake word yang aktif (CPU sangat rendah).
- **LISTENING**: merekam audio sampai VAD mendeteksi diam.
- **THINKING**: STT + Router + LLM + Tool.
- **SPEAKING**: TTS berjalan; wake word tetap aktif untuk **interupsi** (v1.0).
- **CONFIRMING**: menunggu jawaban "ya/tidak" untuk aksi berisiko.

---

## 3. Sistem "2 Otak" (Router)

Tujuan: **cepat untuk hal sederhana, pintar untuk hal rumit.**

```
Teks dari STT
    │
    ▼
[Tier 0: Rule Engine]  ── cocok regex? ──► jalankan tool langsung (≈ 0 ms LLM)
    │  contoh: "volume 30", "jam berapa", "buka spotify"
    │ tidak cocok
    ▼
[Tier 1: Qwen3.5 4B]   ── tool calling + jawaban singkat
    │  jika model memanggil tool "escalate" ATAU
    │  pertanyaan panjang (> 25 kata) ATAU kata kunci
    │  ("jelaskan", "analisis", "bandingkan", "kenapa")
    ▼
[Tier 2: Qwen3.5 9B]   ── reasoning lebih dalam, jawaban lebih lengkap
```

Pseudo-code:

```python
def route(text: str) -> Response:
    if cmd := rules.match(text):
        return tools.run(cmd)

    if is_complex(text):
        return brain.ask(text, model="qwen3.5:9b")

    resp = brain.ask(text, model="qwen3.5:4b", tools=registry.schemas())
    if resp.tool_call and resp.tool_call.name == "escalate":
        return brain.ask(text, model="qwen3.5:9b")
    return resp
```

---

## 4. Platform Adapter

Semua aksi yang berbeda antar OS dibungkus di satu interface:

```python
class PlatformAdapter(ABC):
    def open_app(self, name: str) -> None: ...
    def close_app(self, name: str) -> None: ...
    def set_volume(self, percent: int) -> None: ...
    def mute(self, on: bool) -> None: ...
    def media(self, action: Literal["play_pause", "next", "prev"]) -> None: ...
    def type_text(self, text: str) -> None: ...
    def screenshot(self) -> bytes: ...
    def notify(self, title: str, body: str) -> None: ...
    def lock_screen(self) -> None: ...
    def shutdown(self) -> None: ...
```

Dipilih otomatis saat startup:

```python
import sys

if sys.platform == "darwin":
    from .macos import MacAdapter as Adapter
elif sys.platform == "win32":
    from .windows import WindowsAdapter as Adapter
else:
    from .linux import LinuxAdapter as Adapter
```

Detail implementasi per OS ada di [`COMMANDS.md`](COMMANDS.md).

---

## 5. Tool Registry & Keamanan

Setiap tool didefinisikan dengan schema (untuk LLM tool calling) + level risiko:

```python
@tool(
    name="set_volume",
    description="Mengatur volume suara komputer",
    risk="low",
)
def set_volume(percent: int) -> str:
    adapter.set_volume(max(0, min(100, percent)))
    return f"Volume diatur ke {percent} persen"
```

| Risk | Perilaku | Contoh |
|---|---|---|
| `low` | Langsung jalan | volume, buka app, jam, cari web |
| `medium` | Jalan + notifikasi | ketik teks, tutup app |
| `high` | **Wajib konfirmasi suara** | shutdown, restart, hapus catatan, kirim email |

**Aturan keamanan wajib:**
1. Tidak ada tool `run_shell` bebas di registry. Pengecualian: agen kerja (`jarvis/agent/`, opt-in) — shell terjaga: konfirmasi tiap perintah, blokir keras, folder kerja saja.
2. Argumen tool divalidasi (pydantic) sebelum dieksekusi.
3. Nama aplikasi dicek terhadap daftar `apps.allowed` di config (opsional).
4. Teks dari layar / dokumen tidak boleh memicu tool `high` tanpa konfirmasi.

---

## 6. Memori

SQLite di folder data pengguna (`platformdirs`):

| Tabel | Isi |
|---|---|
| `conversations` | Riwayat percakapan (id, waktu, role, teks) |
| `facts` | Fakta tentang pengguna ("nama: Roy", "kota: Jakarta") |
| `notes` | Catatan dari perintah "catat …" |
| `reminders` | Pengingat terjadwal |

Konteks yang dikirim ke LLM = system prompt + facts + 6 pesan terakhir.

---

## 7. Concurrency

- **Thread audio** (callback `sounddevice`): mengisi ring buffer, tidak boleh blocking.
- **Thread wake word**: membaca buffer, memicu event.
- **Main loop (asyncio)**: state machine, STT, LLM, tools.
- **Thread TTS**: memutar audio agar bisa diinterupsi.
- **Thread tray** (`pystray`): UI status.

Komunikasi antar thread memakai `queue.Queue` / `asyncio.Queue`.

---

## 8. Struktur Folder

```
jarvis/
├── pyproject.toml
├── config.yaml                 # konfigurasi default
├── README.md
├── docs/                       # dokumen ini
├── jarvis/
│   ├── __main__.py             # entry point: python -m jarvis
│   ├── app.py                  # state machine & orkestrasi
│   ├── config.py               # load & validasi config (pydantic)
│   ├── setup.py                # CLI: download voice, cek dependensi
│   ├── audio/
│   │   ├── stream.py           # input mic (sounddevice)
│   │   ├── wakeword.py         # openWakeWord
│   │   ├── vad.py              # Silero VAD
│   │   └── sounds/             # ting.wav, done.wav
│   ├── stt/
│   │   └── whisper.py          # faster-whisper
│   ├── brain/
│   │   ├── router.py           # rule → 4B → 9B
│   │   ├── rules.py            # regex perintah cepat
│   │   ├── llm.py              # wrapper Ollama
│   │   ├── prompts.py          # system prompt
│   │   └── memory.py           # SQLite
│   ├── tools/
│   │   ├── registry.py         # decorator @tool, schema, risk
│   │   ├── system.py           # jam, baterai, cpu, shutdown
│   │   ├── apps.py             # buka/tutup app
│   │   ├── media.py            # volume, play/pause
│   │   ├── web.py              # buka url, cari google
│   │   ├── screen.py           # screenshot → vision
│   │   ├── keyboard.py         # ketik teks
│   │   └── notes.py            # catatan & pengingat
│   ├── platform/
│   │   ├── base.py             # PlatformAdapter (ABC)
│   │   ├── macos.py
│   │   ├── windows.py
│   │   └── linux.py
│   ├── tts/
│   │   ├── piper.py            # Piper TTS (utama)
│   │   └── fallback.py         # say / SAPI / espeak-ng
│   └── ui/
│       └── tray.py             # pystray
├── models/                     # suara Piper (.onnx) — di-gitignore
├── scripts/
│   ├── install_macos.sh
│   ├── install_linux.sh
│   └── install_windows.ps1
└── tests/
    ├── test_router.py
    ├── test_rules.py
    └── test_tools.py
```
