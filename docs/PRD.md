# PRD — Jarvis: Asisten Suara AI Offline

| | |
|---|---|
| **Versi dokumen** | 1.0 |
| **Status** | Draft |
| **Platform** | macOS, Windows, Linux |
| **Owner** | Product Owner |
| **Tanggal** | November 2026 |

---

## 1. Ringkasan Produk

Jarvis adalah asisten suara desktop yang berjalan **sepenuhnya lokal** (offline). Pengguna
memanggil dengan wake word "Hey Jarvis", berbicara dalam bahasa Indonesia (atau Inggris),
lalu Jarvis memahami maksudnya, menjalankan aksi di komputer, dan menjawab dengan suara.

**Positioning:** "Siri/Alexa untuk komputer, tapi privat, gratis, open source, dan jalan di semua OS."

---

## 2. Masalah yang Diselesaikan

1. Asisten suara yang ada (Siri, Cortana, Google Assistant) **mengirim data ke cloud** → masalah privasi.
2. Asisten bawaan OS **terbatas** dan tidak bisa dikustomisasi.
3. Tidak ada asisten suara desktop yang **paham bahasa Indonesia dengan baik** dan bisa jalan offline.
4. Asisten berbasis ChatGPT/API **butuh biaya bulanan** dan internet.

---

## 3. Target Pengguna

| Persona | Deskripsi | Kebutuhan Utama |
|---|---|---|
| **Developer / Power User** | Programmer, kerja di depan komputer 8+ jam | Kontrol cepat tanpa pindah tangan dari keyboard, otomasi |
| **Content Creator** | YouTuber, editor video | Kontrol musik/aplikasi saat tangan sibuk |
| **Privacy-Conscious User** | Pengguna yang peduli data | Asisten yang tidak kirim data ke server |
| **Pengguna Disabilitas** | Keterbatasan motorik | Mengoperasikan komputer dengan suara |

---

## 4. Tujuan & Metrik Sukses

| Tujuan | Metrik | Target MVP |
|---|---|---|
| Responsif | Latensi dari selesai bicara → mulai jawab (perintah sederhana) | ≤ 2 detik |
| Responsif | Latensi untuk pertanyaan umum (LLM) | ≤ 5 detik (CPU) |
| Akurat | Word Error Rate STT bahasa Indonesia | ≤ 15% |
| Akurat | Perintah dijalankan dengan benar | ≥ 90% |
| Tidak mengganggu | False wake-up (terpanggil tanpa disengaja) | ≤ 1x per jam |
| Ringan | Pemakaian RAM saat idle | ≤ 6 GB |
| Ringan | CPU saat idle (menunggu wake word) | ≤ 5% |

---

## 5. Fitur

### 5.1 MVP (Wajib — P0)

| ID | Fitur | Deskripsi |
|---|---|---|
| F-01 | Wake word | Aktif saat mendengar "Hey Jarvis", bunyi notifikasi "ting" |
| F-02 | Speech-to-Text | Mengubah suara jadi teks (Indonesia & Inggris) |
| F-03 | Percakapan | Tanya-jawab umum dengan LLM lokal |
| F-04 | Text-to-Speech | Menjawab dengan suara bahasa Indonesia |
| F-05 | Buka/tutup aplikasi | "Buka Spotify", "Tutup Chrome" |
| F-06 | Kontrol volume | "Volume 30 persen", "Mute" |
| F-07 | Kontrol media | Play/pause, next, previous |
| F-08 | Buka website / cari Google | "Cari resep rendang" |
| F-09 | Info sistem | Jam, tanggal, baterai, pemakaian CPU/RAM |
| F-10 | Konfirmasi aksi berisiko | Aksi sensitif wajib konfirmasi "ya/tidak" |
| F-11 | System tray | Ikon di tray: status, mute mic, keluar |

### 5.2 v1.0 (Penting — P1)

| ID | Fitur | Deskripsi |
|---|---|---|
| F-12 | Baca layar | "Rangkum isi layar ini" (screenshot → model vision) |
| F-13 | Dikte / ketik teks | "Ketik: halo apa kabar" ke window aktif |
| F-14 | Memori | Ingat fakta pengguna ("nama saya Roy") & riwayat percakapan |
| F-15 | Timer & pengingat | "Ingatkan saya 10 menit lagi" |
| F-16 | Catatan | "Catat: beli kopi besok" → file Markdown lokal |
| F-17 | Router 2 otak | Otomatis pilih model 4B/9B sesuai kompleksitas |
| F-18 | Interupsi | Pengguna bisa memotong Jarvis yang sedang bicara |

### 5.3 v2.0 (Nice to have — P2)

| ID | Fitur | Deskripsi |
|---|---|---|
| F-19 | Plugin system | Developer bisa tambah tool sendiri (Python) |
| F-20 | Integrasi kalender & email | Google/Outlook (opsional, butuh internet) |
| F-21 | Smart home | Home Assistant / MQTT |
| F-22 | RAG dokumen pribadi | "Cari di dokumen saya tentang kontrak X" |
| F-23 | Custom wake word | Latih nama panggilan sendiri |
| F-24 | Dashboard web lokal | Lihat log, atur config, kelola plugin |

