# 🤖 Jarvis — Asisten Suara AI Offline (Cross-Platform)

Jarvis adalah asisten suara pribadi yang berjalan **100% offline** di komputer kamu.
Panggil dengan **"Hey Jarvis"**, kasih perintah pakai bahasa Indonesia, dan Jarvis akan
menjawab dengan suara sekaligus menjalankan aksi di komputer (buka aplikasi, atur volume,
baca layar, ketik teks, dll).

- ✅ Jalan di **macOS (Intel & Apple Silicon), Windows 10/11, dan Linux (Ubuntu/Fedora/Arch)**
- ✅ Tanpa internet, tanpa API berbayar, data tidak keluar dari komputer
- ✅ Otak AI: **Qwen3.5 4B** (cepat) + **Qwen3.5 9B** (pintar), open source Apache 2.0
- ✅ Bisa jalan hanya dengan CPU (minimal RAM 16 GB, direkomendasikan 32 GB)
- ✅ Bisa ngomong dengan **suara cowok atau cewek** (Piper offline / suara OS / Edge TTS online)

---

## 📚 Daftar Dokumen

| File | Isi |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Instruksi kerja untuk Claude Code: aturan kode, keamanan, cross-platform, cara kerja per fase |
| [`docs/PRD.md`](docs/PRD.md) | Product Requirements: tujuan, fitur, user story, target kualitas |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arsitektur sistem, alur data, sistem "2 otak", struktur folder |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Framework & library yang dipakai + alasannya, matriks per OS |
| [`docs/SETUP.md`](docs/SETUP.md) | Cara install & menjalankan di Mac, Windows, Linux |
| [`docs/CONFIG.md`](docs/CONFIG.md) | Semua parameter `config.yaml` beserta penjelasan & nilai rekomendasi |
| [`docs/COMMANDS.md`](docs/COMMANDS.md) | Daftar perintah suara & implementasi per OS |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Rencana pengembangan MVP → v1.0 → v2.0 |

---

## ⚡ Quick Start (ringkas)

```bash
# 1. Install Ollama dari https://ollama.com lalu download model
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b

# 2. Clone & install
git clone <repo-kamu>/jarvis.git
cd jarvis
uv sync            # atau: pip install -e .

# 3. Download suara Indonesia untuk TTS
python -m jarvis.setup download-voice

# 4. Jalankan
python -m jarvis
```

Lalu bilang: **"Hey Jarvis… buka browser"** 🎙️

Panduan lengkap per OS ada di [`docs/SETUP.md`](docs/SETUP.md).

---

## 🧠 Cara Kerja Singkat

```
🎙️ Mic → Wake Word → Rekam → Speech-to-Text → 🧠 Router → LLM / Tool → Text-to-Speech → 🔊
```

Detail di [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 📄 Lisensi

MIT (kode Jarvis). Model Qwen berlisensi Apache 2.0, Whisper MIT, Piper MIT.
