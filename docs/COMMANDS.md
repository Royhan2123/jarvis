# Daftar Perintah & Implementasi per OS

## 1. Contoh Perintah Suara

| Kategori | Contoh ucapan | Tool | Risk | Tier |
|---|---|---|---|---|
| Aplikasi | "Buka Spotify" · "Buka VS Code dan Chrome" | `open_app` | low | Rule / 4B |
| Aplikasi | "Tutup Chrome" | `close_app` | medium | Rule / 4B |
| Volume | "Volume 30 persen" · "Kecilin suaranya" · "Mute" | `set_volume`, `mute` | low | Rule |
| Media | "Putar musik" · "Pause" · "Lagu berikutnya" | `media` | low | Rule |
| Web | "Cari resep rendang" · "Buka YouTube" | `web_search`, `open_url` | low | Rule / 4B |
| Web | "Putar lagu Dewa 19 di YouTube" · "play despacito on YouTube" | `play_youtube` (membuka video hasil pertama di browser bawaan; butuh `offline_only: false`; Safari bisa menahan putar otomatis) | low | Rule |
| Info | "Jam berapa?" · "Tanggal berapa hari ini?" | `get_time` | low | Rule |
| Info | "Baterai tinggal berapa?" · "RAM kepake berapa?" | `system_info` | low | Rule |
| Layar | "Rangkum isi layar ini" · "Ini error apa?" | `read_screen` | low | 4B (vision) |
| Ketik | "Ketik: halo, meeting diundur jam 3" | `type_text` | medium | 4B |
| Catatan | "Catat beli kopi besok" · "Bacakan catatan saya" | `add_note`, `list_notes` | low | 4B |
| Pengingat | "Ingatkan saya 10 menit lagi minum obat" | `set_reminder` | low | 4B |
| Memori | "Nama saya Roy" · "Kamu ingat nama saya?" | `remember_fact` | low | 4B |
| Sistem | "Kunci layar" | `lock_screen` | medium | Rule |
| Sistem | "Matikan komputer" · "Restart" | `shutdown`, `restart` | **high** | Rule + konfirmasi |
| Ngobrol | "Apa bedanya RAM dan SSD?" | – | – | 4B |
| Ngobrol | "Jelaskan cara kerja blockchain" | – | – | 9B |
| Kontrol Jarvis | "Berhenti" · "Diam" | `stop_speaking` | – | Rule |
| Kontrol Jarvis | "Ganti suara cewek" · "Pakai suara cowok" | `set_voice` | low | Rule |
| Kontrol Jarvis | "Ngomongnya pelan-pelan" · "Lebih cepat" | `set_speech_rate` | low | Rule |

---

## 2. Implementasi per OS

### Buka aplikasi — `open_app(name)`

| OS | Implementasi |
|---|---|
| macOS | `open -a "<name>"` |
| Windows | Cari shortcut di `%ProgramData%\Microsoft\Windows\Start Menu` & `%AppData%\...\Start Menu`, lalu `os.startfile(path)`; fallback `start "" "<name>"` |
| Linux | Cari file `.desktop` di `/usr/share/applications` & `~/.local/share/applications` (fuzzy match nama), lalu `gtk-launch <id>`; fallback `subprocess.Popen([name])` |

### Tutup aplikasi — `close_app(name)`

| OS | Implementasi |
|---|---|
| macOS | `osascript -e 'tell application "<name>" to quit'` |
| Windows | `psutil` cari proses → `proc.terminate()`; fallback `taskkill /IM <exe>` |
| Linux | `wmctrl -c "<name>"` (tutup sopan); fallback `psutil` → `terminate()` |

### Volume — `set_volume(percent)` / `mute(on)`

| OS | Implementasi |
|---|---|
| macOS | `osascript -e "set volume output volume <p>"` · mute: `set volume output muted true` |
| Windows | `pycaw`: `IAudioEndpointVolume.SetMasterVolumeLevelScalar(p/100)` · `SetMute(1)` |
| Linux | PipeWire: `wpctl set-volume @DEFAULT_AUDIO_SINK@ <p>%` · PulseAudio: `pactl set-sink-volume @DEFAULT_SINK@ <p>%` · mute: `pactl set-sink-mute @DEFAULT_SINK@ 1` |

### Media — `media(action)`

| OS | Implementasi |
|---|---|
| macOS | AppleScript ke app yang sedang jalan: `tell application "Spotify" to playpause` / `next track` / `previous track` (juga untuk "Music") |
| Windows | `pynput` media keys: `Key.media_play_pause`, `Key.media_next`, `Key.media_previous` |
| Linux | `playerctl play-pause` / `next` / `previous` (MPRIS — jalan untuk Spotify, browser, VLC) |

