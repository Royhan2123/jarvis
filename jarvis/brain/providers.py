"""Penyedia model bahasa: Ollama lokal (bawaan) atau API online (kunci milik pengguna).

Semua klien meniru bentuk `ollama.Client.chat`: `chat(model, messages, stream, options, tools, ...)`
mengembalikan objek dengan `.message.content` dan `.message.tool_calls[i].function.{name,arguments}`
(atau iterator potongan bila `stream=True`). Dengan begitu LLM/agen/penerjemah tidak peduli
modelnya di mana. Kunci API TIDAK pernah ditulis ke log, config.yaml, atau respons API.

Penyedia online hanya jalan bila pengguna memilihnya (`llm.allow_cloud`); selain itu tidak ada
satu byte pun yang keluar dari komputer (kecuali ke Ollama di localhost).
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from jarvis.config import Config

# provider -> (jenis protokol, alamat dasar). "openai" = protokol OpenAI Chat Completions, yang juga
# dipakai Gemini, Groq, OpenRouter, DeepSeek, Mistral, LM Studio, vLLM, dll.
PRESETS: dict[str, tuple[str, str]] = {
    "ollama": ("ollama", ""),
    "openai": ("openai", "https://api.openai.com/v1"),
    "anthropic": ("anthropic", "https://api.anthropic.com/v1"),
    "gemini": ("openai", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "groq": ("openai", "https://api.groq.com/openai/v1"),
    "openrouter": ("openai", "https://openrouter.ai/api/v1"),
    "deepseek": ("openai", "https://api.deepseek.com/v1"),
    "mistral": ("openai", "https://api.mistral.ai/v1"),
    "custom": ("openai", ""),  # alamat sendiri (api_base), protokol OpenAI
}
ANTHROPIC_VERSION = "2023-06-01"
MIN_CLOUD_TOKENS = 256  # num_predict lokal (100) terlalu kecil untuk model online


class ProviderError(RuntimeError):
    """Pesan aman untuk ditampilkan/dibacakan (tanpa kunci API)."""


# ── bentuk jawaban (sama dengan ollama) ──
@dataclass
class _Fn:
    name: str
    arguments: dict[str, Any]


@dataclass
class _Call:
    function: _Fn
    id: str = field(default_factory=lambda: "call_" + uuid.uuid4().hex[:12])


@dataclass
class _Msg:
    content: str = ""
    tool_calls: list[_Call] = field(default_factory=list)
    role: str = "assistant"


@dataclass
class _Resp:
    message: _Msg


def _get(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return val if isinstance(val, dict) else {}


def _normalize(messages: list[Any]) -> list[dict[str, Any]]:
    """Pesan (dict/objek) -> dict seragam; id pemanggilan tool dipasangkan ke hasilnya."""
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    for m in messages:
        role, content = _get(m, "role"), _get(m, "content") or ""
        calls = _get(m, "tool_calls") or []
        if role == "assistant" and calls:
            norm = []
            for c in calls:
                fn = _get(c, "function")
                cid = _get(c, "id") or "call_" + uuid.uuid4().hex[:12]
                norm.append(
                    {"id": cid, "name": _get(fn, "name"), "args": _args(_get(fn, "arguments"))}
                )
            pending = [c["id"] for c in norm]
            out.append({"role": "assistant", "content": content, "calls": norm})
        elif role == "tool":
            out.append(
                {"role": "tool", "content": content, "id": pending.pop(0) if pending else "call_0"}
            )
        else:
            out.append({"role": role, "content": content})
    return out


def _explain(resp: httpx.Response) -> ProviderError:
    code = resp.status_code
    if code in (401, 403):
        return ProviderError("Kunci API ditolak penyedia. Periksa kuncinya di setelan AI Jarvis")
    if code == 404:
        return ProviderError("Model atau alamat penyedia tidak ditemukan. Periksa nama modelnya")
    if code == 429:
        return ProviderError("Penyedia membatasi permintaan (kuota habis atau terlalu sering)")
    try:
        detail = resp.json()
        detail = detail.get("error", detail)
        detail = detail.get("message", detail) if isinstance(detail, dict) else detail
    except ValueError:
        detail = resp.text
    return ProviderError(f"Penyedia menolak permintaan ({code}): {str(detail)[:200]}")


class _HttpClient:
    """Dasar klien online: satu httpx.Client, galat jaringan jadi ProviderError."""

    def __init__(self, base: str, key: str, cfg: Config) -> None:
        if not cfg.llm.allow_cloud:
            raise ProviderError("Penyedia online belum diizinkan (llm.allow_cloud)")
        if not key:
            raise ProviderError("Kunci API belum diisi di setelan AI Jarvis")
        self.base, self._key = base.rstrip("/"), key
        self.cfg = cfg
        self._http = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._http.post(self.base + path, headers=self._headers(), json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"Tidak bisa menghubungi penyedia AI: {type(e).__name__}") from e
        if resp.status_code >= 400:
            raise _explain(resp)
        return resp.json()

    def _sse(self, path: str, body: dict[str, Any]) -> Iterator[dict[str, Any]]:
        try:
            with self._http.stream(
                "POST", self.base + path, headers=self._headers(), json=body
            ) as resp:
                if resp.status_code >= 400:
                    resp.read()
                    raise _explain(resp)
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except ValueError:
                        continue
        except httpx.HTTPError as e:
            raise ProviderError(f"Koneksi ke penyedia AI terputus: {type(e).__name__}") from e

    def _limits(self, options: dict[str, Any] | None) -> tuple[float, int]:
        o = options or {}
        return float(o.get("temperature", 0.3)), max(
            int(o.get("num_predict") or 0), MIN_CLOUD_TOKENS
        )

    def close(self) -> None:
        self._http.close()


class OpenAIClient(_HttpClient):
    """Protokol OpenAI Chat Completions (OpenAI, Gemini, Groq, OpenRouter, DeepSeek, dll.)."""

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    @staticmethod
    def _wire(messages: list[Any]) -> list[dict[str, Any]]:
        wire: list[dict[str, Any]] = []
        for m in _normalize(messages):
            if m["role"] == "assistant" and "calls" in m:
                wire.append(
                    {
                        "role": "assistant",
                        "content": m["content"] or None,
                        "tool_calls": [
                            {
                                "id": c["id"],
                                "type": "function",
                                "function": {"name": c["name"], "arguments": json.dumps(c["args"])},
                            }
                            for c in m["calls"]
                        ],
                    }
                )
            elif m["role"] == "tool":
                wire.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
            else:
                wire.append({"role": m["role"], "content": m["content"]})
        return wire

    def _body(self, model, messages, options, tools, stream) -> dict[str, Any]:  # noqa: ANN001
        temp, max_tokens = self._limits(options)
        body: dict[str, Any] = {"model": model, "messages": self._wire(messages), "stream": stream}
        if self.cfg.llm.provider == "openai":  # model baru OpenAI menolak max_tokens/temperature
            body["max_completion_tokens"] = max_tokens
            if not re.match(r"(o\d|gpt-5)", model):
                body["temperature"] = temp
        else:
            body["max_tokens"] = max_tokens
            body["temperature"] = temp
        if tools:
            body["tools"] = tools
        return body

    def chat(self, model, messages, stream=False, options=None, tools=None, **_ignored):  # noqa: ANN001, ANN201
        body = self._body(model, messages, options, tools, stream)
        return self._stream(body) if stream else self._once(body)

    def _once(self, body: dict[str, Any]) -> _Resp:
        data = self._post_json("/chat/completions", body)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        calls = [
            _Call(
                _Fn(c["function"]["name"], _args(c["function"].get("arguments"))), c.get("id", "")
            )
            for c in msg.get("tool_calls") or []
        ]
        return _Resp(_Msg(msg.get("content") or "", calls))

    def _stream(self, body: dict[str, Any]) -> Iterator[_Resp]:
        partial: dict[int, dict[str, str]] = {}
        for ev in self._sse("/chat/completions", body):
            delta = ((ev.get("choices") or [{}])[0]).get("delta") or {}
            for tc in delta.get("tool_calls") or []:
                slot = partial.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                slot["id"] = tc.get("id") or slot["id"]
                fn = tc.get("function") or {}
                slot["name"] += fn.get("name") or ""
                slot["args"] += fn.get("arguments") or ""
            if delta.get("content"):
                yield _Resp(_Msg(delta["content"]))
        if partial:
            calls = [
                _Call(_Fn(s["name"], _args(s["args"])), s["id"] or "call_" + uuid.uuid4().hex[:12])
                for _, s in sorted(partial.items())
            ]
            yield _Resp(_Msg("", calls))


class AnthropicClient(_HttpClient):
    """Protokol Messages milik Anthropic (Claude)."""

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    @staticmethod
    def _wire(messages: list[Any]) -> tuple[str, list[dict[str, Any]]]:
        system, wire = "", []
        for m in _normalize(messages):
            if m["role"] == "system":
                system += m["content"] + "\n"
            elif m["role"] == "assistant" and "calls" in m:
                blocks: list[dict[str, Any]] = (
                    [{"type": "text", "text": m["content"]}] if m["content"] else []
                )
                blocks += [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]}
                    for c in m["calls"]
                ]
                wire.append({"role": "assistant", "content": blocks})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"]}
                if wire and wire[-1]["role"] == "user" and isinstance(wire[-1]["content"], list):
                    wire[-1]["content"].append(block)
                else:
                    wire.append({"role": "user", "content": [block]})
            else:
                wire.append({"role": m["role"], "content": m["content"] or "."})
        return system.strip(), wire

    @staticmethod
    def _tools(tools: list[dict] | None) -> list[dict[str, Any]]:
        return [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters") or {"type": "object"},
            }
            for t in tools or []
        ]

    def chat(self, model, messages, stream=False, options=None, tools=None, **_ignored):  # noqa: ANN001, ANN201
        temp, max_tokens = self._limits(options)
        system, wire = self._wire(messages)
        body: dict[str, Any] = {
            "model": model, "messages": wire, "max_tokens": max_tokens,
            "temperature": temp, "stream": stream,
        }  # fmt: skip
        if system:
            body["system"] = system
        if tools:
            body["tools"] = self._tools(tools)
        return self._stream(body) if stream else self._once(body)

    def _once(self, body: dict[str, Any]) -> _Resp:
        data = self._post_json("/messages", body)
        text, calls = "", []
        for b in data.get("content") or []:
            if b.get("type") == "text":
                text += b.get("text", "")
            elif b.get("type") == "tool_use":
                calls.append(_Call(_Fn(b["name"], b.get("input") or {}), b["id"]))
        return _Resp(_Msg(text, calls))

    def _stream(self, body: dict[str, Any]) -> Iterator[_Resp]:
        blocks: dict[int, dict[str, str]] = {}
        for ev in self._sse("/messages", body):
            kind = ev.get("type")
            if kind == "content_block_start":
                cb = ev.get("content_block") or {}
                if cb.get("type") == "tool_use":
                    blocks[ev["index"]] = {"id": cb["id"], "name": cb["name"], "args": ""}
            elif kind == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta":
                    yield _Resp(_Msg(d.get("text", "")))
                elif d.get("type") == "input_json_delta" and ev["index"] in blocks:
                    blocks[ev["index"]]["args"] += d.get("partial_json", "")
            elif kind == "error":
                raise ProviderError(str((ev.get("error") or {}).get("message", "galat penyedia")))
        if blocks:
            yield _Resp(
                _Msg(
                    "", [_Call(_Fn(b["name"], _args(b["args"])), b["id"]) for b in blocks.values()]
                )
            )


# ── pabrik klien ──
_lock = threading.Lock()
_cache: dict[tuple, Any] = {}


def is_cloud(cfg: Config) -> bool:
    return cfg.llm.provider != "ollama"


def api_base(cfg: Config) -> str:
    return (cfg.llm.api_base or PRESETS.get(cfg.llm.provider, ("", ""))[1]).strip()


def client_for(cfg: Config) -> Any:
    """Klien sesuai `cfg.llm.provider`; dipakai ulang selama setelannya sama (dinamis: ganti
    penyedia/kunci di tengah jalan langsung berlaku di pemanggilan berikutnya)."""
    from jarvis import ai_settings  # impor malas: ai_settings memakai modul ini

    provider = cfg.llm.provider
    if provider not in PRESETS:
        raise ProviderError(f"Penyedia '{provider}' tidak dikenal")
    if provider == "ollama":
        import ollama

        key: tuple = ("ollama", cfg.llm.host)
        with _lock:
            if key not in _cache:
                _cache[key] = ollama.Client(host=cfg.llm.host)
            return _cache[key]
    protocol, _ = PRESETS[provider]
    base, secret = api_base(cfg), ai_settings.get_key(provider)
    if not base:
        raise ProviderError("Alamat API (api_base) belum diisi untuk penyedia custom")
    key = (provider, base, hash(secret), cfg.llm.allow_cloud)
    with _lock:
        if key not in _cache:
            for stale in [k for k in _cache if k[0] == provider]:
                _cache.pop(stale).close()
            cls = AnthropicClient if protocol == "anthropic" else OpenAIClient
            _cache[key] = cls(base, secret, cfg)
        return _cache[key]


def local_client(cfg: Config) -> Any:
    """Klien Ollama lokal, apa pun penyedia aktifnya (vision & embedding RAG tetap lokal)."""
    import ollama

    key = ("ollama", cfg.llm.host)
    with _lock:
        if key not in _cache:
            _cache[key] = ollama.Client(host=cfg.llm.host)
        return _cache[key]


def unload_local_models(cfg: Config) -> int:
    """Bongkar semua model Ollama dari RAM (dipakai saat pindah ke penyedia online). Mengembalikan
    jumlah model yang dibongkar; Ollama mati = 0 tanpa galat."""
    n = 0
    try:
        client = local_client(cfg)
        for m in client.ps().models:
            client.generate(model=m.model, prompt="", keep_alive=0)
            n += 1
    except Exception:  # noqa: BLE001 — Ollama mati/tidak ada: tidak ada yang perlu dibongkar
        return n
    return n
