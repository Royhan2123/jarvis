---
name: next-phase
description: Kerjakan fase berikutnya (atau fase tertentu) dari docs/ROADMAP.md sampai Definition of Done terpenuhi.
argument-hint: "[nomor fase, opsional]"
disable-model-invocation: true
---

# Kerjakan Fase ROADMAP

Fase target: `$ARGUMENTS` (jika kosong, ambil fase pertama yang checklist-nya belum semua `[x]`).

## Langkah

1. Baca **hanya** bagian fase target di `docs/ROADMAP.md`. Jangan baca seluruh `docs/` sekaligus;
   buka dokumen lain hanya bagian yang relevan dengan item yang sedang dikerjakan.
2. Tulis rencana singkat (maks 10 baris): item, file yang akan dibuat/diubah, urutan.
3. Kerjakan item **satu per satu**. Untuk tiap item:
   - Implementasi + test minimal
   - `uv run ruff check . && uv run pytest -q`
   - Centang `[x]` item itu di `docs/ROADMAP.md`
   - Commit kecil (Conventional Commits)
4. Jika item butuh tool suara baru → pakai skill `add-tool`.
5. Sebelum commit yang menyentuh kode per-OS → pakai skill `cross-platform-review`.
6. Di akhir fase: cek "Definition of Done" fase tersebut dan jalankan skill `latency-check`
   jika fase menyentuh pipeline suara / LLM.

## Laporan akhir (singkat)

- ✅ Item selesai
- ⚠️ Item belum selesai + alasannya
- 🧪 Hasil test & latensi (jika diukur)
- 👉 Saran: "Ketik `/clear` lalu `/next-phase` untuk fase berikutnya"

## Aturan hemat token

- Jangan menampilkan ulang isi file besar; rujuk nama file + baris.
- Jangan membaca file di `models/`, `.venv/`, atau `uv.lock`.
- Gunakan `rg`/Grep untuk mencari, bukan membaca file utuh.
