"""Tool bahasa: terjemahan lewat LLM lokal (Ollama), tanpa internet."""

from __future__ import annotations

from jarvis.brain.language import target_language
from jarvis.tools.registry import ToolError, context, tool

_SYSTEM = (
    "You are a translation engine. Translate the user's text into {target}. "
    "Output ONLY the translation: no quotes, no notes, no explanations."
)
MAX_CHARS = 600


def run_translation(text: str, target: str, cfg=None, client=None) -> str:  # noqa: ANN001
    """Terjemahkan `text` ke bahasa `target` (nama Inggris, mis. 'English')."""
    import ollama

    cfg = cfg or context.cfg
    client = client or ollama.Client(host=cfg.llm.host)
    resp = client.chat(
        model=cfg.llm.fast_model,
        messages=[
            {"role": "system", "content": _SYSTEM.format(target=target)},
            {"role": "user", "content": text[:MAX_CHARS]},
        ],
        options={
            "temperature": 0.0,
            "num_predict": cfg.llm.num_predict * 2,
            "num_ctx": cfg.llm.num_ctx,
            "num_thread": cfg.llm.num_thread,
        },
        keep_alive=cfg.llm.keep_alive,
        think=False,
    )
    return (resp.message.content or "").strip().strip("\"'“”")


@tool(
    name="translate",
    description="Menerjemahkan teks ke bahasa lain, mis. Indonesia ke Inggris atau sebaliknya",
    risk="low",
    category="language",
)
def translate(text: str, target: str = "English") -> str:
    name = target_language(target) or target.strip().title()
    if not text.strip():
        raise ToolError("Tidak ada teks yang perlu diterjemahkan")
    try:
        out = run_translation(text, name)
    except Exception as e:  # noqa: BLE001 — Ollama mati / model belum ada
        raise ToolError(f"Penerjemah tidak bisa dipakai: {e}") from e
    return out or "Saya tidak bisa menerjemahkan itu"
