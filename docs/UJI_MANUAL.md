# Daftar Uji Manual (butuh pemilik)

Hal-hal ini tidak bisa dibuktikan oleh tes otomatis karena butuh mikrofon, akun, atau perangkat
asli. Jalankan satu per satu, centang yang berhasil, catat yang gagal (perintah + pesan di log).

Persiapan umum: `uv run python -m jarvis --check`, lalu `uv run python -m jarvis --listen`.
Tambahkan `--log-level DEBUG` bila perlu rincian log.

## 1. Konfirmasi suara "ya" (tool `high`)
Pastikan speaker tidak terlalu keras (gema bisa memotong konfirmasi).
- [ ] "Hello, matikan komputer" → Jarvis bertanya → ucapkan "tidak" → batal.
- [ ] Ulangi dengan perintah `high` yang aman (mis. "Hello, kunci layar"), jawab "ya" → aksi jalan. **Jangan** uji "matikan komputer" dengan "ya".
- [ ] Diam saja 8 detik → dianggap batal.
- [ ] "Hello, jangan tanya lagi untuk ubah file" → Jarvis minta "ya" → jawab "ya" → terlaksana.
- [ ] "Hello, selalu tanya untuk semuanya" → langsung berlaku tanpa konfirmasi.

## 2. Agen kerja lewat suara
- [ ] "Hello, kerjakan: buat file catatan.txt di folder percobaan berisi halo" → konfirmasi → file terbentuk.
- [ ] Suara pengisi (`agent.narrate`) terdengar saat agen bekerja, dan tidak menabrak jawaban akhir.

## 3. Google Calendar & Gmail (online)
1. Buat OAuth client jenis **Desktop** di Google Cloud, unduh `client_secret.json`.
2. Isi `online.google_credentials` di `config.yaml`, set `general.offline_only: false`.
3. Login pertama (browser terbuka, izinkan akses *baca saja*). Token disimpan 0600.
- [ ] "Hello, jadwal hari ini apa?"
- [ ] "Hello, ada email baru?"
- [ ] Kembalikan `offline_only: true` → kedua perintah menolak dengan sopan.

> **Status QA (2026-11-11, diuji Claude lewat suara sintetis + server palsu):** sudah terbukti: konfirmasi
> "ya"/"tidak" lewat mikrofon, agen membuat file, WhatsApp (URL wa.me benar, tanpa kirim otomatis),
> Smart Home terhadap server Home Assistant palsu (REST + Bearer; alamat internet ditolak saat offline),
> RAG dengan model embedding asli, Fish Inggris/Jepang. **Masih perlu Anda:** Google Calendar/Gmail (akun),
> Smart Home perangkat asli, WhatsApp kirim sungguhan, aksen suara Anda sendiri, Windows/Linux.

## 4. WhatsApp
Isi `messaging.contacts` (nama → nomor berawalan 62).
- [ ] "Hello, kirim WhatsApp ke Budi: sampai nanti" → Jarvis membuka chat terisi, **kamu yang menekan kirim**.

## 5. Smart Home asli
Isi `smarthome` (Home Assistant atau MQTT) dan `devices`, set `smarthome.enabled: true`.
- [ ] "Hello, nyalakan lampu ruang tamu" / "matikan".
- [ ] Perangkat yang tidak ada di `devices` ditolak.
- [ ] Alamat di luar jaringan rumah ditolak saat `offline_only: true`.

## 6. RAG lewat mikrofon
Isi `rag.folders` dengan folder berisi beberapa .md/.pdf, lalu mulai ulang Jarvis (pengindeksan otomatis).
- [ ] Tanyakan isi dokumen secara lisan → jawaban memuat kutipan yang benar.
- [ ] Tanyakan hal di luar dokumen → tidak mengarang dari dokumen.

## 7. Suara Fish Audio lewat pipeline penuh
- [ ] Jawaban pendek, jawaban panjang (beberapa kalimat), dan notifikasi semua bersuara Fish.
- [ ] Putuskan internet → otomatis jatuh ke Piper tanpa error.

## 8. Windows / Linux
CI hanya menjalankan tes unit. Di mesin asli:
- [ ] `uv sync --extra dev && uv run pytest -q`
- [ ] `uv run python -m jarvis --check`, lalu satu perintah suara sederhana (volume, buka aplikasi).

Selesai: laporkan hasilnya (lulus/gagal + log) agar bisa diperbaiki sebelum rilis.
