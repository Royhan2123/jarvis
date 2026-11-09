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

## Status Definition of Done (per 2026-11-09)

Jujur per fase: ✅ terbukti di mesin dev (Mac Intel i9) · 🟡 sebagian · ❌ belum.

| Fase | Definition of Done | Status | Yang masih kurang |
|---|---|---|---|
| 0 | Ngobrol dengan Qwen 4B lewat terminal di 3 OS | 🟡 Mac ✅; CI hijau di 3 OS (unit test) | Ngobrol sungguhan dengan Ollama di Windows/Linux belum diuji |
| 1 | Panggil → jawab dengan suara di 3 OS, ≤ 5 s | 🟡 Mac ✅ (±4,5 s sederhana; 8–13 s jika CPU berebut) | Windows/Linux; kata panggil sekarang "Hello" (bukan "Hey Jarvis") |
| 2 | Semua tool P0 jalan di Mac, Windows, Linux | 🟡 Mac ✅ | Windows/Linux (X11 + Wayland) belum diuji, checklist di COMMANDS.md §4 |
| 3 | MVP: router, konfirmasi, tray, installer | 🟡 Mac ✅; rilis v0.1.0 terbit (4 target) | Installer Windows/Linux/ARM belum pernah dijalankan; belum diuji 3 pengguna nyata |
| 4 | Baca layar, ketik, memori, pengingat, interupsi | 🟡 memori, catatan, pengingat, streaming, interupsi ✅ | `read_screen` & `type_text` butuh izin macOS; benchmark hardware minimum |
| 5 | Plugin, dashboard, RAG, online, smart home, wake word kustom | 🟡 kode + tes ✅ | Calendar/Gmail (butuh akun Google), Home Assistant/MQTT (butuh perangkat), RAG lewat mic, bahasa daerah (hanya dikaji) |

Rilis (v0.1, v1.0, v2.0) belum dibuat: tidak ada push atau tag ke remote tanpa izin.

---

## Fase 0 — Fondasi (Minggu 1)

- [x] Init repo, `pyproject.toml`, `uv`, `ruff`, `pytest`
- [x] Struktur folder sesuai [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [x] `config.py` + `config.yaml` dengan validasi pydantic
- [x] Wrapper Ollama (`brain/llm.py`) + system prompt
- [x] **Mode teks** (`python -m jarvis --text`): ketik pertanyaan → jawaban LLM di terminal
- [x] GitHub Actions: lint + test di `macos-latest`, `windows-latest`, `ubuntu-latest` (hijau di ketiganya sejak 2026-11-09; unit test, bukan uji manual)

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
- [x] Build PyInstaller 3 OS di CI, upload ke GitHub Releases (v0.1.0: Windows, Linux, macOS Intel & ARM terbit; hanya build yang diverifikasi, belum dijalankan di Windows/Linux/ARM)
- [ ] Uji dengan 3 pengguna nyata, perbaiki SETUP.md

> Status: kode & unit test selesai (106 test); alur suara (aturan, konfirmasi, tray) dikonfirmasi berhasil oleh pengguna di Mac. Build lokal PyInstaller di Mac OK (`dist/Jarvis.app` ±385 MB; `--check`, mode teks, mode suara jalan; muat pertama ±75 detik). Tier 2 diuji dengan Qwen 9B asli (token pertama ±6 s, jawaban ±13 s). Belum: `release.yml` belum pernah jalan di GitHub (build Windows/Linux/Intel/ARM + rilis), belum diuji 3 pengguna nyata.

**🚀 Rilis MVP v0.1**

---

## Fase 4 — v1.0 (Bulan 2)

- [ ] `read_screen` dengan vision model
- [ ] `type_text` (termasuk fallback Wayland & clipboard)
- [x] Memori SQLite: fakta pengguna + riwayat percakapan
- [x] Catatan & pengingat (scheduler internal)
- [x] **Interupsi**: wake word / "berhenti" saat Jarvis bicara (terbukti di Mac: ucapan "Hello" memotong jawaban; tanpa peredam gema, segmen panjang diabaikan)
- [x] Streaming: TTS mulai bicara saat kalimat pertama LLM selesai (latensi terasa jauh lebih cepat)
- [ ] Benchmark & tuning latensi di hardware minimum

> Status: kode + unit test selesai; interupsi terbukti live. **Belum terverifikasi sungguhan:** `read_screen`
> (perlu izin Screen Recording; tanpa izin macOS hanya memberi wallpaper; vision 4B ±56 s di CPU),
> `type_text` (perlu izin Accessibility; belum diuji mengetik), dan benchmark di hardware minimum
> (hanya ada Mac i9).

**🚀 Rilis v1.0**

---

## Fase 5 — v2.0 (Bulan 3+)

- [x] Plugin system (folder `plugins/`, auto-load tool baru)
- [x] Dashboard web lokal (FastAPI): log, config, plugin
- [x] RAG dokumen pribadi (embedding lokal via Ollama + SQLite/numpy; diuji dengan qwen3-embedding:0.6b: indeks 3 dokumen 3,7 s, cari 0,05 s; pipeline Jarvis diuji dengan teks: jawaban dari kutipan dokumen benar; lewat mic terganggu salah dengar)
- [x] Integrasi opsional online: Google Calendar, Gmail, cuaca (cuaca diuji asli lewat suara; Calendar/Gmail diuji dengan mock, belum dengan akun Google)
- [x] Smart home: Home Assistant / MQTT (diuji dengan server HA palsu lokal; belum dengan Home Assistant/broker asli)
- [x] Custom wake word (nama panggilan sendiri lewat `wakeword.phrases`, uji dengan `setup test-wake`)
- [x] Folder kerja: baca & ubah kode dengan konfirmasi suara, draf WhatsApp (tambahan di luar roadmap awal; diuji dengan LLM asli pada file contoh)
- [ ] Multi-bahasa daerah (Jawa/Sunda) — eksperimen fine-tune (dikaji: lihat [`EXPERIMEN_BAHASA_DAERAH.md`](EXPERIMEN_BAHASA_DAERAH.md); belum dikerjakan)

---

## Ide Monetisasi (opsional)

| Model | Deskripsi |
|---|---|
| **Open core** | Versi dasar gratis & open source; plugin premium (kalender, email, CRM) berbayar |
| **Jarvis for Business** | Versi kantor: integrasi tools internal, deploy massal, support |
| **Marketplace plugin** | Developer jual plugin, platform ambil komisi |
| **Custom voice / wake word** | Jasa suara & nama panggilan custom untuk brand |