### Ketik teks — `type_text(text)`

| OS | Implementasi |
|---|---|
| macOS | `pynput.keyboard.Controller().type(text)` (butuh izin Accessibility) |
| Windows | `pynput` |
| Linux X11 | `pynput` / `xdotool type` |
| Linux Wayland | `ydotool type` ; fallback: salin ke clipboard + notifikasi "tekan Ctrl+V" |

> Teks panjang / berisi emoji lebih andal lewat **clipboard + paste** (`pyperclip` + Cmd/Ctrl+V).

### Screenshot — `read_screen()`

| OS | Implementasi |
|---|---|
| macOS | `mss` (butuh izin Screen Recording) |
| Windows | `mss` |
| Linux X11 | `mss` |
| Linux Wayland | `grim` (Sway/Hyprland) atau XDG Desktop Portal (GNOME/KDE) |

Lalu gambar di-resize ke lebar maks 1280 px dan dikirim ke `vision_model`.

### Notifikasi — `notify(title, body)`

| OS | Implementasi |
|---|---|
| macOS | `osascript -e 'display notification "<body>" with title "<title>"'` |
| Windows | `win11toast.toast(title, body)` |
| Linux | `notify-send "<title>" "<body>"` |

### Kunci layar / Shutdown

| Aksi | macOS | Windows | Linux |
|---|---|---|---|
| Kunci | `pmset displaysleepnow` | `rundll32.exe user32.dll,LockWorkStation` | `loginctl lock-session` |
| Shutdown | `osascript -e 'tell app "System Events" to shut down'` | `shutdown /s /t 0` | `systemctl poweroff` |
| Restart | `osascript -e 'tell app "System Events" to restart'` | `shutdown /r /t 0` | `systemctl reboot` |

---

## 3. Rule Engine (Tier 0) — Contoh Pola

Perintah ini dieksekusi **tanpa LLM** (instan):

```python
RULES = [
    (r"^(buka|jalankan)\s+(?P<app>.+)$", "open_app"),
    (r"^(tutup|matikan aplikasi)\s+(?P<app>.+)$", "close_app"),
    (r"volume\s+(?P<p>\d{1,3})\s*(persen|%)?", "set_volume"),
    (r"^(mute|bisukan|diam(kan)? suara)$", "mute"),
    (r"^(putar|play|lanjut(kan)?)( musik| lagu)?$", "media:play_pause"),
    (r"^(pause|jeda|stop musik)$", "media:play_pause"),
    (r"(lagu )?(berikutnya|selanjutnya|next)", "media:next"),
    (r"^jam berapa", "get_time"),
    (r"^cari\s+(?P<q>.+)$", "web_search"),
    (r"^kunci (layar|komputer)$", "lock_screen"),
    (r"^(matikan|shutdown) (komputer|laptop|pc)$", "shutdown"),
    (r"^(berhenti|stop|diam|cukup)$", "stop_speaking"),
]
```

Teks dinormalisasi dulu: huruf kecil, hapus "jarvis", "tolong", "dong", "ya", tanda baca.
Angka yang ditulis Whisper sebagai kata ("tiga puluh") dikonversi ke digit.

---

## 4. Catatan Implementasi (Fase 2)

- **Keamanan nama aplikasi:** hanya huruf/angka/spasi dan `. + ( ) ' -` (maks 60 karakter). macOS
  mengirim nama lewat `argv` AppleScript (tidak disisipkan ke teks script). Windows & Linux hanya
  membuka aplikasi yang punya **shortcut Start Menu / file `.desktop`**; tidak pernah menjalankan
  binary acak dari `PATH` (mencegah `open_app "shutdown"` melewati konfirmasi tool `high`).
- **close_app (Windows/Linux fallback):** hanya proses milik user saat ini, nama persis.
- **open_url / web_search:** hanya `http`/`https`; yang melakukan request jaringan adalah browser
  pengguna, bukan Jarvis, jadi tetap diizinkan saat `offline_only: true`.
- **Konfirmasi:** `registry.call()` menolak tool dengan risk >= `tools.confirm_risk_level`
  kecuali `confirmed=True` (alur konfirmasi suara dibuat di Fase 3).
- **Uji manual cepat:** `uv run python -m jarvis.tools list` dan
  `uv run python -m jarvis.tools call set_volume percent=30`.

### Checklist uji manual per OS

