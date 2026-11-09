from __future__ import annotations

import pytest

from jarvis import workspace
from jarvis.brain.actions import ActionRunner
from jarvis.brain.rules import Intent, match
from jarvis.config import Config
from jarvis.tools import messaging
from jarvis.tools.registry import ConfirmationRequired, ToolError, context, registry

CODE = "def halo():\n    return 'dunia'\n\n\ndef main():\n    print(halo())\n"


@pytest.fixture
def ws(adapter, tmp_path):
    root = tmp_path / "proyek"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(CODE)
    (root / ".env").write_text("RAHASIA=1")
    (root / "gambar.png").write_bytes(b"\x89PNG")
    outside = tmp_path / "luar.py"
    outside.write_text("x = 1")
    (root / "link.py").symlink_to(outside)
    cfg = Config()
    cfg.workspace.folders = [str(root)]
    context.configure(adapter, cfg, context.memory)
    return cfg, root


def test_find_by_name_and_denied_cases(ws) -> None:
    cfg, root = ws
    assert workspace.find_file(cfg, "app.py") == (root / "src" / "app.py").resolve()
    for bad in [".env", "gambar.png", "link.py", "/etc/hosts"]:
        with pytest.raises(workspace.WorkspaceError):
            workspace.find_file(cfg, bad)


def test_list_dir_hides_protected(ws) -> None:
    cfg, _ = ws
    out = workspace.list_dir(cfg)
    assert "src/" in out and ".env" not in out
    with pytest.raises(workspace.WorkspaceError):
        workspace.list_dir(cfg, "../")


def test_replace_unique_with_backup(ws) -> None:
    cfg, root = ws
    msg = workspace.replace_in_file(cfg, "app.py", "return 'dunia'", "return 'semesta'")
    assert "app.py.jarvis-bak" in msg
    assert "semesta" in (root / "src" / "app.py").read_text()
    assert (root / "src" / "app.py.jarvis-bak").read_text() == CODE


def test_replace_rejects_missing_or_ambiguous(ws) -> None:
    cfg, root = ws
    with pytest.raises(workspace.WorkspaceError, match="tidak ditemukan"):
        workspace.replace_in_file(cfg, "app.py", "tidak ada", "x")
    (root / "src" / "dua.py").write_text("a = 1\na = 1\n")
    with pytest.raises(workspace.WorkspaceError, match="2 kali"):
        workspace.replace_in_file(cfg, "dua.py", "a = 1", "a = 2")
    assert (root / "src" / "dua.py").read_text() == "a = 1\na = 1\n"


def test_create_file_never_overwrites(ws) -> None:
    cfg, root = ws
    workspace.create_file(cfg, "src/baru.py", "print(1)\n")
    assert (root / "src" / "baru.py").read_text() == "print(1)\n"
    with pytest.raises(workspace.WorkspaceError, match="sudah ada"):
        workspace.create_file(cfg, "src/baru.py", "x")
    with pytest.raises(workspace.WorkspaceError):
        workspace.create_file(cfg, "../keluar.py", "x")
    with pytest.raises(workspace.WorkspaceError):
        workspace.create_file(cfg, ".env", "x")


def test_mentioned_files_and_context(ws) -> None:
    cfg, _ = ws
    assert [p.name for p in workspace.mentioned_files(cfg, "jelaskan app titik py")] == ["app.py"]
    assert workspace.mentioned_files(cfg, "jelaskan resep.py") == []
    ctx = workspace.file_context(cfg, "apa isi baris 5 sampai 6 di app.py")
    assert "5: def main():" in ctx and "1: def halo" not in ctx and "BUKAN bagian kode" in ctx


def test_edit_tools_need_voice_confirmation(ws) -> None:
    _, root = ws
    args = {"path": "app.py", "old": "dunia", "new": "x"}
    with pytest.raises(ConfirmationRequired):
        registry.call("replace_in_file", args)
    assert "dunia" in (root / "src" / "app.py").read_text()  # belum berubah
    runner = ActionRunner()
    reply = runner.execute(Intent("replace_in_file", args))
    assert "mengubah file app.py" in reply and runner.pending
    assert "sudah diubah" in runner.resolve(True)
    runner.execute(Intent("replace_in_file", {**args, "old": "x", "new": "y"}))
    assert runner.resolve(None).startswith("Saya tidak mendengar")


def test_whatsapp_draft(adapter, monkeypatch) -> None:
    cfg = Config()
    cfg.messaging.contacts = {"Budi": "+62 812-3456-7890"}
    context.configure(adapter, cfg, context.memory)
    opened: list[str] = []
    monkeypatch.setattr(messaging.webbrowser, "open", lambda u: opened.append(u) or True)
    out = registry.call("whatsapp_draft", {"contact": "budi", "message": "Halo\nBos & kawan"})
    assert "tinggal kamu kirim" in out
    assert opened == ["https://wa.me/6281234567890?text=Halo%20Bos%20%26%20kawan"]
    with pytest.raises(ToolError, match="tidak dikenal"):
        registry.call("whatsapp_draft", {"contact": "Siti", "message": "hai"})


def test_whatsapp_voice_rule() -> None:
    assert match("Kirim pesan WhatsApp ke Budi isinya Besok rapat jam 9") == [
        Intent("whatsapp_draft", {"contact": "Budi", "message": "Besok rapat jam 9"})
    ]
    assert match("tolong tulis wa ke siti: Aku telat")[0].args["contact"] == "siti"
    assert match("kirim email ke budi") is None


def test_stt_hint_lists_recent_safe_names(ws) -> None:
    cfg, root = ws
    hint = workspace.stt_hint(cfg)
    assert "app.py" in hint and ".env" not in hint and "gambar.png" not in hint
    assert workspace.stt_hint(Config()) == ""


def test_code_request_detection() -> None:
    assert workspace.looks_like_code_request("ada bug di toko titik py")
    assert workspace.looks_like_code_request("perbaiki fungsi total")
    assert not workspace.looks_like_code_request("jam berapa sekarang")
