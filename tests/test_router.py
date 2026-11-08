from __future__ import annotations

from types import SimpleNamespace

import pytest

from jarvis.brain.actions import ActionRunner
from jarvis.brain.llm import LLM
from jarvis.brain.router import Router
from jarvis.brain.rules import Intent
from jarvis.config import Config


def test_simple_command_uses_rules(adapter) -> None:
    plan = Router(Config()).plan("volume 30 persen")
    assert plan.tier == "rule"
    assert plan.intents == [Intent("set_volume", {"percent": 30})]
    assert plan.model == ""


def test_question_goes_to_fast_model_with_tools(adapter) -> None:
    plan = Router(Config()).plan("apa ibu kota jepang sih")
    assert plan.tier == "fast" and plan.model == "qwen3.5:4b"
    # obrolan biasa: tanpa tools (skema tool menambah 5–8 detik prefill di CPU)
    assert plan.tools == []


def test_only_relevant_tool_schemas_sent(adapter) -> None:
    plan = Router(Config()).plan("kecilkan suaranya sedikit")
    names = {t["function"]["name"] for t in plan.tools}
    assert names == {"set_volume", "mute", "escalate"}
    plan = Router(Config()).plan("nyalakan aplikasi kalkulator itu")
    assert {"open_app", "close_app"} <= {t["function"]["name"] for t in plan.tools}
    assert "shutdown" not in {t["function"]["name"] for t in plan.tools}


@pytest.mark.parametrize(
    "text",
    [
        "jelaskan cara kerja blockchain",
        "bandingkan python dan rust",
        " ".join(["kata"] * 30),
    ],
)
def test_complex_goes_to_smart_model(adapter, text) -> None:
    plan = Router(Config()).plan(text)
    assert plan.tier == "smart" and plan.model == "qwen3.5:9b"
    assert "escalate" not in {t["function"]["name"] for t in plan.tools}


def test_smart_model_can_be_disabled(adapter) -> None:
    cfg = Config()
    cfg.router.enable_smart_model = False
    plan = Router(cfg).plan("jelaskan cara kerja blockchain")
    assert plan.tier == "fast"
    assert "escalate" not in {t["function"]["name"] for t in plan.tools}


def test_rules_can_be_disabled(adapter) -> None:
    cfg = Config()
    cfg.router.enable_rules = False
    assert Router(cfg).plan("volume 30").tier == "fast"


def test_escalated_plan(adapter) -> None:
    plan = Router(Config()).escalated("matikan laptop")
    assert plan.tier == "smart" and plan.model == "qwen3.5:9b"
    assert "shutdown" in {t["function"]["name"] for t in plan.tools}


# ── konfirmasi ──
def test_shutdown_needs_confirmation_and_is_not_executed(adapter) -> None:
    runner = ActionRunner()
    out = runner.run([Intent("shutdown")])
    assert "Yakin mau mematikan komputer" in out
    assert runner.pending == Intent("shutdown")
    assert ("shutdown",) not in adapter.calls


def test_confirm_yes_executes(adapter) -> None:
    runner = ActionRunner()
    runner.run([Intent("shutdown")])
    assert "dimatikan" in runner.resolve(True)
    assert ("shutdown",) in adapter.calls and runner.pending is None


@pytest.mark.parametrize("answer", [False, None])
def test_confirm_no_or_unclear_cancels(adapter, answer) -> None:
    runner = ActionRunner()
    runner.run([Intent("restart")])
    assert "batal" in runner.resolve(answer)
    assert ("restart",) not in adapter.calls and runner.pending is None


def test_pending_stops_following_intents(adapter) -> None:
    runner = ActionRunner()
    runner.run([Intent("shutdown"), Intent("set_volume", {"percent": 10})])
    assert ("set_volume", 10) not in adapter.calls


def test_error_is_spoken_and_beeps(adapter) -> None:
    beeps: list[int] = []
    runner = ActionRunner(on_error=lambda: beeps.append(1))
    out = runner.run([Intent("open_app", {"name": "Tidak Ada"})])
    assert "tidak ditemukan" in out and beeps == [1]


def test_local_action(adapter) -> None:
    runner = ActionRunner(local={"stop_speaking": lambda _a: ""})
    assert runner.run([Intent("stop_speaking")]) == ""


def test_llm_tool_call_never_bypasses_confirmation(adapter) -> None:
    """Tool call dari LLM (mis. hasil prompt injection) tetap butuh konfirmasi."""
    runner = ActionRunner()
    runner.run([Intent("shutdown", {})])
    assert runner.pending is not None and ("shutdown",) not in adapter.calls


# ── LLM tool calling ──
class FakeToolClient:
    def chat(self, **kw):
        assert kw["tools"]
        call = SimpleNamespace(
            function=SimpleNamespace(name="set_volume", arguments={"percent": 20})
        )
        yield SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))


def test_llm_collects_tool_calls() -> None:
    llm = LLM(Config(), client=FakeToolClient())  # type: ignore[arg-type]
    assert "".join(llm.ask("kecilkan volume", tools=[{"x": 1}])) == ""
    assert llm.tool_calls == [("set_volume", {"percent": 20})]
    llm.replace_last_reply("Volume sekarang 20 persen")
    assert llm.history[-1]["content"] == "Volume sekarang 20 persen"