| Tool | macOS | Windows | Linux X11 | Linux Wayland |
|---|---|---|---|---|
| `open_app` / `close_app` | ✅ diuji (Calculator) | ⬜ belum | ⬜ belum | ⬜ belum |
| `set_volume` / `mute` | ✅ diuji | ⬜ belum | ⬜ belum | ⬜ belum |
| `media` | ⚠️ hanya jalur error (tanpa pemutar) | ⬜ belum | ⬜ belum | ⬜ belum |
| `open_url` / `web_search` | ⚠️ validasi URL saja | ⬜ belum | ⬜ belum | ⬜ belum |
| `get_time` / `system_info` | ✅ diuji | ⬜ belum | ⬜ belum | ⬜ belum |
| `lock_screen` | ⬜ belum (mematikan layar) | ⬜ belum | ⬜ belum | ⬜ belum |

### Router & LLM tool calling (Fase 3)

- Urutan: **aturan regex** (`brain/rules.py`) → **Qwen 4B** → **Qwen 9B** (kata kunci kompleks,
  > `router.complex_min_words` kata, atau 4B memanggil tool `escalate`; jika 9B belum terpasang
  jatuh kembali ke 4B).
- **Skema tool hanya dikirim bila relevan** (`TOOL_HINTS` di `brain/router.py`). Terukur di Mac i9:
  mengirim tool ke Qwen 4B menambah 5–8 detik prefill (obrolan biasa tanpa tool ≈ 2,6 detik), dan 4B
  cenderung memanggil `web_search` untuk pertanyaan fakta. Perintah umum ditangkap aturan regex
  (instan); jalur LLM+tool (≈ 12–19 detik) hanya untuk ucapan yang tidak cocok aturan.
- **Konfirmasi suara:** tool `high` → Jarvis bertanya "Yakin …? Bilang ya atau tidak.", mendengar
  `tools.confirm_timeout_s` detik. Kata "tidak/jangan/batal" selalu menang; diam atau tidak jelas =
  batal. Tool call dari LLM juga lewat jalur yang sama (tidak bisa melewati konfirmasi).

### Fase 4: layar, ketik, memori, pengingat, interupsi

- **read_screen:** screenshot (`mss`; Wayland: `grim`) → diperkecil 960 px → model vision Ollama
  (`llm.vision_model`). Prompt vision menyatakan isi layar sebagai DATA (tidak boleh dituruti), dan
  hasilnya hanya dibacakan; tidak pernah diteruskan ke tool lain. macOS: wajib izin *Screen Recording*
  (tanpa izin hanya wallpaper yang tertangkap; Jarvis mengecek dan meminta izin).
- **type_text:** satu baris saja (Enter/Tab/karakter kontrol dibuang, maks 500 karakter) agar teks
  tidak bisa mengeksekusi perintah di terminal. macOS butuh izin *Accessibility*. Teks panjang/emoji
  lewat clipboard + paste. Wayland: `ydotool`, fallback clipboard + notifikasi "tekan Ctrl+V".
- **Memori (SQLite, folder data pengguna):** riwayat percakapan (dipertahankan `memory.retention_days`),
  fakta (masuk system prompt), catatan (juga ditambahkan ke `notes.md`), pengingat.
  Perintah: "catat …", "bacakan catatan", "nama saya …", "ingatkan saya 10 menit lagi …".
- **Pengingat:** thread penjadwal memeriksa tiap 3 detik; saat jatuh tempo → notifikasi + bunyi ting +
  diucapkan (saat Jarvis idle).
- **Interupsi:** selama Jarvis bicara, ucapan pendek yang terdengar ditranskripsi (model wake);
  "berhenti/stop/cukup/diam" atau kata pemanggil memotong suara dan menghentikan LLM. Tanpa peredam
  gema: segmen yang terus-menerus (gema suara Jarvis sendiri) diabaikan, jadi lebih andal dengan headset.

---

## 6. Plugin (Fase 5)

Tool buatan sendiri tanpa mengubah kode Jarvis:

1. Buat file `.py` (atau folder dengan `__init__.py`) di folder plugins:
   macOS `~/Library/Application Support/jarvis/plugins`, Linux `~/.local/share/jarvis/plugins`,
   Windows `%LOCALAPPDATA%\jarvis\plugins` (atau atur `tools.plugins.dir`).
2. Pakai dekorator `@tool` yang sama dengan tool bawaan (lihat `examples/plugins/dadu.py`).
   Isi `KEYWORDS = [...]` agar skema tool dikirim ke LLM saat ucapan mengandung kata itu.
3. Restart Jarvis. Cek dengan `uv run python -m jarvis.tools list`.

Aturan: argumen divalidasi pydantic; risk `high` tetap butuh konfirmasi suara; nama yang bentrok
dengan tool bawaan ditolak; plugin yang error dilewati (log WARNING). Plugin adalah kode dengan hak
penuh pengguna: pasang hanya yang dipercaya, atau batasi lewat `tools.plugins.allowed`.

