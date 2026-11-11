# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/id/1.1.0/). Versi mengikuti `pyproject.toml`.

## [0.2.0] — 2026-11-11

### Ditambahkan
- **Agen kerja** (`jarvis/agent/`): mengerjakan tugas bertahap di komputer (baca/cari/ubah file, jalankan
  perintah) dengan konfirmasi tiap langkah, blokir keras (`sudo`, hapus massal, unduh-lalu-jalankan, path
  rahasia), folder kerja `workspace.folders` (boleh seluruh home), dan suara pengisi (`agent.narrate`).
- **Izin agen bisa disetel**: lewat suara ("jangan tanya lagi untuk ubah file"), dashboard, atau
  `agent.confirm_actions`. Melonggarkan butuh konfirmasi "ya" dan tidak pernah ditawarkan ke LLM.
- **Suara Fish Audio** (online, opsional) per gender dengan cadangan Piper.
- **Bahasa Inggris**: deteksi Indonesia/Inggris per ucapan (`stt.language: auto`), perintah dasar dan
  lanjutan dalam Inggris, tool `translate` (LLM lokal) untuk terjemah lisan, suara balasan Inggris offline
  (Piper `en_US`) dipilih per kalimat.
- **API lokal** (`ui.api`, `/v1`): ask, agen dengan SSE dan konfirmasi, status suara langsung
  (`/v1/state`, `/v1/state/events`), jawaban kartu izin (`/v1/approvals/{id}`); token Bearer + cek Host.
- **Sambungan Isla Desk**: notifikasi ke pulau, batang suara saat Jarvis mendengar/berpikir/bicara
  (`island.show_voice`), kartu izin Setuju/Tolak (`island.approvals`), dan penyedia AI "Jarvis" di Isla.
- **Folder kerja** (baca/ubah kode dengan cadangan `.jarvis-bak`) dan draf WhatsApp tanpa kirim otomatis.
- `docs/UJI_MANUAL.md`: daftar uji yang butuh mikrofon, akun, atau perangkat asli.

### Diubah
- Jawaban dibuat lebih singkat; agen dipanaskan di awal; konfirmasi agen tidak bisa dipotong gema.
- Benchmark Mac Intel i9: mulai bicara ±4,3 dtk (STT `small` 2,5 dtk; +0,6 dtk bila `language: auto`).

### Diketahui
- Belum diuji lewat mikrofon asli: deteksi bahasa, konfirmasi "ya", Google Calendar/Gmail, WhatsApp,
  Smart Home, RAG lewat mic. Lihat `docs/UJI_MANUAL.md`.
- Jarvis di Windows/Linux baru dibuktikan oleh tes unit di CI.
- Terjemahan Jawa/Sunda dari Qwen belum bagus.