---

## 6. User Stories

1. **Sebagai** developer, **saya ingin** bilang "Hey Jarvis, buka VS Code dan Spotify" **agar** saya bisa mulai kerja tanpa klik-klik.
2. **Sebagai** pengguna, **saya ingin** bertanya "Apa bedanya RAM dan storage?" **agar** dapat jawaban cepat tanpa buka browser.
3. **Sebagai** pengguna, **saya ingin** Jarvis bertanya "Yakin?" sebelum mematikan komputer **agar** tidak terjadi kesalahan fatal.
4. **Sebagai** pengguna privat, **saya ingin** semua data diproses lokal **agar** percakapan saya tidak bocor.
5. **Sebagai** pengguna, **saya ingin** bilang "Rangkum layar ini" saat membaca artikel panjang **agar** hemat waktu.
6. **Sebagai** pengguna Windows/Linux, **saya ingin** pengalaman yang sama dengan pengguna Mac.

---

## 7. Alur Pengguna Utama

```
[Idle: dengar wake word]
      │ "Hey Jarvis"
      ▼
[Bunyi "ting" + ikon tray berubah jadi 🎙️]
      │ pengguna bicara
      ▼
[Deteksi selesai bicara (diam 0.8 detik)]
      │
      ▼
[STT → teks] ──► [Router] ──► perintah sederhana → Tool langsung
                     │
                     ├──► perintah/tanya ringan → Qwen 4B
                     └──► pertanyaan kompleks  → Qwen 9B
      │
      ▼
[Aksi berisiko?] ──ya──► "Yakin mau matikan komputer?" → tunggu "ya"
      │ tidak
      ▼
[Jalankan tool] → [TTS jawab] → kembali Idle
```

---

## 8. Kebutuhan Non-Fungsional

| Kategori | Kebutuhan |
|---|---|
| **Privasi** | Tidak ada data suara/teks dikirim ke internet (kecuali fitur yang eksplisit online & diaktifkan pengguna) |
| **Keamanan** | Tool hanya dari whitelist; perintah shell bebas **dilarang** (kecuali agen kerja opt-in dengan konfirmasi tiap perintah); aksi destruktif wajib konfirmasi |
| **Kompatibilitas** | macOS 12+, Windows 10/11, Ubuntu 22.04+ / Fedora 39+ (X11 & Wayland) |
| **Performa** | Bisa jalan di CPU saja; otomatis pakai GPU (CUDA/Metal) jika tersedia |
| **Bahasa** | Bahasa Indonesia utama, Inggris sekunder, campuran (code-switching) didukung |
| **Reliabilitas** | Crash di satu modul (misal TTS) tidak mematikan seluruh aplikasi |
| **Konfigurasi** | Semua parameter di satu file `config.yaml` |
| **Log** | Log lokal di folder data pengguna, bisa dimatikan |

---

## 9. Kebutuhan Hardware

| Level | CPU | RAM | Storage | Model yang disarankan |
|---|---|---|---|---|
| Minimum | 4 core (i5 gen 8 / Ryzen 5) | 16 GB | 15 GB | Qwen3.5 4B saja |
| Rekomendasi | 8 core (i7/i9 / Ryzen 7) | 32 GB | 25 GB | Qwen3.5 4B + 9B |
| Optimal | Apple Silicon / GPU NVIDIA 8 GB+ | 32 GB+ | 50 GB | 4B + 9B (+ opsional Qwen 3.6) |

---

## 10. Di Luar Cakupan (Out of Scope)

- Aplikasi mobile (Android/iOS)
- Menjalankan perintah shell bebas dari ucapan
- Melatih model LLM dari nol
- Panggilan telepon / kirim SMS

---

## 11. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| LLM lambat di CPU | UX buruk | Router: perintah sederhana tidak lewat LLM; pakai 4B sebagai default |
| STT salah dengar | Aksi salah | Konfirmasi untuk aksi berisiko; tampilkan teks hasil STT di tray/notifikasi |
| Perbedaan API antar OS | Fitur tidak konsisten | Lapisan adapter per OS (`platform/`) + test di CI 3 OS |
| Wayland membatasi otomasi keyboard | Fitur "ketik" gagal di Linux | Fallback ke `ydotool` / clipboard |
| Prompt injection dari isi layar | Aksi tak diinginkan | Isi layar diperlakukan sebagai data, bukan instruksi; tool berisiko tetap butuh konfirmasi |

---

## 12. Kriteria Rilis MVP

- [ ] Semua fitur P0 berjalan di macOS, Windows, dan Linux
- [ ] Latensi perintah sederhana ≤ 2 detik di hardware rekomendasi
- [ ] Tidak ada request jaringan keluar saat mode offline (diverifikasi)
- [ ] Installer/package tersedia untuk 3 OS
- [ ] Dokumentasi SETUP.md teruji oleh 3 orang di 3 OS berbeda