---

## 7. Integrasi online (Fase 5, opsional)

Default mati: tool `get_weather`, `calendar_events`, `add_calendar_event`, `unread_emails` menolak
jalan selama `general.offline_only: true`. Untuk memakai:

1. **Cuaca:** set `general.offline_only: false`. Gratis, tanpa akun (Open-Meteo); hanya nama kota keluar.
2. **Calendar & Gmail:** buat sendiri proyek di Google Cloud Console → aktifkan Google Calendar API
   dan Gmail API → OAuth consent screen (External, tambahkan emailmu sebagai test user) → buat
   OAuth client jenis *Desktop app* → unduh JSON, isi `online.google_credentials` dengan path-nya →
   jalankan `uv run python -m jarvis.setup google-login` dan setujui di browser.
3. Scope minimal: `calendar.events` dan `gmail.readonly`. Gmail hanya membaca pengirim + subjek.
   Tidak ada tool kirim email atau hapus acara.
4. Selama aplikasi berstatus *Testing*, token Google kedaluwarsa tiap ±7 hari → ulangi `google-login`.
5. Tanpa pustaka `google-auth` (butuh `cryptography`, tidak ada paket siap pakai untuk Mac Intel);
   OAuth loopback + PKCE dan REST ditulis dengan pustaka standar (`jarvis/online/google.py`).

---

## 8. Smart home (Fase 5, opsional)

Default mati (`smarthome.enabled: false`). Tool: `device_control` (risk medium), `device_state`,
`list_devices`. Suara: "nyalakan/matikan <nama perangkat>", "apakah <nama> menyala".

- **Hanya perangkat di `smarthome.devices`** yang bisa disentuh; nama diucapkan = kunci di config.
- **Home Assistant:** REST API dengan long-lived token (buat di profil HA; simpan di file, isi
  `token_file`, atau env `JARVIS_HA_TOKEN`). Domain dibatasi ke `light`, `switch`, `fan`, `scene`:
  kunci pintu, alarm, dan garasi sengaja ditolak.
- **MQTT:** publish `on`/`off` ke topik perangkat (paho-mqtt). Status tidak tersedia untuk MQTT.
- **Jaringan:** saat `general.offline_only: true`, host harus alamat lokal (localhost, 10.x/172.16.x/
  192.168.x, link-local, atau `.local`). Alamat internet publik baru diizinkan jika
  `offline_only: false`. Ini pelonggaran terbatas dari aturan "tidak ada request keluar" untuk LAN
  rumah (aturan ini sudah dicatat di CLAUDE.md).
- Token/password tidak boleh ditulis di `config.yaml`.

---

## 9. Folder kerja & draf WhatsApp (setelah Fase 5)

**Baca / perbaiki kode** (`workspace.folders` harus diisi; kosong = mati):
- Sebut nama file dalam ucapan: "jelaskan fungsi hitung_diskon di toko titik py", "baris 10 sampai 30
  di app.py". Potongan file (±3000 karakter, bernomor baris) dikirim ke LLM sebagai DATA.
- Kata ubah/ganti/perbaiki/tambah → LLM boleh memakai `replace_in_file` / `create_file`. Keduanya
  **risk high**: Jarvis menyebut file yang akan diubah dan menunggu "ya" (diam/tidak jelas = batal).
- `replace_in_file` hanya jika teks lama muncul tepat satu kali; file asli dicadangkan sebagai
  `<file>.jarvis-bak`. `create_file` tidak pernah menimpa file yang ada.
- Dilindungi selalu: path di luar folder kerja (symlink keluar ditolak), `.env`, `.ssh`, `.git`, kunci,
  token, dan ekstensi di luar daftar. Tidak ada penghapusan file dan tidak ada shell.
- Batas nyata di CPU: file kecil/potongan saja; jawaban 15–25 detik. Untuk file besar sebut nomor baris.

**WhatsApp:** "kirim pesan WhatsApp ke Budi isinya besok rapat jam 9" → membuka `wa.me` dengan teks
terisi. Pesan **tidak terkirim otomatis**; kamu menekan kirim. Hanya kontak di `messaging.contacts`.

---

## 9b. Bahasa Inggris & terjemahan

Dengan `stt.language: auto`, tiap ucapan dideteksi Indonesia atau Inggris (model `tiny`, ±0.4 dtk lebih
lama dari `id` saja), lalu ditranskripsi dengan bahasa itu. Frasa pemanggil tetap dikenali sebagai "Hello".

