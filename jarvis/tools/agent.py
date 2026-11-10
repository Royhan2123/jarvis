"""Tool `run_agent`: serahkan tugas multi-langkah ke agen kerja (langkah berisiko dikonfirmasi)."""

from __future__ import annotations

from collections.abc import Callable

from jarvis import island
from jarvis.tools.registry import ToolError, context, tool

# Diisi aplikasi (suara/UI): konfirmasi(kalimat) -> bool dan ucapan(teks). Tanpa itu agen menolak.
confirm_hook: Callable[[str], bool] | None = None
say_hook: Callable[[str], None] | None = None


@tool(
    name="run_agent",
    description="Mengerjakan tugas komputer multi-langkah di folder kerja (perbaiki bug, jalankan "
    "tes, ubah file) dengan konfirmasi untuk tiap langkah berisiko",
    risk="medium",
    category="agent",
)
def run_agent(task: str) -> str:
    from jarvis.agent import Agent, AgentError

    cfg = context.cfg
    if not cfg.agent.enabled:
        raise ToolError("Agen kerja belum diaktifkan. Setel agent.enabled: true di config.yaml")
    if confirm_hook is None:
        raise ToolError("Agen butuh cara konfirmasi (suara atau UI) yang belum tersambung")
    try:
        result = Agent(cfg, confirm_hook, say_hook).run(task)
        island.notify_async(cfg, f"Jarvis: {result}")
        return result
    except AgentError as e:
        raise ToolError(str(e)) from e
    except Exception as e:  # noqa: BLE001 — Ollama mati dsb. jangan menjatuhkan Jarvis
        raise ToolError(f"Agen gagal: {e}") from e
