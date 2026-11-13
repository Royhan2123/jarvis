# ─────────────────────────────────────────────────────────────────────────────
# Jarvis — pemasang satu baris untuk Windows (PowerShell). TANPA admin, TANPA Node.js.
#
#   irm https://raw.githubusercontent.com/Royhan2123/jarvis/main/scripts/install.ps1 | iex
#
# Memasang uv (ke folder pengguna) → mengunduh kode Jarvis → menyiapkan Python & paket →
# mengunduh model suara → membuat config.yaml awal (API lokal aktif) dan peluncur run.cmd yang
# dipakai Isla Desk. Aman dijalankan ulang (config.yaml kamu tidak disentuh).
#
# Variabel lingkungan opsional: JARVIS_SOURCE_URL (arsip .zip), JARVIS_SOURCE_DIR (salin dari
# folder lokal), JARVIS_SKIP_MODELS (isi apa saja = lewati unduhan model), JARVIS_HOME.
# ─────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$SourceUrl = if ($env:JARVIS_SOURCE_URL) { $env:JARVIS_SOURCE_URL } else { "https://github.com/Royhan2123/jarvis/archive/refs/heads/main.zip" }
$HomeDir = if ($env:JARVIS_HOME) { $env:JARVIS_HOME } else { Join-Path $env:LOCALAPPDATA "jarvis-app" }
$App = Join-Path $HomeDir "app"

function Step($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Warn($t) { Write-Host "!  $t" -ForegroundColor Yellow }

# 1. uv ────────────────────────────────────────────────────────────────────────
Step "1/5 Cek uv (mengurus Python, tidak perlu install Python manual)"
$uvBin = Join-Path $env:USERPROFILE ".local\bin"
$env:Path = "$uvBin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$uvBin;$env:Path"
}
uv --version

# 2. Kode ──────────────────────────────────────────────────────────────────────
Step "2/5 Siapkan kode Jarvis di $App"
New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("jarvis-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
    $Src = Join-Path $Tmp "src"
    if ($env:JARVIS_SOURCE_DIR) {
        New-Item -ItemType Directory -Force -Path $Src | Out-Null
        robocopy $env:JARVIS_SOURCE_DIR $Src /E /XD .venv .git __pycache__ .ruff_cache .pytest_cache /XF config.yaml /NFL /NDL /NJH /NJS | Out-Null
    } else {
        $Zip = Join-Path $Tmp "src.zip"
        Invoke-WebRequest -Uri $SourceUrl -OutFile $Zip -UseBasicParsing
        Expand-Archive -Path $Zip -DestinationPath $Tmp -Force
        $Inner = Get-ChildItem $Tmp -Directory | Where-Object { $_.Name -ne "src" } | Select-Object -First 1
        Move-Item $Inner.FullName $Src
        Remove-Item (Join-Path $Src "config.yaml") -ErrorAction SilentlyContinue  # config pengembang tidak ikut
    }
    if (-not (Test-Path (Join-Path $Src "pyproject.toml"))) { throw "Arsip kode tidak valid (pyproject.toml tidak ada)." }
    New-Item -ItemType Directory -Force -Path $App | Out-Null
    # Perbarui kode, pertahankan config.yaml dan .venv milik pengguna.
    Get-ChildItem $App -Force | Where-Object { $_.Name -notin @("config.yaml", ".venv") } | Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $Src "*") -Destination $App -Recurse -Force
} finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Python & paket ────────────────────────────────────────────────────────────
Step "3/5 Pasang Python & paket (pertama kali ±1-3 menit)"
Push-Location $App
try { uv sync; if ($LASTEXITCODE -ne 0) { throw "uv sync gagal" } } finally { Pop-Location }

# 4. Model ─────────────────────────────────────────────────────────────────────
Step "4/5 Model suara"
if ($env:JARVIS_SKIP_MODELS) {
    Warn "JARVIS_SKIP_MODELS aktif: unduhan model dilewati."
} else {
    Push-Location $App
    try {
        uv run python -m jarvis.setup download-voice
        uv run python -m jarvis.setup download-models
        if ($LASTEXITCODE -ne 0) { Warn "Unduhan model gagal. Ulangi nanti: jalankan skrip ini lagi." }
    } finally { Pop-Location }
}

# 5. Config & peluncur ─────────────────────────────────────────────────────────
Step "5/5 Config awal & peluncur"
$Cfg = Join-Path $App "config.yaml"
if (-not (Test-Path $Cfg)) {
    @"
# Dibuat oleh pemasang. Bawaan: offline penuh (Ollama lokal). Semua parameter: docs/CONFIG.md
ui:
  api:
    enabled: true   # dibutuhkan Isla Desk untuk berbicara dengan Jarvis (hanya 127.0.0.1)
"@ | Set-Content -Path $Cfg -Encoding UTF8
    Write-Host "config.yaml dibuat."
} else {
    Write-Host "config.yaml sudah ada, tidak diubah."
}
@"
@echo off
rem Peluncur Jarvis (dipakai Isla Desk). Jalan di latar: pipeline suara + API lokal.
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd /d "%~dp0app" || exit /b 1
uv run python -m jarvis --listen --config config.yaml %*
"@ | Set-Content -Path (Join-Path $HomeDir "run.cmd") -Encoding ASCII

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama terdeteksi. Model bawaan: ollama pull qwen3.5:4b (±3,4 GB), jalankan bila belum."
} else {
    Warn "Ollama belum terpasang (https://ollama.com/download). Tanpa Ollama, pilih penyedia online"
    Warn "(kunci API milikmu) di Setelan Isla Desk -> Otak Jarvis."
}
Write-Host "`nJarvis terpasang di $HomeDir" -ForegroundColor Green
Write-Host "Jalankan manual: `"$HomeDir\run.cmd`"  - atau biarkan Isla Desk yang menjalankannya."