- **Perintah dasar Inggris** (Tier 0, `jarvis/brain/rules_en.py`): "open Chrome", "close Spotify",
  "what time is it", "what's the date", "set volume to 40", "mute", "next song", "lock screen",
  "search for …", "what's the weather in Bandung". Perintah lain ditangani LLM dengan tool; LLM menjawab
  Inggris bila Anda berbicara Inggris.
- **Terjemahan** — `translate(text, target)` (risk low, LLM lokal Qwen 4B, tanpa internet):
  "terjemahkan ke bahasa Inggris: selamat pagi" · "apa bahasa Inggris dari terima kasih" ·
  "translate good morning to Indonesian" · "how do you say thank you in Japanese".
  Bahasa dikenal: Inggris, Indonesia, Jepang, Korea, Mandarin, Arab, Jerman, Prancis, Spanyol, Belanda,
  Portugis, Rusia, Italia, Jawa, Sunda (kualitas Jawa/Sunda dari Qwen belum teruji baik).
- **Suara balasan:** Fish Audio membacakan Inggris/Jepang dengan suara yang sama. Untuk Piper/suara OS
  (cadangan atau mode offline), tiap kalimat dipilih suaranya: kalimat Inggris memakai `tts.voices.piper_en`
  (atau `system_en`), selainnya suara Indonesia. Unduh suara Inggris: `python -m jarvis.setup download-voice
  en_US-ryan-medium` (pria) / `en_US-amy-medium` (wanita), masing-masing ±63 MB. Bahasa selain Inggris
  (mis. Jepang) tetap dibaca suara Indonesia bila Fish tak tersedia.
- **±100 bahasa (Whisper):** terjemahan ke semua bahasa di `jarvis/brain/language.py` (nama Indonesia atau
  Inggris: "terjemahkan ke bahasa Swahili: …"). Hasil uji nyata (26 bahasa, 2026-11-11): Jepang, Korea,
  Mandarin, Arab, Jerman, Prancis, Spanyol, Rusia, Hindi, Vietnam, Polandia, Swedia, Ibrani, Persia dst.
  diterjemahkan, diucapkan Fish, dan didengar balik dengan benar; **Turki dan Ukraina masih cacat** (kata
  Indonesia tersisa / salah ketik). Bila hasil hampir sama dengan sumber, Jarvis mengulang dengan Qwen 9B.
