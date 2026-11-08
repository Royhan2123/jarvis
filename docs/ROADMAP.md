# Roadmap Jarvis

## Ringkasan

| Fase | Durasi | Hasil |
|---|---|---|
| **Fase 0 — Fondasi** | Minggu 1 | Repo, struktur, CI 3 OS, mode teks jalan |
| **Fase 1 — Pipeline Suara** | Minggu 2 | Wake word → STT → LLM → TTS jalan end-to-end |
| **Fase 2 — Tools & Platform** | Minggu 3 | Kontrol app, volume, media, web di 3 OS |
| **Fase 3 — MVP Polish** | Minggu 4 | Router, konfirmasi, tray, installer → **Rilis MVP v0.1** |
| **Fase 4 — v1.0** | Bulan 2 | Baca layar, ketik, memori, pengingat, interupsi |
| **Fase 5 — v2.0** | Bulan 3+ | Plugin, dashboard, RAG dokumen, smart home |

---

## Fase 0 — Fondasi (Minggu 1)

- [x] Init repo, `pyproject.toml`, `uv`, `ruff`, `pytest`
- [x] Struktur folder sesuai [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [x] `config.py` + `config.yaml` dengan validasi pydantic
- [x] Wrapper Ollama (`brain/llm.py`) + system prompt
- [x] **Mode teks** (`python -m jarvis --text`): ketik pertanyaan → jawaban LLM di terminal
- [x] GitHub Actions: lint + test di `macos-latest`, `windows-latest`, `ubuntu-latest`

**Definition of Done:** bisa ngobrol dengan Qwen 4B lewat terminal di 3 OS.

---

## Fase 1 — Pipeline Suara (Minggu 2)

- [x] `audio/stream.py`: input mic 16 kHz, ring buffer
- [x] `audio/wakeword.py`: openWakeWord `hey_jarvis` (ONNX)
- [x] `audio/vad.py`: Silero VAD, deteksi selesai bicara
- [x] `stt/whisper.py`: faster-whisper `small`, int8, bahasa Indonesia
- [x] `tts/piper.py` + `tts/fallback.py`
- [x] `app.py`: state machine IDLE → LISTENING → THINKING → SPEAKING
- [x] Log latensi tiap tahap (mode DEBUG)
- [x] `setup.py`: `check`, `list-mics`, `download-voice`

**Definition of Done:** "Hey Jarvis, apa ibu kota Jepang?" → dijawab dengan suara di 3 OS, total latensi ≤ 5 detik di CPU.

> Status: Mac Intel i9 ✅ mulai bicara ±4,5 detik (`uv run python -m jarvis.bench`: STT 1,6 + LLM kalimat pertama 2,6 + TTS 0,2). Windows & Linux belum diuji → belum dicentang.

---

## Fase 2 — Tools & Platform (Minggu 3)

- [x] `tools/registry.py`: decorator `@tool`, schema JSON untuk Ollama, level risk
- [x] `platform/base.py` + `macos.py`, `windows.py`, `linux.py`
- [x] Tools: `open_app`, `close_app`, `set_volume`, `mute`, `media`, `open_url`, `web_search`, `get_time`, `system_info`, `lock_screen`
- [x] Unit test tool dengan adapter palsu (mock)
- [ ] Uji manual di 3 OS (checklist di [`COMMANDS.md`](COMMANDS.md))

> Status: unit test lulus & uji manual di Mac OK; Windows/Linux belum diuji (lihat checklist di COMMANDS.md §4).

**Definition of Done:** semua tool P0 jalan di Mac, Windows, Linux (X11 + Wayland).

---

## Fase 3 — MVP Polish (Minggu 4)

- [x] `brain/rules.py`: Tier 0 regex + normalisasi teks
- [x] `brain/router.py`: rule → 4B → 9B + tool `escalate`
- [x] Alur konfirmasi untuk tool risk `high`
- [x] `ui/tray.py`: ikon state, toggle mic, buka config, keluar
- [x] Bunyi notifikasi (ting / selesai / error)
- [ ] Build PyInstaller 3 OS di CI, upload ke GitHub Releases
- [ ] Uji dengan 3 pengguna nyata, perbaiki SETUP.md

> Status: kode & unit test selesai (106 test); alur suara (aturan, konfirmasi, tray) dikonfirmasi berhasil oleh pengguna di Mac. Build lokal PyInstaller di Mac OK (`dist/Jarvis.app` ±385 MB; `--check`, mode teks, mode suara jalan; muat pertama ±75 detik). Tier 2 diuji dengan Qwen 9B asli (token pertama ±6 s, jawaban ±13 s). Belum: `release.yml` belum pernah jalan di GitHub (build Windows/Linux/Intel/ARM + rilis), belum diuji 3 pengguna nyata.

**🚀 Rilis MVP v0.1**

---

## Fase 4 — v1.0 (Bulan 2)

- [ ] `read_screen` dengan vision model
- [ ] `type_text` (termasuk fallback Wayland & clipboard)
- [x] Memori SQLite: fakta pengguna + riwayat percakapan
- [x] Catatan & pengingat (scheduler internal)
- [ ] **Interupsi**: wake word / "berhenti" saat Jarvis bicara
- [x] Streaming: TTS mulai bicara saat kalimat pertama LLM selesai (latensi terasa jauh lebih cepat)
- [ ] Benchmark & tuning latensi di hardware minimum

> Status: kode + 127 unit test selesai. **Belum terverifikasi sungguhan:** `read_screen` (perlu izin Screen
> Recording; tanpa izin macOS hanya memberi wallpaper; vision 4B ±56 s di CPU), `type_text` (perlu izin
> Accessibility; belum diuji mengetik), interupsi (tanpa peredam gema, segmen panjang diabaikan), dan
> benchmark di hardware minimum (hanya ada Mac i9).

**🚀 Rilis v1.0**

---

## Fase 5 — v2.0 (Bulan 3+)

- [ ] Plugin system (folder `plugins/`, auto-load tool baru)
- [ ] Dashboard web lokal (FastAPI): log, config, plugin
- [ ] RAG dokumen pribadi (embedding lokal + vector DB)
- [ ] Integrasi opsional online: Google Calendar, Gmail, cuaca
- [ ] Smart home: Home Assistant / MQTT
- [ ] Custom wake word (latih nama panggilan sendiri)
- [ ] Multi-bahasa daerah (Jawa/Sunda) — eksperimen fine-tune

---

## Ide Monetisasi (opsional)

| Model | Deskripsi |
|---|---|
| **Open core** | Versi dasar gratis & open source; plugin premium (kalender, email, CRM) berbayar |
| **Jarvis for Business** | Versi kantor: integrasi tools internal, deploy massal, support |
| **Marketplace plugin** | Developer jual plugin, platform ambil komisi |
| **Custom voice / wake word** | Jasa suara & nama panggilan custom untuk brand |
