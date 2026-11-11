"""Tool bahasa: terjemahan lewat LLM lokal (Ollama), tanpa internet."""

from __future__ import annotations

import re

from jarvis.brain.language import WHISPER_LANGUAGES, target_language
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


def _barely_translated(source: str, out: str) -> bool:
    """True bila hasil hampir sama dengan sumber (model kecil kadang gagal untuk bahasa langka)."""
    a = set(re.findall(r"\w+", source.lower()))
    b = set(re.findall(r"\w+", out.lower()))
    return len(a) >= 3 and len(a & b) / len(a) > 0.5


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
        if name != "Indonesian" and _barely_translated(text, out):  # coba model yang lebih pintar
            smart = context.cfg.model_copy(deep=True)
            smart.llm.fast_model = smart.llm.smart_model
            out = run_translation(text, name, smart) or out
    except Exception as e:  # noqa: BLE001 — Ollama mati / model belum ada
        raise ToolError(f"Penerjemah tidak bisa dipakai: {e}") from e
    return out or "Saya tidak bisa menerjemahkan itu"


@tool(
    name="set_language",
    description=(
        "Mengganti bahasa yang didengarkan Jarvis (mis. Jepang, Inggris, Spanyol); "
        "'otomatis' untuk deteksi Indonesia/Inggris, 'Indonesia' untuk kembali ke awal"
    ),
    risk="low",
    category="language",
)
def set_language(language: str) -> str:
    """Bahasa ucapan untuk sisa sesi (tidak menulis config.yaml). Whisper dengan bahasa tetap jauh
    lebih akurat daripada deteksi otomatis lintas banyak bahasa."""
    word = language.strip().lower()
    if word in {"otomatis", "auto", "automatic"}:
        context.cfg.stt.language = "auto"
        return "Oke, bahasa otomatis: Indonesia atau Inggris"
    name = target_language(word)
    code = next((c for c, n in WHISPER_LANGUAGES.items() if n == name), None)
    if code is None:
        raise ToolError(f"Bahasa {language} tidak dikenal")
    context.cfg.stt.language = code
    if code == "id":
        return "Oke, kembali ke bahasa Indonesia"
    return f"Oke, sekarang saya dengarkan bahasa {name} sampai Anda ganti lagi"
