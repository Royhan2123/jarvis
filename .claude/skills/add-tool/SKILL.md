---
name: add-tool
description: Prosedur menambah perintah suara / tool baru ke Jarvis (registry, risk level, adapter macOS/Windows/Linux, rule regex, test, dokumentasi). Pakai saat membuat atau mengubah file di jarvis/tools/ atau jarvis/platform/.
argument-hint: "[nama tool] [deskripsi singkat]"
---

# Tambah Tool Jarvis

Tool: `$ARGUMENTS`

## Checklist (urut)

1. **Cek dulu** `docs/COMMANDS.md`: apakah tool sudah direncanakan? Ikuti implementasi per OS di sana.
2. **Tentukan risk**: `low` (langsung), `medium` (jalan + notifikasi), `high` (wajib konfirmasi suara).
   Aksi yang menghapus, mematikan, mengirim, atau membeli = `high`.
3. **Adapter OS**: jika aksi berbeda per OS, tambah method abstrak di `jarvis/platform/base.py`,
   lalu implementasi di `macos.py`, `windows.py`, `linux.py`.
   - OS yang belum bisa → `raise NotImplementedError("…alasan…")` + catat di `docs/COMMANDS.md`.
   - Linux: sediakan jalur X11 **dan** Wayland bila relevan.
4. **Tool** di `jarvis/tools/<kategori>.py`:

   ```python
   @tool(name="set_volume", description="Mengatur volume suara komputer (0-100)", risk="low")
   def set_volume(percent: int) -> str:
       adapter.set_volume(max(0, min(100, percent)))
       return f"Volume diatur ke {percent} persen"
   ```

   - Argumen bertipe jelas (dipakai untuk JSON schema LLM + validasi pydantic).
   - `description` dalam bahasa Indonesia, singkat, jelas kapan dipakai (LLM 4B membacanya).
   - Return = kalimat pendek yang enak **diucapkan** (tanpa markdown/emoji).
5. **Rule cepat (opsional)**: jika perintah umum & bisa dikenali regex, tambah pola di
   `jarvis/brain/rules.py` agar tidak perlu LLM.
6. **Test** di `tests/test_tools.py` memakai mock adapter. **Jangan** pernah benar-benar
   shutdown / ubah volume / ketik saat test.
7. **Dokumentasi**: update tabel di `docs/COMMANDS.md` (contoh ucapan, risk, tier, implementasi per OS).

## Larangan

- Tidak ada tool yang menjalankan shell bebas atau `eval/exec` dari teks user/LLM.
- Jangan memanggil `sys.platform` di luar `jarvis/platform/`.
