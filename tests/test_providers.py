from __future__ import annotations

import json
import stat

import httpx
import pytest

from jarvis import ai_settings
from jarvis.agent import Agent
from jarvis.brain import providers
from jarvis.brain.llm import LLM
from jarvis.config import Config


def cloud_cfg(provider: str = "openai") -> Config:
    c = Config()
    c.llm.provider = provider  # type: ignore[assignment]
    c.llm.allow_cloud = True
    c.llm.cloud_fast_model = "model-x"
    return c


def sse(*events: dict, done: bool = True) -> bytes:
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
    return (body + ("data: [DONE]\n\n" if done else "")).encode()


def mock(client, handler) -> None:
    client._http = httpx.Client(transport=httpx.MockTransport(handler))


def test_default_is_ollama_and_blocks_cloud_without_permission() -> None:
    c = Config()
    assert c.llm.provider == "ollama" and not c.llm.allow_cloud
    assert c.llm.active_fast_model == "qwen3.5:4b"
    c.llm.provider = "openai"  # type: ignore[assignment]
    with pytest.raises(providers.ProviderError, match="allow_cloud"):
        providers.client_for(c)


def test_openai_streams_text_and_sends_key_only_in_header() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"], seen["body"] = req.headers["authorization"], json.loads(req.content)
        seen["url"] = str(req.url)
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "Halo"}}]},
                {"choices": [{"delta": {"content": " Bos"}}]},
            ),
        )

    c = cloud_cfg()
    cl = providers.OpenAIClient("https://api.openai.com/v1", "sk-rahasia", c)
    mock(cl, handler)
    llm = LLM(c, client=cl)
    assert "".join(llm.ask("hai")) == "Halo Bos"
    assert seen["auth"] == "Bearer sk-rahasia" and seen["url"].endswith("/chat/completions")
    assert "sk-rahasia" not in json.dumps(seen["body"])
    assert seen["body"]["model"] == "model-x"  # model online dipakai, bukan qwen
    assert seen["body"]["max_completion_tokens"] >= 256


def test_openai_stream_assembles_tool_call_fragments() -> None:
    frames = [
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "set_vol", "arguments": '{"perc'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": 'ent": 40}'}}]}}]},
    ]  # fmt: skip
    c = cloud_cfg()
    cl = providers.OpenAIClient("https://x/v1", "k", c)
    mock(cl, lambda r: httpx.Response(200, content=sse(*frames)))
    llm = LLM(c, client=cl)
    "".join(llm.ask("volume 40"))
    assert llm.tool_calls == [("set_vol", {"percent": 40})]


def test_http_errors_become_friendly_messages_without_key() -> None:
    c = cloud_cfg()
    cl = providers.OpenAIClient("https://x/v1", "sk-rahasia", c)
    mock(cl, lambda r: httpx.Response(401, json={"error": {"message": "bad key sk-rahasia"}}))
    with pytest.raises(providers.ProviderError) as e:
        cl.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert "ditolak" in str(e.value) and "sk-rahasia" not in str(e.value)


def test_anthropic_wire_format_and_tool_roundtrip() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["headers"], seen["body"] = req.headers, json.loads(req.content)
        return httpx.Response(
            200,
            json={"content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "id": "tu1", "name": "list_dir", "input": {"path": "."}},
            ]},
        )  # fmt: skip

    c = cloud_cfg("anthropic")
    cl = providers.AnthropicClient("https://api.anthropic.com/v1", "sk-ant", c)
    mock(cl, handler)
    tools = [{"type": "function", "function": {"name": "list_dir", "description": "d",
                                                 "parameters": {"type": "object"}}}]  # fmt: skip
    r = cl.chat(
        model="claude-x",
        messages=[{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}],
        tools=tools,
    )
    assert seen["headers"]["x-api-key"] == "sk-ant"
    assert seen["body"]["system"] == "S" and seen["body"]["tools"][0]["input_schema"]
    call = r.message.tool_calls[0]
    assert (call.function.name, call.function.arguments, call.id) == (
        "list_dir",
        {"path": "."},
        "tu1",
    )
    # hasil tool dipasangkan ke id pemanggilan sebelumnya
    system, wire = providers.AnthropicClient._wire(
        [{"role": "user", "content": "hi"}, r.message, {"role": "tool", "content": "a.py"}]
    )
    assert wire[-1] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "a.py"}],
    }


