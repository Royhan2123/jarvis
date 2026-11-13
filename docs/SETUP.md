# Setup & Cara Menjalankan Jarvis

Panduan ini untuk **macOS, Windows, dan Linux**. Langkahnya sama secara garis besar:

1. Install **Python 3.11/3.12** + **uv**
2. Install **Ollama** + download model **Qwen3.5**
3. Install dependensi sistem (audio)
4. Install Jarvis + download suara Indonesia
5. Beri izin mikrofon & aksesibilitas
6. Jalankan

---

## ⚡ Pasang Satu Baris (untuk pengguna biasa, tanpa sudo/admin, tanpa Node.js)

Memasang `uv` ke folder pengguna, mengunduh Jarvis, menyiapkan Python & paket, mengunduh model suara, dan membuat
`config.yaml` awal (API lokal aktif untuk Isla Desk). Aman dijalankan ulang: kode diperbarui, `config.yaml` kamu tidak disentuh.

| OS | Perintah |
|---|---|
| macOS / Linux (Terminal) | `curl -LsSf https://raw.githubusercontent.com/Royhan2123/jarvis/main/scripts/install.sh \| bash` |
| Windows (PowerShell) | `irm https://raw.githubusercontent.com/Royhan2123/jarvis/main/scripts/install.ps1 \| iex` |

- Lokasi: macOS `~/Library/Application Support/jarvis-app/`, Linux `~/.local/share/jarvis-app/`, Windows `%LOCALAPPDATA%\jarvis-app\`.
  Di sana ada `app/` (kode + `config.yaml`) dan peluncur `run.sh` / `run.cmd`.
- **Isla Desk** menemukan peluncur itu sendiri: bila otak AI dipilih "Jarvis", Isla menyalakannya saat start dan mematikannya saat keluar
  (Setelan → Otak Jarvis juga punya tombol "Jalankan Jarvis" dan menampilkan perintah di atas bila belum terpasang).
- Linux: PortAudio (`libportaudio2`) kadang perlu dipasang lewat `apt`/`dnf`/`pacman` (butuh sudo); skrip hanya mencetak perintahnya.
- Ollama tidak ikut dipasang (https://ollama.com/download). Tanpa Ollama pakai penyedia online di Setelan Isla → Otak Jarvis.
- Uji/offline: `JARVIS_SOURCE_DIR=<folder jarvis> JARVIS_SKIP_MODELS=1 bash scripts/install.sh` (juga `JARVIS_HOME`, `JARVIS_SOURCE_URL`).
- **Status uji (2026-11-13):** macOS terbukti (pasang ke folder sementara, Jarvis menyala, `/v1/ai` menjawab). **Windows dan Linux belum diuji**
  (skrip ditulis, sintaks bash diperiksa; PowerShell belum dijalankan sama sekali).
- **Syarat sebelum perintah di atas bisa dipakai orang lain:** repo GitHub harus **publik** (sekarang private), dan `config.yaml`
  pengembang di repo diganti `config.example.yaml` (installer membuang `config.yaml` dari arsip dan membuat yang baru).

---

## 🍎 macOS (Intel & Apple Silicon)

> ⚠️ **Tanpa Homebrew.** Sejak September 2026 Homebrew menurunkan Mac Intel ke Tier 3
> (tidak ada lagi paket siap pakai baru, banyak paket harus di-compile dan bisa gagal).
> Jadi semua tool di bawah dipasang lewat installer resminya. Cara ini juga jalan di Apple Silicon.

### 1. Install tools

```bash
# Xcode Command Line Tools (git & compiler)
xcode-select --install

# uv (otomatis mengurus Python 3.12, tidak perlu install Python manual)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Ollama:** download dari https://ollama.com/download → pindahkan `Ollama.app` ke Applications → buka sekali.

> PortAudio tidak perlu dipasang terpisah: paket `sounddevice` untuk macOS sudah membawanya.

### 2. Download model

```bash
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b
```

### 3. Install Jarvis

