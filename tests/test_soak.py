"""Penjaga kebocoran memori: ribuan putaran jalur teks/aksi tidak boleh menambah memori Python."""

from __future__ import annotations

import gc
import tracemalloc
from types import SimpleNamespace

from jarvis.brain import rules
from jarvis.brain.actions import ActionRunner
from jarvis.brain.llm import LLM
from jarvis.brain.replies_en import to_english
from jarvis.brain.rules import Intent
from jarvis.config import Config
from jarvis.state_hub import HUB
from jarvis.tools.registry import context
from jarvis.tts.stream import speakable

PHRASES = [
    "jam berapa sekarang", "volume 40 persen", "buka kalkulator dan tutup safari",
    "what time is it", "terjemahkan ke bahasa Inggris selamat pagi",
    "putar lagu dewa 19 di youtube", "ganti bahasa ke Jepang", "catat beli kopi besok",
    "Sekarang jam 19.43, baterai 80 persen, 3,14159265", "open Chrome",
]  # fmt: skip


class FakeClient:
    def chat(self, **kw):  # noqa: ANN003, ANN201
        yield SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))


def _round(llm: LLM, runner: ActionRunner, i: int) -> None:
    text = PHRASES[i % len(PHRASES)]
    rules.match(text)
    speakable(text)
    to_english("Sekarang jam 22.20")
    list(llm.ask(text))
    runner.run([Intent("get_time", {"what": "time"})])
    HUB.publish(["idle", "listening", "thinking", "speaking"][i % 4])


def test_thousands_of_rounds_do_not_grow_python_memory(adapter) -> None:
    context.configure(adapter, Config(), context.memory)
    llm, runner = LLM(Config(), client=FakeClient()), ActionRunner()
    for i in range(300):  # pemanasan: cache regex, impor malas, dsb.
        _round(llm, runner, i)
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    for i in range(3000):
        _round(llm, runner, i)
    gc.collect()
    growth = sum(s.size_diff for s in tracemalloc.take_snapshot().compare_to(before, "filename"))
    tracemalloc.stop()
    assert growth < 1_500_000, f"memori Python tumbuh {growth / 1e6:.1f} MB dalam 3000 putaran"
    assert len(llm.history) <= Config().llm.history_turns  # riwayat tidak menumpuk
