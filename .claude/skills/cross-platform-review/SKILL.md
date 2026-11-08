---
name: cross-platform-review
description: Review perubahan kode agar tetap jalan di macOS, Windows, dan Linux (X11/Wayland) sebelum commit. Pakai setelah mengubah jarvis/platform/, jarvis/tools/, audio, TTS, path file, atau dependensi.
allowed-tools: Read Grep Glob Bash(git diff *)
---

# Review Cross-Platform

Lihat perubahan dengan `git diff` (staged + unstaged). Periksa hanya file yang berubah.

## Checklist

**Struktur**
- [ ] Tidak ada `sys.platform` / `platform.system()` di luar `jarvis/platform/`
- [ ] Method baru di `base.py` diimplementasikan di ketiga adapter (atau `NotImplementedError` + dicatat)

**Path & file**
- [ ] Pakai `pathlib.Path` / `platformdirs`, tidak ada `"~/"`, `"/tmp"`, atau `\\` hardcode
- [ ] Encoding file eksplisit: `open(..., encoding="utf-8")`

**Proses & perintah**
- [ ] `subprocess` dipanggil dengan list argumen, bukan string + `shell=True`
- [ ] Perintah khusus OS dicek dulu dengan `shutil.which()` dan punya fallback / pesan error jelas
- [ ] Linux: ada jalur Wayland (`ydotool`, `grim`/portal, `wl-clipboard`) bila menyentuh keyboard/layar/clipboard

**Dependensi**
- [ ] Paket khusus OS memakai marker di `pyproject.toml` (`; sys_platform == 'win32'`)
- [ ] Tidak menambah paket yang butuh PyTorch (Mac Intel)
- [ ] Import paket khusus OS dilakukan di dalam adapter OS-nya, bukan di level modul umum

**Audio**
- [ ] Sample rate 16 kHz, mono, `int16`/`float32` konsisten
- [ ] Device audio dari config, tidak hardcode index

## Output

Daftar temuan singkat: `file:baris — masalah — saran perbaikan`. Jika bersih, tulis "✅ Aman cross-platform".
