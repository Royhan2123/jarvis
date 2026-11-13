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
        keep_alive=cfg.llm.keep_alive_for(cfg.llm.fast_model),
        think=False,
    )
    return (resp.message.content or "").strip().strip("\"'“”")


def _barely_translated(source: str, out: str) -> bool:
    """True bila hasil masih memuat kata sumber (model kecil kadang menerjemahkan setengah untuk
    bahasa langka: "Selamat pagi, bugün hava çok güzel"): ≥2 kata sumber (≥4 huruf) yang sama,
    atau lebih dari separuh kata sumber."""
    a = {w for w in re.findall(r"\w+", source.lower()) if not w.isdigit()}
    b = set(re.findall(r"\w+", out.lower()))
    shared = a & b
    long_shared = {w for w in shared if len(w) >= 4}
    return len(a) >= 3 and (len(long_shared) >= 2 or len(shared) / len(a) > 0.5)


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


_ORIGINAL: dict[str, object] = {}


@tool(
    name="set_language",
    description=(
        "Mengganti bahasa yang didengarkan Jarvis (mis. Jepang, Spanyol, Korea) selain Indonesia "
        "dan Inggris; 'Indonesia' atau 'otomatis' untuk kembali ke awal"
    ),
    risk="low",
    category="language",
)
def set_language(language: str) -> str:
    """Tambahkan satu bahasa ke deteksi untuk sisa sesi (tidak menulis config.yaml).

    Jarvis lalu memilih per ucapan di antara Indonesia, Inggris, dan bahasa itu: pilihan tiga arah
    jauh lebih andal daripada deteksi ±90 bahasa, dan ucapan Indonesia tetap dikenali (jadi
    "ganti bahasa ke Indonesia" selalu bisa diucapkan)."""
    stt = context.cfg.stt
    _ORIGINAL.setdefault("language", stt.language)
    _ORIGINAL.setdefault("detect_languages", list(stt.detect_languages))
    word = language.strip().lower()
    name = target_language(word)
    reset = word in {"otomatis", "auto", "automatic"} or name == "Indonesian"
    if reset:
        stt.language = _ORIGINAL["language"]
        stt.detect_languages = list(_ORIGINAL["detect_languages"])  # type: ignore[arg-type]
        return "Oke, kembali ke bahasa Indonesia dan Inggris"
    code = next((c for c, n in WHISPER_LANGUAGES.items() if n == name), None)
    if code is None:
        raise ToolError(f"Bahasa {language} tidak dikenal")
    stt.language = "auto"
    stt.detect_languages = list(dict.fromkeys(["id", "en", code]))
    return f"Oke, sekarang saya juga mendengarkan bahasa {name}; bahasa Indonesia tetap bisa"
