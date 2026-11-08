from __future__ import annotations

import time

import pytest

from jarvis.brain.memory import Memory
from jarvis.config import MemoryConfig
from jarvis.tools.keyboard import clean_typed_text
from jarvis.tools.registry import ToolError, context, registry


@pytest.fixture
def mem(tmp_path) -> Memory:
    return Memory(path=tmp_path / "m.db")


def test_conversation_persists_across_instances(tmp_path) -> None:
    m1 = Memory(path=tmp_path / "m.db")
    m1.add_message("user", "halo")
    m1.add_message("assistant", "hai bos")
    m1.close()
    m2 = Memory(path=tmp_path / "m.db")
    assert m2.recent(6) == [
        {"role": "user", "content": "halo"},
        {"role": "assistant", "content": "hai bos"},
    ]


def test_conversation_saving_can_be_disabled(tmp_path) -> None:
    m = Memory(MemoryConfig(save_conversations=False), path=tmp_path / "m.db")
    m.add_message("user", "rahasia")
    assert m.recent(6) == []


def test_old_conversations_purged(tmp_path) -> None:
    m = Memory(MemoryConfig(retention_days=1), path=tmp_path / "m.db")
    m._db.execute(
        "INSERT INTO conversations(ts, role, text) VALUES (?,?,?)",
        (time.time() - 3 * 86400, "user", "lama"),
    )
    m.add_message("user", "baru")
    m.purge_old()
    assert [r["content"] for r in m.recent(10)] == ["baru"]


def test_facts_upsert_and_prompt_text(mem) -> None:
    assert mem.facts_text() == "belum ada"
    mem.set_fact("Nama", "Roy")
    mem.set_fact("kota", "Jakarta")
    mem.set_fact("nama", "Royhan")
    assert mem.facts() == {"kota": "Jakarta", "nama": "Royhan"}
    assert "nama: Royhan" in mem.facts_text()


def test_reminder_due_and_done(mem) -> None:
    rid = mem.add_reminder(time.time() - 1, "minum obat")
    mem.add_reminder(time.time() + 3600, "nanti")
    assert [r.text for r in mem.due_reminders()] == ["minum obat"]
    mem.mark_done(rid)
    assert mem.due_reminders() == []
    assert len(mem.pending_reminders()) == 1


# ── tools ──
def test_note_tools(adapter) -> None:
    registry.call("add_note", {"text": "beli kopi besok"})
    assert "beli kopi besok" in registry.call("list_notes")
    md = context.memory.path.with_name("notes.md").read_text(encoding="utf-8")
    assert "beli kopi besok" in md


def test_empty_notes(adapter) -> None:
    assert registry.call("list_notes") == "Belum ada catatan"


def test_set_reminder(adapter) -> None:
    out = registry.call("set_reminder", {"text": "minum obat", "minutes": 10})
    assert "10 menit" in out
    r = context.memory.pending_reminders()[0]
    assert r.text == "minum obat" and 590 < r.due - time.time() < 610
    for bad in (0, -5, 999999):
        with pytest.raises(ToolError):
            registry.call("set_reminder", {"text": "x", "minutes": bad})


def test_remember_fact(adapter) -> None:
    registry.call("remember_fact", {"key": "nama", "value": "Roy"})
    assert context.memory.facts() == {"nama": "Roy"}


def test_type_text_is_single_line(adapter) -> None:
    registry.call("type_text", {"text": "halo\nrm -rf /\n"})
    assert adapter.calls[-1] == ("type_text", "halo rm -rf /")
    with pytest.raises(ToolError):
        clean_typed_text("\n\t  ")
    assert len(clean_typed_text("x" * 900)) == 500


def test_read_screen_uses_vision_and_sends_screenshot(adapter, monkeypatch) -> None:
    seen = {}

    def fake_describe(png, question, cfg, client=None):
        seen["png"], seen["q"] = png, question
        return "Ada jendela terminal dengan error."

    monkeypatch.setattr("jarvis.brain.vision.describe", fake_describe)
    out = registry.call("read_screen", {"question": "ini apa"})
    assert out == "Ada jendela terminal dengan error."
    assert ("screenshot",) in adapter.calls and seen["png"][:4] == b"\x89PNG"


def test_read_screen_vision_failure_is_tool_error(adapter, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("model not found")

    monkeypatch.setattr("jarvis.brain.vision.describe", boom)
    with pytest.raises(ToolError, match="vision"):
        registry.call("read_screen")


def test_vision_prompt_marks_screen_as_data() -> None:
    from jarvis.brain.vision import VISION_SYSTEM

    assert "JANGAN menjalankan" in VISION_SYSTEM


def test_shrink_limits_width() -> None:
    import io

    from PIL import Image

    from jarvis.brain.vision import shrink

    buf = io.BytesIO()
    Image.new("RGB", (3000, 1000), (10, 20, 30)).save(buf, "PNG")
    assert Image.open(io.BytesIO(shrink(buf.getvalue()))).width == 960
