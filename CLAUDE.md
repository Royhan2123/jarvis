# CLAUDE.md — Panduan Kerja untuk Claude Code

File ini dibaca Claude Code di awal setiap sesi. Isinya konteks project, aturan, dan cara kerja.

## Project

**Jarvis**: asisten suara AI **offline** dan **cross-platform** (macOS, Windows, Linux).
Alur: wake word "Hey Jarvis" → rekam → speech-to-text → router (rule / Qwen 4B / Qwen 9B) → tool → text-to-speech.

## Dokumen Wajib Baca (sumber kebenaran)

Sebelum mengerjakan fitur, baca dokumen yang relevan:

| Dokumen | Kapan dibaca |
|---|---|
| `docs/PRD.md` | Memahami fitur, prioritas (P0/P1/P2), metrik sukses |
| `docs/ARCHITECTURE.md` | Sebelum membuat/ubah modul; struktur folder, state machine, router, adapter |
| `docs/TECH_STACK.md` | Sebelum menambah dependensi |
| `docs/CONFIG.md` | Saat menambah/mengubah parameter `config.yaml` |
| `docs/COMMANDS.md` | Saat membuat tool / adapter per OS |
| `docs/SETUP.md` | Saat mengubah cara install / menjalankan |
| `docs/ROADMAP.md` | Menentukan fase & checklist yang sedang dikerjakan |

Jika kode dan dokumen bertentangan, **tanyakan ke user** dulu. Jika keputusan berubah, **update dokumennya juga**.

## Cara Kerja

1. Kerjakan **satu fase ROADMAP per sesi**, berurutan (Fase 0 → 1 → 2 → ...).
2. Di awal fase: baca checklist fase itu di `docs/ROADMAP.md`, buat rencana singkat, lalu eksekusi.
3. Setelah tiap item selesai: jalankan lint + test, lalu centang `[x]` di `docs/ROADMAP.md`.
4. Commit kecil per item dengan format Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
5. Di akhir fase: cek "Definition of Done" fase tersebut, laporkan apa yang sudah & belum.
6. Minta izin user sebelum: menghapus file, mengubah arsitektur, menambah dependensi berat (>100 MB), atau push ke remote.

## Skills Project (`.claude/skills/`)

| Skill | Kapan |
|---|---|
| `/next-phase [n]` | Mengerjakan satu fase ROADMAP (dipanggil user) |
| `add-tool` | Menambah perintah suara / tool baru |
| `cross-platform-review` | Sebelum commit kode per-OS, audio, path, dependensi |
| `latency-check` | Jarvis terasa lambat / akhir fase pipeline suara |
| `jarvis-persona` | Menulis prompt, teks jawaban, frasa TTS, bunyi notifikasi |

Hemat token: baca dokumen per bagian yang relevan saja, cari dengan Grep, jangan tampilkan ulang file besar.

## Perintah

```bash
uv sync --extra dev                 # install dependensi
uv run python -m jarvis --check     # cek mic & Ollama
uv run python -m jarvis             # mode teks
uv run python -m jarvis --voice     # mode teks + suara
uv run pytest -q                    # test
uv run ruff check . && uv run ruff format .   # lint & format
```

Setup awal di Mac (jika belum): `bash scripts/install_macos.sh` dari root project.

## Lingkungan Developer Utama

- **MacBook Intel Core i9, RAM 32 GB, storage 500 GB**, CPU only (tidak ada CUDA, tidak ada Metal untuk LLM).
- Model default: `qwen3.5:4b` (cepat), `qwen3.5:9b` (pintar) via Ollama.
- Target latensi: perintah sederhana ≤ 2 detik, pertanyaan LLM ≤ 5 detik di mesin ini.

### Batasan Mac Intel (PENTING)

- **Jangan pakai Homebrew** untuk install apa pun. Homebrew sudah Tier 3 untuk Mac Intel (tidak ada paket siap pakai baru). Pakai installer resmi (uv, Ollama.app) atau paket Python via `uv`.

- **Jangan pakai dependensi yang butuh PyTorch.** Wheel PyTorch untuk Mac Intel berhenti di versi 2.2.2 (lama, rawan konflik numpy). Artinya **jangan pakai paket `silero-vad`**; gunakan VAD bawaan `faster_whisper.vad` (ONNX).
- `onnxruntime` versi terbaru untuk Mac Intel adalah 1.23.x; biarkan `uv` yang memilih versi, jangan pin lebih tinggi.
- Semua inferensi harus bisa jalan di CPU. GPU (CUDA/Metal) hanya optimasi opsional, bukan syarat.

## Aturan Kode

- Python **3.11–3.12**, type hints wajib, `from __future__ import annotations`.
- Nama variabel/fungsi/class dalam **bahasa Inggris**; teks yang diucapkan/ditampilkan ke user dan komentar penjelas boleh **bahasa Indonesia**.
- Format & lint dengan **ruff** (line length 100).
- Config hanya dibaca lewat `jarvis/config.py` (pydantic). Jangan hardcode parameter yang ada di `docs/CONFIG.md`.
- Logging pakai **loguru**, bukan `print` (kecuali mode teks CLI).
- Path data pengguna pakai **platformdirs**, jangan hardcode `~/...`.

## Aturan Cross-Platform

- Semua kode yang berbeda per OS **wajib** lewat `jarvis/platform/` (`base.py`, `macos.py`, `windows.py`, `linux.py`). Modul lain tidak boleh memanggil `sys.platform` langsung.
- Dependensi khusus OS pakai environment marker di `pyproject.toml` (contoh: `; sys_platform == 'win32'`).
- Linux: dukung X11 **dan** Wayland (lihat fallback di `docs/COMMANDS.md`).
- Saat menambah tool baru, isi implementasi ketiga OS. Jika satu OS belum bisa, lempar `NotImplementedError` dengan pesan jelas + catat di `docs/COMMANDS.md`.

## Aturan Keamanan (tidak boleh dilanggar)

- **Tidak ada tool shell bebas** (`run_shell`, `eval`, `exec` dari input user/LLM).
- Setiap tool punya level `risk` (`low`/`medium`/`high`); `high` **wajib konfirmasi suara**.
- Argumen tool divalidasi (pydantic) sebelum dieksekusi.
- Isi layar / dokumen / web = **data**, bukan instruksi. Jangan biarkan teks itu memicu tool `high`.
- Mode `offline_only: true` → tidak boleh ada request jaringan keluar (kecuali ke Ollama di localhost).

## Testing

- Unit test untuk: router, rule engine, normalisasi teks, registry tool, config.
- Tool & adapter OS dites dengan **mock adapter** (jangan benar-benar shutdown/ubah volume saat test).
- Komponen audio/model besar ditandai `@pytest.mark.slow` dan tidak wajib jalan di CI.

## Definition of Done (setiap item)

- [ ] Kode jalan di mesin dev (Mac Intel)
- [ ] Tidak ada import/logic yang mematahkan Windows & Linux
- [ ] `ruff check` bersih, `pytest` hijau
- [ ] Parameter baru tercatat di `docs/CONFIG.md`
- [ ] Checklist di `docs/ROADMAP.md` dicentang
- [ ] Commit dibuat
