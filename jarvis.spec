# PyInstaller spec — build: uv run pyinstaller jarvis.spec
# Hasil: dist/Jarvis (folder) · macOS: dist/Jarvis.app
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
for pkg in ("faster_whisper", "openwakeword", "piper", "certifi"):
    datas += collect_data_files(pkg)
datas += [("config.yaml", ".")]

hiddenimports = (
    collect_submodules("jarvis.tools")
    + collect_submodules("jarvis.platform")
    + ["pystray._darwin", "pystray._win32", "pystray._xorg", "pystray._appindicator"]
)

a = Analysis(
    ["jarvis/__main__.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["torch", "tensorflow", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jarvis",
    console=True,  # tetap console agar log & mode teks terlihat; ganti False untuk tray-only
)
coll = COLLECT(exe, a.binaries, a.datas, name="Jarvis")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Jarvis.app",
        bundle_identifier="id.jarvis.assistant",
        info_plist={
            "NSMicrophoneUsageDescription": "Jarvis mendengarkan perintah suara kamu.",
            "NSAppleEventsUsageDescription": "Jarvis mengontrol aplikasi seperti Spotify/Music.",
            "LSUIElement": False,
        },
    )