def test_agent_runs_on_cloud_client_with_tool_message_ids() -> None:
    bodies = []

    def handler(req: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(req.content))
        if len(bodies) == 1:
            fn = {"name": "list_dir", "arguments": "{}"}
            msg = {"tool_calls": [{"id": "c9", "type": "function", "function": fn}]}
        else:
            msg = {"content": "Selesai."}
        return httpx.Response(200, json={"choices": [{"message": msg}]})

    c = cloud_cfg()
    c.workspace.folders = ["."]
    cl = providers.OpenAIClient("https://x/v1", "k", c)
    mock(cl, handler)
    assert Agent(c, lambda _w: False, client=cl).run("lihat") == "Selesai."
    tool_msg = [m for m in bodies[1]["messages"] if m["role"] == "tool"][0]
    assert tool_msg["tool_call_id"] == "c9"


def test_update_saves_key_0600_never_returns_it_and_switches_live(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(providers, "unload_local_models", lambda cfg: 2)
    c = Config()
    v = ai_settings.update(c, "openai", api_key="sk-rahasia", fast_model="gpt-4o-mini")
    assert c.llm.provider == "openai" and c.llm.allow_cloud
    assert c.llm.active_fast_model == "gpt-4o-mini" and v["has_key"]
    assert "sk-rahasia" not in json.dumps(v)
    assert stat.S_IMODE(ai_settings.path().stat().st_mode) == 0o600
    assert ai_settings.get_key("openai") == "sk-rahasia"
    ai_settings.update(c, "ollama")  # kembali lokal, tanpa izin online
    assert c.llm.provider == "ollama" and not c.llm.allow_cloud
    assert c.llm.active_fast_model == "qwen3.5:4b"
    fresh = Config()  # pemuatan ulang: setelan tersimpan menimpa config.yaml
    ai_settings.update(fresh, "openai", fast_model="gpt-4o-mini")  # kunci lama masih tersimpan
    again = Config()
    ai_settings.apply(again)
    assert again.llm.provider == "openai" and again.llm.cloud_fast_model == "gpt-4o-mini"


def test_view_reports_voice_without_secrets() -> None:
    c = Config()
    c.tts.engine = "fish"
    c.tts.gender = "female"
    v = ai_settings.view(c)
    assert v["voice"] == {"engine": "fish", "gender": "female"}
    assert "voice_id" not in json.dumps(v) and "api_key" not in json.dumps(v)


def test_update_validates_input() -> None:
    c = Config()
    with pytest.raises(ValueError, match="tidak dikenal"):
        ai_settings.update(c, "skynet")
    with pytest.raises(ValueError, match="Kunci"):
        ai_settings.update(c, "openai", fast_model="m")
    with pytest.raises(ValueError, match="model"):
        ai_settings.update(c, "openai", api_key="k")
    with pytest.raises(ValueError, match="api_base"):
        ai_settings.update(c, "custom", api_key="k", fast_model="m")
    assert c.llm.provider == "ollama"  # gagal = tidak ada yang berubah


def test_env_key_and_cloud_without_permission_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("JARVIS_API_KEY_GROQ", "gsk-env")
    assert ai_settings.get_key("groq") == "gsk-env"
    ai_settings.path().write_text(json.dumps({"provider": "groq", "allow_cloud": False}))
    c = Config()
    ai_settings.apply(c)
    assert c.llm.provider == "ollama"  # online tanpa izin eksplisit tidak pernah aktif


def test_api_endpoints_get_put_never_leak_key(tmp_path, monkeypatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from jarvis.ui.api import ApiBackend, build_router

    monkeypatch.setattr(providers, "unload_local_models", lambda cfg: 0)
    c = Config()
    app = FastAPI()
    app.include_router(build_router(ApiBackend(c), "tok"))
    cl = TestClient(app)
    h = {"Authorization": "Bearer tok"}
    assert cl.get("/v1/ai").status_code == 401
    assert cl.get("/v1/ai", headers=h).json()["provider"] == "ollama"
    r = cl.put(
        "/v1/ai", headers=h, json={"provider": "groq", "api_key": "gsk-1", "fast_model": "m"}
    )
    assert r.status_code == 200 and "gsk-1" not in r.text and r.json()["provider"] == "groq"
    bad = cl.put("/v1/ai", headers=h, json={"provider": "openai", "fast_model": "m"})
    assert bad.status_code == 422
