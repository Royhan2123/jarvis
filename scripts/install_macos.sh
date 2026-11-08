#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Jarvis — Setup project macOS (Intel & Apple Silicon) TANPA Homebrew
# Homebrew sudah Tier 3 untuk Mac Intel sejak Sept 2026 (tidak ada paket siap pakai baru),
# jadi script ini memakai installer resmi masing-masing tool.
#
# Pakai (dari root project):  bash scripts/install_macos.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT="${1:-jarvis}"
# Dijalankan dari dalam folder project (ada CLAUDE.md)? Pakai folder ini.
if [ -z "${1:-}" ] && [ -f CLAUDE.md ]; then PROJECT="."; fi
# Dijalankan dari dalam folder scripts/? Pakai root project.
if [ -z "${1:-}" ] && [ -f ../CLAUDE.md ] && [ "$(basename "$PWD")" = "scripts" ]; then cd ..; PROJECT="."; fi
MODEL="qwen3.5:4b"

step() { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }

# 1. Xcode Command Line Tools (git, compiler) ──────────────────
step "1/7 Cek Xcode Command Line Tools (git)"
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Belum ada. Jendela install akan muncul: klik Install, tunggu selesai, lalu jalankan ulang script ini."
  xcode-select --install || true
  exit 1
fi
git --version

# 2. uv (pengelola Python & library) ───────────────────────────
step "2/7 Cek uv (Python dikelola uv, tidak perlu install Python manual)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv --version

# 3. Ollama + model ────────────────────────────────────────────
step "3/7 Cek Ollama & download $MODEL (±3.4 GB, sabar ya)"
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama belum terpasang."
  echo "1) Halaman download akan terbuka → download Ollama untuk macOS"
  echo "2) Pindahkan Ollama.app ke folder Applications, buka sekali"
  echo "3) Jalankan ulang script ini"
  open "https://ollama.com/download" || true
  exit 1
fi
if ! curl -s http://localhost:11434 >/dev/null 2>&1; then
  open -a Ollama >/dev/null 2>&1 || (ollama serve >/dev/null 2>&1 &)
fi
for _ in $(seq 1 30); do
  curl -s http://localhost:11434 >/dev/null 2>&1 && break
  sleep 1
done
ollama pull "$MODEL"

# 4. Struktur folder ───────────────────────────────────────────
step "4/7 Buat struktur project ./$PROJECT"
if [ -e "$PROJECT/pyproject.toml" ]; then
  echo "Folder $PROJECT sudah berisi project. Dihentikan supaya tidak menimpa file kamu."
  exit 1
fi
mkdir -p "$PROJECT" && cd "$PROJECT"
mkdir -p jarvis/{audio/sounds,stt,brain,tools,platform,tts,ui} docs models scripts tests
for d in jarvis jarvis/audio jarvis/stt jarvis/brain jarvis/tools jarvis/platform jarvis/tts jarvis/ui; do
  touch "$d/__init__.py"
done

# 5. File dasar ────────────────────────────────────────────────
step "5/7 Tulis pyproject.toml, config.yaml, .gitignore, __main__.py"

