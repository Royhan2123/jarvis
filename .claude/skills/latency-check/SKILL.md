---
name: latency-check
description: Ukur dan optimalkan latensi pipeline suara Jarvis (wake word, VAD, STT, router, LLM, TTS) di CPU Mac Intel. Pakai saat Jarvis terasa lambat atau di akhir fase yang menyentuh pipeline.
---

# Cek & Optimasi Latensi

Target (Mac Intel i9, CPU only):
| Tahap | Target |
|---|---|
| Selesai bicara → teks (VAD + STT) | ≤ 1.0 s |
| Rule engine → aksi | ≤ 0.1 s |
| LLM 4B token pertama | ≤ 1.5 s |
| Teks → suara mulai keluar (TTS) | ≤ 0.4 s |
| **Total perintah sederhana** | **≤ 2 s** |
| **Total pertanyaan LLM** | **≤ 5 s** |

## Langkah

1. Pastikan ada modul `jarvis/bench.py` (buat jika belum) yang:
   - memakai file audio contoh di `tests/fixtures/` (rekam/generate sekali, jangan dibaca sebagai teks),
   - mengukur tiap tahap dengan `time.perf_counter()`,
   - menjalankan 5x dan mencetak median per tahap dalam tabel.
2. Jalankan: `uv run python -m jarvis.bench`
3. Bandingkan dengan target. Untuk tahap yang lewat target, coba (satu per satu, ukur ulang):

**STT**: `beam_size=1`, `compute_type="int8"`, `language="id"`, model `base` jika `small` terlalu lambat,
`cpu_threads` = core fisik, VAD `silence_ms` 600–800.

**LLM**: `keep_alive=-1` (model tetap di RAM), `num_ctx` 2048, `num_predict` 150, `think=False`,
`num_thread` = core fisik, prompt sistem pendek, riwayat ≤ 6 pesan, perbanyak pola di rule engine.

**TTS**: streaming per kalimat (mulai bicara saat kalimat pertama LLM selesai), cache audio
untuk frasa yang sering ("Siap", "Oke, sebentar").

**Persepsi**: putar bunyi "ting" + frasa pengisi singkat saat LLM masih berpikir (lihat skill `jarvis-persona`).

4. Catat hasil sebelum/sesudah di laporan singkat. Jika mengubah default, update `config.yaml` dan `docs/CONFIG.md`.
