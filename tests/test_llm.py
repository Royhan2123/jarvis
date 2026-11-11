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


def test_prompt_is_short_static_and_context_only_when_needed() -> None:
    from jarvis.brain.prompts import context_line, static_system_prompt

    p = static_system_prompt("Bos")
    assert "Waktu" not in p and "Info pengguna" not in p
    assert len(p.split()) < 80  # tiap token ±30 ms di CPU
    assert context_line("belum ada", "", "apa ibu kota Jepang") == ""  # tanpa info: tanpa token
    assert "Info pengguna: nama: Roy" in context_line("nama: Roy", "", "halo")
    assert "Waktu:" in context_line("belum ada", "", "hari apa besok?")
    assert "[sewa.txt]" in context_line("belum ada", "[sewa.txt] jaminan", "berapa jaminan")


def test_ask_sends_compact_prompt_and_context_only_in_last_message() -> None:
    from types import SimpleNamespace

    from jarvis.brain.llm import LLM
    from jarvis.config import Config

    sent: list[list[dict]] = []

    class Client:
        def chat(self, **kw):  # noqa: ANN003, ANN202
            sent.append(kw["messages"])
            yield SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))

    llm = LLM(Config(), client=Client(), facts=lambda: "nama: Roy")
    list(llm.ask("hari apa besok?"))
    msgs = sent[0]
    assert msgs[0]["role"] == "system" and "Waktu" not in msgs[0]["content"]
    assert "Waktu:" in msgs[-1]["content"] and msgs[-1]["content"].endswith("hari apa besok?")
    assert llm.history[0] == {"role": "user", "content": "hari apa besok?"}  # riwayat polos
