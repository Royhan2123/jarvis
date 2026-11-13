"""Router 2 otak: Tier 0 regex → Tier 1 Qwen 4B (+tool calling) → Tier 2 Qwen 9B."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jarvis.brain import rules
from jarvis.brain.rules import Intent
from jarvis.config import Config
from jarvis.tools.plugins import PLUGIN_CATEGORY
from jarvis.tools.registry import registry

ESCALATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "escalate",
        "description": "Serahkan ke model yang lebih pintar untuk pertanyaan rumit atau analisis",
        "parameters": {"type": "object", "properties": {}},
    },
}


# Kata kunci (awalan) → tool yang relevan. Hanya skema tool yang relevan dikirim ke LLM:
# 12 skema sekaligus membuat Qwen 4B di CPU 10–20 detik lebih lambat dan sering salah panggil tool.
TOOL_HINTS: dict[tuple[str, ...], tuple[str, ...]] = {
    (
        "volume",
        "suara",
        "kecil",
        "besar",
        "pelan",
        "keras",
        "naik",
        "turun",
        "mute",
        "bisu",
        "louder",
        "quieter",
        "lower",
        "raise",
    ): (
        "set_volume",
        "mute",
    ),
    ("lagu", "musik", "putar", "play", "pause", "jeda", "next", "skip", "berikut", "sebelum"): (
        "media",
    ),
    ("buka", "tutup", "aplikasi", "jalankan", "quit", "app", "open", "close", "launch"): (
        "open_app",
        "close_app",
    ),
    ("web", "situs", "cari", "google", "browser", "link", "url", ".com", "search"): (
        "open_url",
        "web_search",
    ),
    ("youtube", "yutub", "video"): ("play_youtube", "open_url"),
    ("layar", "screen", "rangkum", "error", "summarize"): ("read_screen",),
    ("ketik", "tulis"): ("type_text",),
    ("catat", "catatan", "ingat", "pengingat", "nama", "note", "remind", "reminder", "remember"): (
        "add_note",
        "list_notes",
        "set_reminder",
        "remember_fact",
    ),
    ("cuaca", "hujan", "suhu", "panas", "dingin", "weather"): ("get_weather",),
    ("jadwal", "kalender", "agenda", "acara", "rapat", "meeting"): (
        "calendar_events",
        "add_calendar_event",
    ),
    ("email", "gmail", "surel", "surat"): ("unread_emails",),
    ("lampu", "kipas", "saklar", "perangkat", "nyalakan", "hidupkan", "matikan"): (
        "device_control",
        "device_state",
        "list_devices",
    ),
    ("whatsapp", "wa", "pesan"): ("whatsapp_draft",),
    ("folder", "direktori", "proyek", "project"): ("list_files",),
    ("dokumen", "berkas", "arsip", "kontrak", "pdf"): ("search_docs", "index_docs"),
    (
        "jam",
        "tanggal",
        "hari",
        "baterai",
        "batre",
        "ram",
        "cpu",
        "memori",
        "time",
        "date",
        "battery",
        "memory",
    ): (
        "get_time",
        "system_info",
    ),
    ("terjemah", "translate", "artikan", "bahasa", "inggris", "english"): ("translate",),
    ("kunci", "layar", "matikan", "restart", "shutdown", "komputer", "laptop"): (
        "lock_screen",
        "shutdown",
        "restart",
    ),
}


@dataclass
class Plan:
    intents: list[Intent] = field(default_factory=list)  # tidak kosong → Tier 0 (tanpa LLM)
    model: str = ""
    tier: str = "rule"  # rule | fast | smart
    tools: list[dict] = field(default_factory=list)
    num_ctx: int | None = None  # None = pakai llm.num_ctx


class Router:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def is_complex(self, text: str) -> bool:
        r = self.cfg.router
        words = re.findall(r"\w+", text.lower())
        return len(words) > r.complex_min_words or any(k in words for k in r.complex_keywords)

    def relevant_tools(self, text: str) -> list[str]:
        words = re.findall(r"[\w.]+", text.lower())
        names: list[str] = []
        from jarvis.tools.plugins import PLUGIN_HINTS

        for keys, tools in (*TOOL_HINTS.items(), *PLUGIN_HINTS.items()):
            if any(w.startswith(k) or (k == ".com" and k in w) for w in words for k in keys):
                names.extend(t for t in tools if t not in names)
        return names

    def tool_schemas(self, text: str, escalate: bool) -> list[dict]:
        wanted = set(self.relevant_tools(text))
        if not wanted:  # obrolan biasa: tanpa tools sama sekali (tools menambah 5–8 detik di CPU)
            return []
        schemas = [
            s
            for s in registry.schemas([*self.cfg.tools.enabled, PLUGIN_CATEGORY])
            if s["function"]["name"] in wanted
        ]
        return [*schemas, ESCALATE_SCHEMA] if escalate else schemas

    def plan(self, text: str) -> Plan:
        r, llm = self.cfg.router, self.cfg.llm
        sh = self.cfg.smarthome
        if sh.enabled and (intents := rules.match_devices(text, list(sh.devices))):
            return Plan(intents=intents, tier="rule")
        if r.enable_rules and (intents := rules.match(text)):
            return Plan(intents=intents, tier="rule")
        if r.enable_smart_model and self.is_complex(text):
            return Plan(
                model=llm.active_smart_model, tier="smart", tools=self.tool_schemas(text, False)
            )
        return Plan(
            model=llm.active_fast_model,
            tier="fast",
            tools=self.tool_schemas(text, escalate=r.enable_smart_model),
        )

    def escalated(self, text: str) -> Plan:
        """Rencana Tier 2 setelah 4B memanggil tool `escalate`."""
        return Plan(
            model=self.cfg.llm.active_smart_model,
            tier="smart",
            tools=self.tool_schemas(text, escalate=False),
        )
