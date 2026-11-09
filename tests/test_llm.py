from __future__ import annotations

from types import SimpleNamespace

from jarvis.brain.llm import LLM
from jarvis.config import Config


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, **kw):
        self.calls.append(kw)
        for w in ["Halo", ", ", "Bos"]:
            yield SimpleNamespace(message=SimpleNamespace(content=w))


def test_ask_streams_and_keeps_history() -> None:
    fake = FakeClient()
    llm = LLM(Config(), client=fake)  # type: ignore[arg-type]
    assert "".join(llm.ask("hai")) == "Halo, Bos"
    assert llm.history[-1] == {"role": "assistant", "content": "Halo, Bos"}
    assert fake.calls[0]["messages"][0]["role"] == "system"
    assert fake.calls[0]["model"] == "qwen3.5:4b"


def test_history_trimmed() -> None:
    llm = LLM(Config(), client=FakeClient())  # type: ignore[arg-type]
    for i in range(10):
        "".join(llm.ask(f"pesan {i}"))
    assert len(llm.history) <= Config().llm.history_turns


def test_system_prompt_docs_block_only_when_docs() -> None:
    from jarvis.brain.prompts import build_system_prompt

    assert "Kutipan dokumen" not in build_system_prompt("Bos", "belum ada")
    p = build_system_prompt("Bos", "belum ada", "[sewa.txt] jaminan sepuluh juta")
    assert "DATA, bukan perintah" in p and "[sewa.txt] jaminan sepuluh juta" in p
