"""Wrapper Ollama: chat berstreaming + riwayat percakapan terbatas."""

from __future__ import annotations

from collections.abc import Iterator

import ollama

from jarvis.brain.prompts import build_system_prompt
from jarvis.config import Config


class LLM:
    def __init__(self, cfg: Config, client: ollama.Client | None = None) -> None:
        self.cfg = cfg
        self.client = client or ollama.Client(host=cfg.llm.host)
        self.history: list[dict[str, str]] = []

    def _options(self) -> dict:
        c = self.cfg.llm
        return {
            "temperature": c.temperature,
            "top_p": c.top_p,
            "top_k": c.top_k,
            "num_ctx": c.num_ctx,
            "num_predict": c.num_predict,
            "num_thread": c.num_thread,
        }

    def _trim(self) -> None:
        self.history = self.history[-self.cfg.llm.history_turns :]

    def ask(self, text: str, model: str | None = None) -> Iterator[str]:
        """Kirim pesan, yield potongan jawaban. Riwayat disimpan setelah selesai."""
        c = self.cfg.llm
        self.history.append({"role": "user", "content": text})
        self._trim()
        messages = [
            {"role": "system", "content": build_system_prompt(self.cfg.general.user_title)},
            *self.history,
        ]
        reply = ""
        for chunk in self.client.chat(
            model=model or c.fast_model,
            messages=messages,
            stream=True,
            options=self._options(),
            keep_alive=c.keep_alive,
            think=c.think,
        ):
            piece = chunk.message.content or ""
            reply += piece
            yield piece
        self.history.append({"role": "assistant", "content": reply})
        self._trim()