- **Mendengarkan bahasa lain:** ucapkan **"ganti bahasa ke Jepang"** (juga "pakai bahasa Korea", "switch
  language to German"). Jarvis lalu memilih per ucapan di antara **Indonesia, Inggris, dan bahasa itu**
  (tiga arah, jauh lebih andal daripada ±90 bahasa) sampai dimatikan; bahasa Indonesia tetap dikenali,
  jadi "ganti bahasa ke Indonesia" / "ganti ke otomatis" selalu bisa dipakai untuk kembali. Hanya satu
  bahasa tambahan sekaligus; frasa pemanggil tetap "Hello".
- **Deteksi otomatis banyak bahasa tidak andal** (uji nyata 26 bahasa: `tiny` benar 10, `base` 6, `small`
  5; bahasa Indonesia berisiko terdeteksi sebagai bahasa lain). Karena itu default `detect_languages` hanya
  `["id","en"]`; `["all"]` hanya untuk eksperimen.
- **Suara:** Fish resmi mendukung ±13 bahasa (uji: Jepang, Korea, Mandarin, Arab, Jerman, Spanyol, Rusia,
  Hindi baik). Bahasa lain dan mode offline (Piper/OS) hanya Indonesia/Inggris.
- **Perintah Inggris lainnya:** "take a note: …", "type: …", "remind me to X in 10 minutes", "read my notes",
  "my name is Roy", "summarize my screen", "what's on my calendar", "any new emails", "send a WhatsApp to
  Budi saying …", "work on <tugas>" (agen), "turn on <nama perangkat>".

## 10. Suara Fish Audio (online, opsional)

`tts.engine: fish` memakai API Fish Audio untuk suara yang lebih jelas. **Privasi:** teks setiap kalimat
yang diucapkan Jarvis dikirim ke server Fish Audio; karena itu hanya jalan jika `general.offline_only: false`
(kalau tidak, Jarvis otomatis memakai Piper). Jika Fish gagal (jaringan, key, saldo), kalimat itu diucapkan
Piper sebagai cadangan.

1. Buat API key di https://fish.audio/app/api-keys (tampil sekali). Simpan di file, bukan di config/chat:
   `read -s K && printf '%s' "$K" > ~/.jarvis-fish-key && chmod 600 ~/.jarvis-fish-key`
2. Pilih suara di https://fish.audio/app/discovery, salin ID-nya (bagian akhir URL `fish.audio/m/<id>`).
3. Isi `tts.engine: fish`, `tts.fish.voice_id` (pria, default), `tts.fish.female_voice_id` (wanita, dipakai bila `tts.gender: female`), `tts.fish.api_key_file: ~/.jarvis-fish-key`.
4. Dokumentasi Fish: bahasa Indonesia **belum dikonfirmasi** didukung; uji kualitasnya dulu. Model gratis
   `s2.1-pro-free` tanpa jaminan latensi; model berbayar perlu saldo (kalau kosong → HTTP 402 → Piper).

---

## 11. Agen kerja (shell terjaga)

> **Akses penuh (2026-11-13):** `workspace.full_access: true` membolehkan agen *memeriksa* (baca/lihat/cari) di mana saja di
> komputer. Tiap akses di luar `workspace.folders` **selalu minta izin** (tak bisa dilonggarkan); ubah/buat file tetap hanya di
> `folders`; rahasia (`workspace.deny`) dan blokir keras shell tetap berlaku.

Jarvis mengerjakan tugas bertahap di komputer, mirip Claude Code: baca/cari file, ubah, lalu jalankan
tes. Aktifkan: `agent.enabled: true` + isi `workspace.folders`. Model: `llm.smart_model` (Qwen 9B).

| Cara | Contoh |
|---|---|
| Suara / teks Jarvis | "Jarvis, kerjakan perbaiki bug diskon di toko.py lalu jalankan tesnya" (awalan `kerjakan` / `agen`) |
| Terminal | `uv run python -m jarvis.agent "perbaiki toko.py dan jalankan pytest"` |
| Dipakai app lain | `from jarvis.agent import Agent; Agent(cfg, confirm=fn, say=fn).run(tugas)` |

Tool agen: `list_dir`, `read_file`, `search`, `edit_file`, `write_file`, `run_command`.

**Suara pengisi:** saat agen bekerja Jarvis mengucapkan status singkat ("Membaca toko titik py", "Mencari …",
"Menjalankan perintah") di latar, supaya tidak terasa mati selama model berpikir. Ucapan tidak menahan agen,
dilewati bila ucapan sebelumnya belum selesai, dan selalu selesai dulu sebelum pertanyaan izin atau ringkasan
akhir (dua suara sekaligus saling menutupi). Matikan dengan `agent.narrate: false`.

**Pengaman (jangan dilonggarkan tanpa izin pemilik):**
- **Izin bisa disetel** lewat `agent.confirm_actions` (default minta izin untuk `edit_file`, `write_file`, `run_command`; hapus item agar otomatis, `[]` = tanpa tanya). Blokir keras dan file rahasia tidak ikut longgar.
- Ubah/buat file dan semua perintah shell **dikonfirmasi** (suara "ya"; diam/tidak jelas = batal).
  Pengecualian: `agent.readonly_commands` (ls, cat, grep, git status...) tanpa pipa/redirect/`$()`.
- Daftar blokir keras yang **tak bisa ditembus konfirmasi**: `sudo`, `rm -rf` ke `/`/`~`/`*`, perintah
  disk (`mkfs`, `dd of=`), `curl | sh`, shutdown/reboot, `crontab`/`launchctl`/`systemctl`, perintah
  yang menyebut path rahasia (`.ssh`, `.env`, `id_rsa`, ...), perintah > 300 karakter.
- `offline_only: true` → `curl`, `ssh`, `git push/pull`, `pip/npm install`, dll. diblokir.
- `workspace.folders` boleh seluruh home (`["~"]`); folder raksasa (`Library`, `node_modules`, ...) tidak dipindai, dan `workspace.deny` (`.ssh`, `.config`, `.env`, kunci Fish, riwayat shell, Keychains, ...) tetap tak tersentuh walau folder dibuka penuh.
- Folder kerja perintah = `workspace.folders[0]`; path file harus di dalam folder kerja (symlink di-resolve).
- Environment dibersihkan dari variabel `*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASSWORD*`; timeout; keluaran dipotong.
- Isi file & keluaran perintah dikirim ke model sebagai DATA; file yang diubah dicadangkan `.jarvis-bak`.
- Batas `agent.max_steps` langkah per tugas.

**Mengatur izin tanpa edit `config.yaml`** (berlaku seketika; dari suara hanya sampai Jarvis dimatikan):

| Ucapan | Efek |
|---|---|
| "Jarvis, jangan tanya lagi untuk ubah file" / "…buat file baru" / "…menjalankan perintah" / "…semuanya" | Melonggarkan: **butuh konfirmasi suara** ("ya"), karena menurunkan pengaman |
| "Selalu tanya untuk ubah file" / "tanya sebelum menjalankan perintah" / "mulai tanya lagi untuk semuanya" | Mengetatkan: langsung berlaku |

Tool pelonggar (`agent_auto_approve`, risk high) hanya terpicu oleh rule ucapan dan **tidak pernah ditawarkan ke
LLM**, jadi teks dari file/web tidak bisa memicunya. Dashboard punya bagian **Izin agen kerja** (kotak centang +
"simpan permanen ke config.yaml", mengganti hanya baris `confirm_actions`, komentar tetap, cadangan `.bak`).
Blokir keras dan file rahasia tidak ikut longgar dalam kondisi apa pun.

Batas jujur: Qwen 9B di CPU lambat (puluh detik per langkah) dan bisa salah memilih tool; selalu
dengarkan kalimat konfirmasi sebelum bilang "ya".

---

## 12. Sambungan ke Isla Desk (pulau notifikasi)

Isla Desk adalah proyek terpisah (`Dekstop-Notification-With-Tauri`): pulau notifikasi di atas layar. Jarvis
mengirim teks ke pulau lewat IPC loopback; Isla membalas "diterima". Aktifkan: `island.enabled: true` dan
jalankan Isla Desk lebih dulu.

**Isla ↔ Jarvis dua arah** (butuh `ui.api.enabled: true` supaya Isla bisa menghubungi Jarvis):
- **Batang suara:** fase Jarvis (mendengarkan/berpikir/bicara) tampil di pulau (`island.show_voice`).
- **Tanya AI lewat Jarvis:** di Setelan Isla pilih otak AI **Jarvis**; Quick Ask dijawab Jarvis lokal (offline)
  lewat `POST /v1/ask`. Catatan: fitur Isla yang butuh keluaran terstruktur (review kode, saran commit)
  lebih andal dengan penyedia lain.
- **Izin agen sebagai tombol:** bila agen minta izin dan Isla menerima kartunya (`island.approvals`), pulau
  menampilkan kartu **Setuju/Tolak**; jawaban dikirim ke `POST /v1/approvals/{id}`. Tanpa jawaban dalam
  `island.approval_timeout_s` detik = ditolak. Bila Isla tidak berjalan, Jarvis kembali bertanya lewat suara.

| Cara | Contoh |
|---|---|
| Suara / teks Jarvis | "Jarvis, tampilkan di pulau selamat pagi bos" (tool `show_on_island`, risk low) |
| Otomatis | Pertanyaan izin agen ("Jarvis ingin mengubah file …") dan ringkasan hasil agen ikut tampil di pulau |
| Dari kode | `from jarvis import island; island.notify(cfg, "teks")` (`notify_async` agar tidak menunggu) |

**Protokol** (`jarvis/island.py`): baca `ipc.json` ({port, token}) di folder data Isla; kirim satu baris JSON
`{"token": …, "notify": "<teks>"}` ke `127.0.0.1:<port>`; Isla membalas satu baris `{"allow": true}`.
Teks dirapikan jadi satu baris tanpa karakter kontrol, maksimal 200 karakter (batas Isla).

**Batas jujur**
- Balasan `allow:true` hanya berarti *diterima*, bukan *tampil*. Isla membuang pesan saat **Jangan Ganggu** aktif,
  dan pulau tidak terlihat di Space layar penuh kecuali Isla memakai versi `macos-support` (NSPanel).
  Karena itu pesan tool-nya "Sudah saya kirim ke pulau Isla", bukan "sudah tampil".
- Pesan hanya tampil sekitar 8 detik (setelan `display_seconds` di Isla).
- Isla tidak menyala atau IPC tak terjangkau → Jarvis diam-diam melewatinya (tidak error).
- Arah sebaliknya (Tanya AI di pulau memanggil Jarvis, persetujuan agen lewat tombol) belum ada; lihat ROADMAP.

---

## 12b. Penyedia AI (Ollama bawaan atau API online)

Bawaan: **Ollama lokal**, offline penuh. Atas pilihan pemilik, otak Jarvis bisa memakai API online
(OpenAI, Anthropic, Gemini, Groq, OpenRouter, DeepSeek, Mistral, atau alamat sendiri berprotokol OpenAI) dengan kunci
milik pengguna. Atur lewat Isla Desk (`PUT /v1/ai`), atau:

```bash
uv run python -m jarvis.setup ai openai --model gpt-4o-mini     # kunci ditanya (tersembunyi)
uv run python -m jarvis.setup ai ollama                         # kembali ke lokal
uv run python -m jarvis.setup ai --test                         # lihat penyedia aktif + uji
```

- Berlaku **seketika** tanpa restart. Pindah ke online membongkar model Ollama dari RAM (Jarvis ±1,5 GB).
- Kunci disimpan di `ai.json` (izin 0600, folder data pengguna) atau env; tidak pernah di `config.yaml`, log, atau respons API.
- Online hanya jalan bila `llm.allow_cloud` (otomatis true saat dipilih lewat setelan). Tanpa izin itu, tidak ada byte keluar.
- **Tetap lokal apa pun penyedianya:** baca layar (gambar tidak dikirim), embedding RAG, dan suara/STT.
- Yang dikirim ke penyedia online: pertanyaan, riwayat singkat, info/dokumen yang relevan, dan (agen) isi file yang dibaca.
- Pemanasan model (`agent.prewarm`) dilewati saat online (hanya membuang kuota).

## 13. API lokal untuk aplikasi lain

Agar aplikasi desktop (mis. Isla Desk) bisa bertanya ke Jarvis dan memberi tugas ke agen kerja, dengan persetujuan
lewat **tombol** (bukan suara). Aktifkan: `ui.api.enabled: true` (memakai server dashboard di 127.0.0.1, port
`ui.dashboard.port`). Mati bawaan.

**Menemukan server:** saat menyala, Jarvis menulis `api.json` (izin 600) di folder data pengguna
(`platformdirs.user_data_dir("jarvis")`): `{"port", "token", "pid", "url"}`. Token acak per proses; kirim sebagai
`Authorization: Bearer <token>`. Header `Host` harus `127.0.0.1:<port>` atau `localhost:<port>` (anti DNS-rebinding).

| Rute | Fungsi |
|---|---|
| `GET /v1/status` | Model, `agent.enabled/workspace/busy/confirm_actions`, `state` suara |
| `GET /v1/state` | `{state, seq, at}`: idle/listening/thinking/speaking/confirming |
| `GET /v1/state/events` | SSE `state`: keadaan sekarang dulu, lalu tiap perubahan (denyut tiap 15 dtk) |
| `GET /v1/ai` | Penyedia AI aktif, model, `has_key`, daftar penyedia (kunci tidak pernah dikembalikan) |
| `PUT /v1/ai` `{provider, api_key?, api_base?, fast_model?, smart_model?}` | Ganti penyedia saat berjalan (tanpa restart). Memilih penyedia online = izin eksplisit (`allow_cloud`); model Ollama dibongkar dari RAM. 422 bila isian tak sah |
| `POST /v1/ai/test` | Satu pertanyaan uji ke penyedia aktif: `{ok, reply}` / `{ok:false, error}` |
| `POST /v1/ask` `{text}` | `{reply, tier}`: aturan, Qwen 4B, atau 9B; tanpa suara. Riwayat percakapan API terpisah dari suara. Aksi berisiko tinggi (matikan komputer) **tidak dijalankan** (butuh "ya" suara) |
| `POST /v1/agent` `{task}` | 202 `{id}`; **satu tugas pada satu waktu** (409 bila sibuk, agen mati, atau folder kerja belum diatur) |
| `GET /v1/agent/{id}` | `{status, result, pending_confirm}` (status: running/done/error/cancelled) |
| `GET /v1/agent/{id}/events` | SSE: `step`, `result`, `confirm` {confirm_id, what}, `confirm_result` {allow, timeout}, `done`/`error`/`cancelled`; denyut `: ping` tiap 15 dtk |
| `POST /v1/agent/{id}/confirm` `{confirm_id, allow}` | Jawab pertanyaan izin (409 bila id salah / tak ada yang menunggu) |
| `POST /v1/agent/{id}/cancel` | Batalkan; pertanyaan izin yang menunggu dianggap ditolak |

**Contoh (curl):**

```bash
# port & token dari api.json
curl -H "Authorization: Bearer $TOKEN" -d '{"text":"apa ibu kota Jepang?"}' -H 'Content-Type: application/json' \
     http://127.0.0.1:8765/v1/ask
```

**Pengaman (sama dengan agen suara, tidak dilonggarkan):** blokir keras shell, file rahasia, `workspace.folders`,
`agent.confirm_actions`. Pertanyaan izin yang tak dijawab dalam `ui.api.confirm_timeout_s` (60 dtk) = ditolak.
Tidak ada CORS (klien adalah program lokal, bukan halaman web). Isi `text`/`task` dibatasi `ui.api.max_text_chars`.

Batas jujur: satu klien agen sekaligus; `/v1/ask` memakai satu riwayat bersama untuk semua pemanggil API; belum ada
streaming token untuk `/v1/ask`.