cat > pyproject.toml <<'EOF'
[project]
name = "jarvis"
version = "0.1.0"
description = "Asisten suara AI offline, cross-platform"
requires-python = ">=3.11,<3.13"
dependencies = [
  "ollama>=0.4",
  "sounddevice>=0.4",
  "numpy>=1.26",
  "pyyaml>=6.0",
  "pydantic>=2.6",
  "platformdirs>=4.2",
  "loguru>=0.7",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.4"]

[project.scripts]
jarvis = "jarvis.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["jarvis"]

[tool.ruff]
line-length = 100
EOF

cat > config.yaml <<'EOF'
# Config minimal untuk Fase 0. Versi lengkap ada di docs/CONFIG.md
general:
  name: "Jarvis"
  language: "id"

llm:
  host: "http://localhost:11434"
  fast_model: "qwen3.5:4b"
  smart_model: "qwen3.5:9b"
  temperature: 0.3
  num_ctx: 4096
  num_predict: 200
  keep_alive: -1

tts:
  gender: "female"
EOF

cat > .gitignore <<'EOF'
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
dist/
build/
models/*
!models/.gitkeep
*.log
.DS_Store
.claude/settings.local.json
EOF
touch models/.gitkeep

cat > jarvis/__main__.py <<'EOF'
"""Jarvis — Fase 0: mode teks + cek sistem.

Jalankan:
  uv run python -m jarvis --check     # cek mic & Ollama
  uv run python -m jarvis             # ngobrol lewat ketikan
  uv run python -m jarvis --voice     # ngobrol + jawaban dibacakan (macOS)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import ollama
import yaml

SYSTEM_PROMPT = (
    "Kamu adalah Jarvis, asisten suara di komputer pengguna. "
    "Jawab dalam bahasa Indonesia santai dan singkat (maksimal 2-3 kalimat), "
    "tanpa markdown atau emoji, karena jawabanmu akan dibacakan."
)

MAC_VOICES = {"female": "Damayanti", "male": None}


def load_config(path: str) -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def check(cfg: dict) -> bool:
    ok = True
    print("── Mikrofon & speaker ──")
    try:
        import sounddevice as sd

        print(sd.query_devices())
    except Exception as e:  # noqa: BLE001
        print(f"❌ Audio bermasalah: {e}")
        ok = False

    print("\n── Ollama ──")
    try:
        models = [m.model for m in ollama.list().models]
        print("Model terpasang:", ", ".join(models) or "(kosong)")
        want = cfg.get("llm", {}).get("fast_model", "qwen3.5:4b")
        if want not in models:
            print(f"⚠️  Model {want} belum ada. Jalankan: ollama pull {want}")
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"❌ Tidak bisa terhubung ke Ollama: {e}")
        print("   Buka aplikasi Ollama, atau jalankan: ollama serve")
        ok = False

    print("\n✅ Semua siap!" if ok else "\n⚠️  Ada yang perlu dibereskan dulu.")
    return ok


def speak(text: str, gender: str) -> None:
    if sys.platform == "darwin" and shutil.which("say"):
        voice = MAC_VOICES.get(gender)
        cmd = ["say", "-r", "185"] + (["-v", voice] if voice else []) + [text]
        subprocess.run(cmd, check=False)
    else:
        print("(Suara di Fase 0 baru untuk macOS. Windows/Linux menyusul di Fase 1.)")


def chat(cfg: dict, voice: bool) -> None:
    llm = cfg.get("llm", {})
    model = llm.get("fast_model", "qwen3.5:4b")
    options = {
        "temperature": llm.get("temperature", 0.3),
        "num_ctx": llm.get("num_ctx", 4096),
        "num_predict": llm.get("num_predict", 200),
    }
    gender = cfg.get("tts", {}).get("gender", "female")
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"🤖 Jarvis siap (model: {model}). Ketik 'keluar' untuk berhenti.")
    while True:
        try:
            text = input("\nKamu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"keluar", "exit", "quit"}:
            break
        if not text:
            continue

        history.append({"role": "user", "content": text})
        print("Jarvis: ", end="", flush=True)
        reply = ""
        for chunk in ollama.chat(
            model=model,
            messages=history,
            stream=True,
            options=options,
            keep_alive=llm.get("keep_alive", -1),
        ):
            piece = chunk.message.content or ""
            reply += piece
            print(piece, end="", flush=True)
        print()

        history.append({"role": "assistant", "content": reply})
        history = [history[0]] + history[-12:]  # ingat 6 percakapan terakhir

        if voice and reply.strip():
            speak(reply, gender)


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("--check", action="store_true", help="cek mic & Ollama")
    ap.add_argument("--voice", action="store_true", help="bacakan jawaban")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.check:
        sys.exit(0 if check(cfg) else 1)
    chat(cfg, voice=args.voice)


if __name__ == "__main__":
    main()
EOF

# 6. Python env ────────────────────────────────────────────────
step "6/7 Siapkan Python 3.12 + install dependensi"
uv python install 3.12
uv python pin 3.12
uv sync --extra dev

# 7. Git ───────────────────────────────────────────────────────
step "7/7 Init git"
git init -q
git add .
git commit -qm "chore: bootstrap project Jarvis (Fase 0)" || true

printf "\n\033[1;32m✅ Project siap di ./%s\033[0m\n" "$PROJECT"
echo
echo "Langkah berikutnya:"
[ "$PROJECT" != "." ] && echo "  cd $PROJECT"
echo "  uv run python -m jarvis --check     # cek mic & Ollama"
echo "  uv run python -m jarvis --voice     # ngobrol + Jarvis ngomong"
[ -f CLAUDE.md ] || echo "Jangan lupa: copy CLAUDE.md & folder docs/ ke project ini"
