"""Tool `run_agent`: serahkan tugas multi-langkah ke agen kerja (langkah berisiko dikonfirmasi)."""

from __future__ import annotations

from collections.abc import Callable

from jarvis import island
from jarvis.agent import policy
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


def _change(action: str, ask: bool) -> str:
    try:
        policy.set_asking(context.cfg, action, ask)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return policy.summary(list(context.cfg.agent.confirm_actions))


@tool(
    name="agent_auto_approve",
    description="Agen berhenti bertanya izin untuk satu jenis aksi (ubah/buat file, perintah)",
    # Melonggarkan pengaman: wajib konfirmasi suara. Hanya dari rule ucapan; tak ditawarkan ke LLM.
    risk="high",
    category="agent",
)
def agent_auto_approve(action: str) -> str:
    return "Baik, sampai Jarvis dimatikan. " + _change(action, ask=False)


@tool(
    name="agent_ask_always",
    description="Agen kembali bertanya izin untuk satu jenis aksi (ubah/buat file, perintah)",
    risk="low",  # mengetatkan pengaman: aman tanpa konfirmasi
    category="agent",
)
def agent_ask_always(action: str) -> str:
    return "Baik. " + _change(action, ask=True)