```bash
cd ~/project/jarvis
bash scripts/install_macos.sh      # cek tools, download model, siapkan Python & library
uv run python -m jarvis --check    # cek mic, speaker, Ollama, model
```

### 4. Izin yang wajib diberikan

Buka **System Settings → Privacy & Security**, lalu izinkan **Terminal** (atau app Jarvis hasil build):

| Izin | Untuk |
|---|---|
| **Microphone** | Mendengar suara |
| **Accessibility** | Ketik teks, kontrol keyboard |
| **Screen Recording** | Fitur "baca layar" |
| **Automation** | Kontrol Spotify/Music/System Events via AppleScript |

### 5. Jalankan

```bash
uv run python -m jarvis
```

### 💡 Tips Mac Intel

- Tidak ada akselerasi GPU untuk LLM, semuanya jalan di **CPU** → gunakan `qwen3.5:4b` sebagai default.
- Set `llm.num_thread` = jumlah **core fisik** (cek: `sysctl -n hw.physicalcpu`).
- Tutup aplikasi berat (Chrome dengan banyak tab) agar respons lebih cepat.

---

## 🪟 Windows 10/11

### 1. Install tools (PowerShell)

```powershell
winget install Python.Python.3.12
winget install astral-sh.uv
winget install Ollama.Ollama
winget install Gyan.FFmpeg
winget install Git.Git
```

Tutup & buka ulang PowerShell setelah install.

### 2. Download model

```powershell
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b
```

### 3. Install Jarvis

```powershell
git clone <repo-kamu>/jarvis.git
cd jarvis
uv sync
uv run python -m jarvis.setup download-voice
uv run python -m jarvis.setup check
```

### 4. Izin

- **Settings → Privacy & security → Microphone** → aktifkan "Let desktop apps access your microphone".
- Jika Windows Defender SmartScreen muncul saat menjalankan `.exe` hasil build, pilih *More info → Run anyway* (atau tanda tangani binary untuk rilis).

### 5. Jalankan

```powershell
uv run python -m jarvis
```

### 💡 Tips Windows

- Punya GPU NVIDIA? Ollama otomatis memakai CUDA. Untuk faster-whisper GPU, install CUDA 12 + cuDNN lalu set `stt.device: cuda`.
- Volume dikontrol lewat `pycaw` (otomatis terinstall di Windows).

---

## 🐧 Linux (Ubuntu / Debian / Fedora / Arch)

### 1. Install dependensi sistem

**Ubuntu / Debian**
```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv portaudio19-dev ffmpeg \
  libnotify-bin playerctl xclip wl-clipboard espeak-ng \
  pulseaudio-utils libgirepository1.0-dev gir1.2-appindicator3-0.1
```

**Fedora**
```bash
sudo dnf install -y python3.12 portaudio-devel ffmpeg libnotify playerctl \
  xclip wl-clipboard espeak-ng pulseaudio-utils libappindicator-gtk3
```

**Arch**
```bash
sudo pacman -S python portaudio ffmpeg libnotify playerctl xclip \
  wl-clipboard espeak-ng libpulse libappindicator-gtk3
```

### 2. Install uv & Ollama

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh

