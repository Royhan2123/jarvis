# Tech Stack Jarvis

Prinsip pemilihan: **open source, jalan offline, jalan di CPU, dan cross-platform (Mac/Windows/Linux).**

---

## 1. Bahasa & Tooling

| Komponen | Pilihan | Alasan |
|---|---|---|
| Bahasa | **Python 3.11 / 3.12** | Ekosistem AI terlengkap, semua library di bawah tersedia |
| Package manager | **uv** (alternatif: pip + venv) | Sangat cepat, lock file, sama di 3 OS |
| Validasi config | **pydantic** + **PyYAML** | Config aman & ada pesan error jelas |
| Folder data per OS | **platformdirs** | Otomatis pakai lokasi yang benar di tiap OS |
| Logging | **loguru** | Simpel, rotasi file otomatis |
| Testing | **pytest** | Standar |
| Lint/format | **ruff** | Cepat, satu tool |
| Packaging | **PyInstaller** | Buat `.app` / `.exe` / binary Linux |
| CI | **GitHub Actions** (matrix: macos, windows, ubuntu) | Test otomatis di 3 OS |

---

## 2. Pipeline Suara & AI

| Tahap | Library / Model | Ukuran | Catatan |
|---|---|---|---|
| Input audio | **sounddevice** (PortAudio) | – | Cross-platform, low latency |
| Wake word | **Frasa via Whisper** (`wakeword.engine: phrase`, default "hello" (juga hi/halo/hai/hey), bebas kata) atau **openWakeWord** `hey_jarvis` | ~1 MB | Pakai `inference_framework="onnx"` agar jalan di Windows & Mac |
| VAD | **Silero VAD** (ONNX, bawaan `faster_whisper.vad`) | ~2 MB | Deteksi kapan pengguna selesai bicara. Jangan pakai paket `silero-vad` (butuh PyTorch, bermasalah di Mac Intel) |
| Speech-to-Text | **faster-whisper** — model `small` | ~460 MB | CTranslate2, `int8` di CPU, CUDA otomatis jika ada GPU NVIDIA |
| LLM runtime | **Ollama** | – | Satu cara install di 3 OS, support tool calling |
| LLM cepat | **Qwen3.5 4B** (`qwen3.5:4b`) | ~3.4 GB | Default; ada vision untuk "baca layar" |
| LLM pintar | **Qwen3.5 9B** (`qwen3.5:9b`) | ~6.6 GB | Untuk pertanyaan kompleks |
| Text-to-Speech | **Piper** (`piper-tts`) — suara `id_ID-news_tts-medium` | ~60 MB | Natural, cepat di CPU |
| TTS fallback | `say` (Mac) / SAPI via **pyttsx3** (Windows) / **espeak-ng** (Linux) | – | Jika Piper gagal |
| TTS online (opsional) | **edge-tts** — `id-ID-ArdiNeural` (cowok) / `id-ID-GadisNeural` (cewek) | – | Paling natural, butuh internet; aktif hanya jika `offline_only: false` |
| Output audio | **sounddevice** | – | Bisa dihentikan di tengah (interupsi) |

### Kenapa model ini?

- **Qwen3.5** — open source Apache 2.0 (boleh komersial), multibahasa (bahasa Indonesia bagus), support tool calling & vision, ukuran kecil tapi performa tinggi.
- **faster-whisper `small`** — keseimbangan terbaik akurasi bahasa Indonesia vs kecepatan CPU. Naik ke `medium` jika punya GPU.
- **Piper** — satu-satunya TTS offline yang cepat, ringan, dan punya suara bahasa Indonesia.

### Alternatif model (opsional)

| Kebutuhan | Alternatif |
|---|---|
| Hardware lemah (RAM 8–16 GB) | `qwen3.5:2b` sebagai otak cepat |
| Punya GPU 24 GB / Apple Silicon 32 GB+ | `qwen3.6:27b` sebagai otak pintar |
| STT lebih akurat (dengan GPU) | faster-whisper `medium` / `large-v3-turbo` |

---

## 3. Kontrol Sistem (Cross-Platform)

| Fungsi | Library umum | macOS | Windows | Linux |
|---|---|---|---|---|
| Info sistem | **psutil** | ✅ | ✅ | ✅ |
| Screenshot | **mss** | ✅ | ✅ | ✅ (X11; Wayland via `grim`/portal) |
| Ketik teks | **pynput** | ✅ (izin Accessibility) | ✅ | ✅ X11 / `ydotool` di Wayland |
| Clipboard | **pyperclip** | ✅ | ✅ | ✅ (butuh `xclip`/`wl-clipboard`) |
| Buka URL | `webbrowser` (stdlib) | ✅ | ✅ | ✅ |
| Notifikasi | **plyer** / native | `osascript` | toast via **win11toast** | `notify-send` |
| Volume | per-OS | `osascript` | **pycaw** | `pactl` / `wpctl` |
| Media key | per-OS | AppleScript (Music/Spotify) | **pynput** media keys | `playerctl` (MPRIS) |
| Buka app | per-OS | `open -a` | `os.startfile` / Start Menu lookup | `gtk-launch` / `.desktop` |
| Tutup app | **psutil** + per-OS | AppleScript `quit` | `taskkill` | `pkill` / `wmctrl -c` |

---

## 4. UI

| Komponen | Pilihan | Catatan |
|---|---|---|
| System tray | **pystray** + **Pillow** | Ikon berubah sesuai state (idle/listening/thinking/speaking) |
| Dashboard (v2) | **FastAPI** + HTML sederhana di `localhost` | Lihat log, edit config, kelola plugin |

---

## 5. Penyimpanan

| Data | Teknologi | Lokasi |
|---|---|---|
| Memori & catatan | **SQLite** (stdlib `sqlite3`) | `platformdirs.user_data_dir("jarvis")` |
| Config | YAML | Root project / `user_config_dir` |
| Log | File teks (loguru) | `user_log_dir("jarvis")` |
| Model Whisper | Cache Hugging Face | `~/.cache/huggingface` |
| Model LLM | Dikelola Ollama | `~/.ollama/models` |

---

## 6. Dependensi (`pyproject.toml`)

```toml
[project]
name = "jarvis"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "sounddevice>=0.4",
  "numpy>=1.26",
  "openwakeword>=0.6",
  "onnxruntime>=1.17",
  "faster-whisper>=1.0",
  "ollama>=0.4",
  "piper-tts>=1.2",
  "pyttsx3>=2.90",
  "psutil>=5.9",
  "mss>=9.0",
  "pynput>=1.7",
  "pyperclip>=1.8",
  "pystray>=0.19",
  "Pillow>=10.0",
  "pydantic>=2.6",
  "pyyaml>=6.0",
  "platformdirs>=4.2",
  "loguru>=0.7",
  "pycaw>=20240210 ; sys_platform == 'win32'",
  "comtypes>=1.2 ; sys_platform == 'win32'",
  "win11toast>=0.34 ; sys_platform == 'win32'",
]

[project.optional-dependencies]
online = ["edge-tts>=6.1"]
dev = ["pytest>=8", "ruff>=0.4", "pyinstaller>=6.5"]

[project.scripts]
jarvis = "jarvis.__main__:main"
```

> Catatan: versi minimum di atas adalah titik awal. Jalankan `uv lock` untuk mengunci versi terbaru yang kompatibel.
