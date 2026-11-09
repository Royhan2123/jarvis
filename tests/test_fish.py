from __future__ import annotations

import http.server
import json
import struct
import threading

import numpy as np
import pytest

from jarvis.config import Config
from jarvis.tts import build_tts, fish

SEEN: list[dict] = []
RESPONSE: dict = {"code": 200}


def make_wav(samples: np.ndarray, rate: int = 24000) -> bytes:
    pcm = samples.astype("<i2").tobytes()
    # header streaming: panjang RIFF/data sengaja palsu (0xFFFFFFFF)
    head = (
        b"RIFF"
        + struct.pack("<I", 0xFFFFFFFF)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    )
    return head + b"data" + struct.pack("<I", 0xFFFFFFFF) + pcm


class FakeFish(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(
            {
                "body": body,
                "auth": self.headers.get("Authorization"),
                "model": self.headers.get("model"),
            }
        )
        self.send_response(RESPONSE["code"])
        self.end_headers()
        self.wfile.write(RESPONSE.get("data", b"{}"))

    def log_message(self, *a) -> None:  # noqa: ANN002
        pass


@pytest.fixture
def server(monkeypatch):
    SEEN.clear()
    RESPONSE.clear()
    RESPONSE.update(code=200, data=make_wav(np.arange(100, dtype=np.int16)))
    srv = http.server.HTTPServer(("127.0.0.1", 0), FakeFish)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(fish, "API_URL", f"http://127.0.0.1:{srv.server_port}/v1/tts")
    yield
    srv.shutdown()


@pytest.fixture
def cfg(tmp_path):
    key = tmp_path / "key"
    key.write_text("kunci-rahasia\n")
    c = Config()
    c.general.offline_only = False
    c.tts.engine = "fish"
    c.tts.fish.voice_id = "abc123"
    c.tts.fish.api_key_file = str(key)
    return c


class FakeLocal:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        pass


def test_synthesize_sends_expected_request_and_parses_streamed_wav(
    server, cfg, monkeypatch
) -> None:
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    audio, rate = fish.FishTTS(cfg).synthesize("Halo Bos")
    assert rate == 24000 and audio.tolist() == list(range(100))
    s = SEEN[0]
    assert s["auth"] == "Bearer kunci-rahasia" and s["model"] == "s2.1-pro-free"
    assert s["body"]["text"] == "Halo Bos" and s["body"]["reference_id"] == "abc123"
    assert s["body"]["format"] == "wav"


def test_http_error_falls_back_to_local_voice(server, cfg, monkeypatch) -> None:
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    RESPONSE.update(code=402, data=b'{"message":"no credit"}')
    local = FakeLocal()
    fish.FishTTS(cfg, fallback=local).speak("Halo")
    assert local.spoken == ["Halo"]


def test_requires_online_voice_and_key(cfg, monkeypatch) -> None:
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    cfg.general.offline_only = True
    with pytest.raises(fish.FishError, match="internet"):
        fish.FishTTS(cfg)
    cfg.general.offline_only = False
    cfg.tts.fish.voice_id = None
    with pytest.raises(fish.FishError, match="voice_id"):
        fish.FishTTS(cfg)
    cfg.tts.fish.voice_id = "x"
    cfg.tts.fish.api_key_file = None
    with pytest.raises(fish.FishError, match="API key"):
        fish.FishTTS(cfg)


def test_build_tts_falls_back_when_offline_only(monkeypatch) -> None:
    c = Config()
    c.tts.engine = "fish"  # offline_only default true → tolak, jangan kirim apa pun ke internet
    sentinel = FakeLocal()
    monkeypatch.setattr("jarvis.tts._local_tts", lambda cfg: sentinel)
    assert build_tts(c) is sentinel


def test_parse_wav_rejects_garbage() -> None:
    with pytest.raises(fish.FishError):
        fish.parse_wav(b'{"status":"error"}')