ollama pull qwen3.5:4b
ollama pull qwen3.5:9b
```

### 3. Install Jarvis

```bash
git clone <repo-kamu>/jarvis.git
cd jarvis
uv sync
uv run python -m jarvis.setup download-voice
uv run python -m jarvis.setup check
```

### 4. Catatan Wayland

Wayland (default di Ubuntu 22.04+ dan Fedora) membatasi simulasi keyboard & screenshot:

| Fitur | Solusi Wayland |
|---|---|
| Ketik teks | Install `ydotool` dan jalankan `ydotoold`, set `platform.linux.typing_backend: ydotool` |
| Screenshot | Install `grim` (wlroots) atau pakai portal GNOME; set `platform.linux.screenshot_backend: portal` |
| Tray icon | GNOME butuh extension **AppIndicator** |

Atau login dengan sesi **X11 / "Ubuntu on Xorg"** agar semua fitur langsung jalan.

### 5. Jalankan

```bash
uv run python -m jarvis
```

---

## ▶️ Opsi Menjalankan

```bash
python -m jarvis                     # mode normal (tray + suara)
python -m jarvis --listen            # pipeline suara penuh (wake word "Hey Jarvis")
python -m jarvis --text              # mode teks di terminal (tanpa mic) — untuk debugging
# Dashboard: set ui.dashboard.enabled: true, lalu buka URL ber-token dari log (127.0.0.1:8765)
python -m jarvis --no-tray           # tanpa ikon tray (server / headless)
python -m jarvis --config my.yaml    # pakai config lain
python -m jarvis --log-level DEBUG   # log detail (latensi tiap tahap)
python -m jarvis.setup check         # cek semua dependensi
python -m jarvis.setup test-wake     # uji frasa pemanggil dengan suaramu (5 percobaan)
python -m jarvis.setup list-mics     # lihat daftar mikrofon
python -m jarvis.setup download-models  # unduh model wake word & Whisper (sekali, butuh internet)
```

---

## 🔁 Jalan Otomatis Saat Komputer Nyala

### macOS — launchd

Buat file `~/Library/LaunchAgents/com.jarvis.agent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.jarvis.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/NAMA_KAMU/jarvis/.venv/bin/python</string>
    <string>-m</string><string>jarvis</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/NAMA_KAMU/jarvis</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.jarvis.agent.plist
```

### Windows — Task Scheduler

```powershell
$action  = New-ScheduledTaskAction -Execute "$HOME\jarvis\.venv\Scripts\pythonw.exe" -Argument "-m jarvis" -WorkingDirectory "$HOME\jarvis"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Jarvis" -Action $action -Trigger $trigger
```

(`pythonw.exe` = tanpa jendela console.)

### Linux — systemd user service

`~/.config/systemd/user/jarvis.service`:

```ini
[Unit]
Description=Jarvis Voice Assistant
After=graphical-session.target

[Service]
WorkingDirectory=%h/jarvis
ExecStart=%h/jarvis/.venv/bin/python -m jarvis
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now jarvis
```

---

## 📦 Build Aplikasi (Installer)

```bash
uv sync --extra dev
uv run pyinstaller jarvis.spec
```

| OS | Hasil | Catatan |
|---|---|---|
| macOS | `dist/Jarvis.app` | Tambahkan `NSMicrophoneUsageDescription` di Info.plist; sign & notarize untuk distribusi |
| Windows | `dist/Jarvis/Jarvis.exe` | Bungkus jadi installer dengan **Inno Setup** |
| Linux | `dist/jarvis/jarvis` | Bungkus jadi **AppImage** / `.deb` |

> Ollama tetap diinstall terpisah oleh pengguna (tidak di-bundle).

---

## 🩺 Troubleshooting

| Masalah | Solusi |
|---|---|
| `PortAudio library not found` | Mac/Windows: install ulang `sounddevice` (`uv sync`); Linux: install `portaudio19-dev` |
| Jarvis tidak mendengar | Cek izin mic; jalankan `setup list-mics` lalu set `audio.input_device` |
| Sering terpanggil sendiri | Naikkan `wakeword.threshold` ke 0.6–0.7 |
| Tidak terpanggil | Turunkan `wakeword.threshold` ke 0.4; dekatkan mic |
| Jawaban lambat | Pakai `qwen3.5:4b`, turunkan `llm.num_ctx` ke 2048, cek `num_thread` |
| `Connection refused` ke Ollama | Jalankan `ollama serve` atau buka aplikasi Ollama |
| Suara TTS tidak keluar | Jalankan `setup download-voice` ulang; cek `tts.engine` |
| Ketik teks gagal di Mac | Beri izin **Accessibility** ke Terminal/Jarvis.app |
| Ketik teks gagal di Linux | Kamu di Wayland → pakai `ydotool` atau sesi X11 |
