# Eksperimen: bahasa daerah (Jawa / Sunda)

Status: **dikaji, belum dikerjakan**. Dicek 2026-11-09.

| Tahap | Kondisi | Kesimpulan |
|---|---|---|
| STT | Whisper punya kode bahasa `jw` (Jawa) dan `su` (Sunda). Cukup set `stt.language: "jw"` / `"su"`. | Bisa dicoba hari ini, akurasi di model `small` belum diukur (data Jawa/Sunda Whisper jauh lebih sedikit dari Indonesia). |
| Router (aturan) | Aturan regex berbahasa Indonesia ("buka", "matikan"). | Perlu kosakata perintah Jawa/Sunda per bahasa (mis. "bukak", "pateni", "hurungkeun"). |
| LLM | Qwen3.5 4B/9B paham bahasa Jawa/Sunda secara terbatas. | Bisa memahami sebagian, kualitas jawaban belum diuji; prompt perlu menyuruh membalas dalam bahasa yang sama. |
| TTS | Daftar suara Piper tidak punya bahasa Jawa maupun Sunda. | Hambatan utama: suara Indonesia akan membaca teks daerah dengan logat salah. Perlu melatih suara sendiri (data rekaman + pelatihan, kemungkinan butuh GPU). |

## Langkah bila dilanjutkan
1. Rekam 20–30 kalimat perintah Jawa/Sunda dengan `uv run python -m jarvis.setup test-stt --save <folder>`,
   bandingkan `stt.language` `id` vs `jw`/`su` (ukur kesalahan kata).
2. Tambah kosakata perintah daerah di `brain/rules.py` (pakai tabel sinonim, uji dengan pytest).
3. Tambah opsi `general.reply_language` dan perintahkan LLM membalas dalam bahasa itu.
4. TTS: mulai dengan membalas dalam bahasa Indonesia; suara daerah menyusul (fine-tune Piper).

Langkah 1–3 ringan; langkah 4 berat dan di luar perangkat Mac Intel ini.
