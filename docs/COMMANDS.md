# Daftar Perintah & Implementasi per OS

## 1. Contoh Perintah Suara

| Kategori | Contoh ucapan | Tool | Risk | Tier |
|---|---|---|---|---|
| Aplikasi | "Buka Spotify" · "Buka VS Code dan Chrome" | `open_app` | low | Rule / 4B |
| Aplikasi | "Tutup Chrome" | `close_app` | medium | Rule / 4B |
| Volume | "Volume 30 persen" · "Kecilin suaranya" · "Mute" | `set_volume`, `mute` | low | Rule |
| Media | "Putar musik" · "Pause" · "Lagu berikutnya" | `media` | low | Rule |
| Web | "Cari resep rendang" · "Buka YouTube" | `web_search`, `open_url` | low | Rule / 4B |
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
