#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Jarvis — pemasang satu baris untuk macOS & Linux. TANPA sudo, TANPA Homebrew, TANPA Node.js.
#
#   curl -LsSf https://raw.githubusercontent.com/Royhan2123/jarvis/main/scripts/install.sh | bash
#
# Yang dilakukan: memasang uv (ke folder pengguna) → mengunduh kode Jarvis → menyiapkan Python &
# paket → mengunduh model suara → membuat config.yaml awal (API lokal aktif) dan peluncur run.sh
# yang dipakai Isla Desk. Aman dijalankan ulang (memperbarui kode, config.yaml kamu tidak disentuh).
#
# Variabel opsional:
#   JARVIS_SOURCE_URL   arsip .tar.gz kode Jarvis (bawaan: GitHub main)
#   JARVIS_SOURCE_DIR   salin dari folder lokal, bukan unduh (untuk uji / offline)
#   JARVIS_SKIP_MODELS  isi apa saja = lewati unduhan model besar
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SOURCE_URL="${JARVIS_SOURCE_URL:-https://github.com/Royhan2123/jarvis/archive/refs/heads/main.tar.gz}"
OS="$(uname -s)"
case "$OS" in
  Darwin) DEFAULT_HOME="$HOME/Library/Application Support/jarvis-app" ;;
  Linux)  DEFAULT_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/jarvis-app" ;;
  *) echo "Sistem $OS tidak didukung skrip ini (Windows: pakai install.ps1)." >&2; exit 1 ;;
esac
HOME_DIR="${JARVIS_HOME:-$DEFAULT_HOME}"
APP="$HOME_DIR/app"

step() { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[1;33m!  %s\033[0m\n" "$1"; }

case "$(uname -m)" in
  x86_64|amd64|arm64|aarch64) ;;
  *) echo "Arsitektur $(uname -m) belum didukung." >&2; exit 1 ;;
esac

# 1. uv ────────────────────────────────────────────────────────────────────────
step "1/6 Cek uv (mengurus Python, tidak perlu install Python manual)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  command -v curl >/dev/null 2>&1 || { echo "curl tidak ada; pasang curl dulu." >&2; exit 1; }
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv --version

# 2. Kode ──────────────────────────────────────────────────────────────────────
step "2/6 Siapkan kode Jarvis di $APP"
mkdir -p "$HOME_DIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [ -n "${JARVIS_SOURCE_DIR:-}" ]; then
  mkdir -p "$TMP/src"
  tar -C "$JARVIS_SOURCE_DIR" --exclude=.venv --exclude=.git --exclude=__pycache__ \
      --exclude=config.yaml --exclude=.ruff_cache --exclude=.pytest_cache -cf - . | tar -C "$TMP/src" -xf -
else
  curl -LsSf "$SOURCE_URL" -o "$TMP/src.tar.gz"
  mkdir -p "$TMP/src"
  tar -xzf "$TMP/src.tar.gz" -C "$TMP/src" --strip-components=1
  rm -f "$TMP/src/config.yaml"  # config milik pengembang tidak ikut; dibuat baru di bawah
fi
[ -f "$TMP/src/pyproject.toml" ] || { echo "Arsip kode tidak valid (pyproject.toml tidak ada)." >&2; exit 1; }
mkdir -p "$APP"
# Perbarui kode, pertahankan config.yaml dan .venv milik pengguna.
for item in "$APP"/* "$APP"/.[!.]*; do
  [ -e "$item" ] || continue
  case "$(basename "$item")" in config.yaml|.venv) ;; *) rm -rf "$item" ;; esac
done
cp -R "$TMP/src/." "$APP/"

# 3. Python & paket ────────────────────────────────────────────────────────────
step "3/6 Pasang Python & paket (pertama kali ±1–3 menit)"
(cd "$APP" && uv sync)

# 4. Audio (Linux) ─────────────────────────────────────────────────────────────
if [ "$OS" = "Linux" ]; then
  step "4/6 Cek pustaka audio"
  if ! (ldconfig -p 2>/dev/null | grep -q libportaudio); then
    warn "PortAudio belum ada. Pasang SEKALI (butuh sudo, tidak saya jalankan otomatis):"
    echo "    Debian/Ubuntu: sudo apt install libportaudio2"
    echo "    Fedora:        sudo dnf install portaudio"
    echo "    Arch:          sudo pacman -S portaudio"
  else
    echo "PortAudio ada."
  fi
else
  step "4/6 Audio: tidak perlu pustaka tambahan di macOS"
fi

# 5. Model ─────────────────────────────────────────────────────────────────────
step "5/6 Model suara"
if [ -n "${JARVIS_SKIP_MODELS:-}" ]; then
  warn "JARVIS_SKIP_MODELS aktif: unduhan model dilewati."
else
  (cd "$APP" && uv run python -m jarvis.setup download-voice && uv run python -m jarvis.setup download-models) \
    || warn "Unduhan model gagal. Ulangi nanti: jalankan skrip ini lagi."
fi

# 6. Config & peluncur ─────────────────────────────────────────────────────────
step "6/6 Config awal & peluncur"
if [ ! -f "$APP/config.yaml" ]; then
  cat > "$APP/config.yaml" <<'YAML'
# Dibuat oleh pemasang. Bawaan: offline penuh (Ollama lokal). Semua parameter: docs/CONFIG.md
ui:
  api:
    enabled: true   # dibutuhkan Isla Desk untuk berbicara dengan Jarvis (hanya 127.0.0.1)
YAML
  echo "config.yaml dibuat."
else
  echo "config.yaml sudah ada, tidak diubah."
fi
cat > "$HOME_DIR/run.sh" <<'RUN'
#!/usr/bin/env bash
# Peluncur Jarvis (dipakai Isla Desk). Jalan di latar: pipeline suara + API lokal.
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/app" || exit 1
exec uv run python -m jarvis --listen --config config.yaml "$@"
RUN
chmod +x "$HOME_DIR/run.sh"

if command -v ollama >/dev/null 2>&1; then
  echo "Ollama terdeteksi. Model bawaan: ollama pull qwen3.5:4b (±3,4 GB), jalankan bila belum."
else
  warn "Ollama belum terpasang (https://ollama.com/download). Tanpa Ollama, pilih penyedia online"
  warn "(kunci API milikmu) di Setelan Isla Desk → Otak Jarvis."
fi

printf "\n\033[1;32m✅ Jarvis terpasang di %s\033[0m\n" "$HOME_DIR"
echo "Jalankan manual:  \"$HOME_DIR/run.sh\"   — atau biarkan Isla Desk yang menjalankannya."
