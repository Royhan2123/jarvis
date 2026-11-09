"""Google OAuth (loopback + PKCE) dan REST Calendar/Gmail, hanya dengan pustaka standar.

Kenapa tanpa google-auth: dependensinya (`cryptography`) tidak punya paket siap pakai untuk Mac
Intel. Kamu membuat sendiri client_secret.json (Google Cloud Console → OAuth client "Desktop") dan
login lewat browser; Jarvis hanya menyimpan token di folder data (izin 0600). Scope minimal:
calendar.events dan gmail.readonly.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from platformdirs import user_data_dir

from jarvis.config import Config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
]


class GoogleError(RuntimeError):
    """Pesan aman untuk dibacakan."""


def token_path(cfg: Config) -> Path:
    o = cfg.online
    return (
        Path(o.google_token).expanduser()
        if o.google_token
        else Path(user_data_dir("jarvis")) / "google_token.json"
    )


def _client(cfg: Config) -> dict:
    f = cfg.online.google_credentials
    if not f or not Path(f).expanduser().is_file():
        raise GoogleError(
            "Belum ada client_secret.json. Isi online.google_credentials di config.yaml"
        )
    data = json.loads(Path(f).expanduser().read_text(encoding="utf-8"))
    c = data.get("installed") or data.get("web")
    if not c or "client_id" not in c:
        raise GoogleError("File client_secret.json tidak valid (pilih jenis 'Desktop app')")
    return c


def _post(url: str, form: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — URL tetap https Google
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise GoogleError(f"Google menolak permintaan ({e.code})") from e
    except OSError as e:
        raise GoogleError("Tidak bisa terhubung ke Google") from e


def _save_token(cfg: Config, tok: dict) -> None:
    p = token_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with contextlib.suppress(OSError):  # file lama bisa berizin longgar; Windows abaikan chmod
        os.chmod(p, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(tok, f)


def login(cfg: Config, open_browser: bool = True) -> str:
    """Alur login sekali jalan: buka browser, kamu setujui, token disimpan. Dijalankan oleh kamu."""
    c = _client(cfg)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    state = secrets.token_urlsafe(16)
    got: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Login selesai. Kamu boleh menutup tab ini.")

        def log_message(self, *args) -> None:  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
            "scope": " ".join(SCOPES), "state": state, "access_type": "offline",
            "prompt": "consent", "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
        }
    )  # fmt: skip
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    if open_browser:
        webbrowser.open(url)
    print(f"Jika browser tidak terbuka, buka alamat ini:\n{url}")
    t.join(timeout=300)
    server.server_close()
    if got.get("state") != state or "code" not in got:
        raise GoogleError("Login dibatalkan atau waktunya habis")
    tok = _post(
        TOKEN_URL,
        {
            "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
            "code": got["code"], "code_verifier": verifier, "grant_type": "authorization_code",
            "redirect_uri": redirect,
        },
    )  # fmt: skip
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    _save_token(cfg, tok)
    return "Login Google berhasil"


def access_token(cfg: Config) -> str:
    p = token_path(cfg)
    if not p.is_file():
        raise GoogleError(
            "Belum login Google. Jalankan: uv run python -m jarvis.setup google-login"
        )
    tok = json.loads(p.read_text(encoding="utf-8"))
    if tok.get("expires_at", 0) - 60 > time.time():
        return tok["access_token"]
    if "refresh_token" not in tok:
        raise GoogleError("Login Google kedaluwarsa. Jalankan google-login lagi")
    c = _client(cfg)
    new = _post(
        TOKEN_URL,
        {
            "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        },
    )  # fmt: skip
    tok.update(new)
    tok["expires_at"] = time.time() + int(new.get("expires_in", 3600))
    _save_token(cfg, tok)
    return tok["access_token"]


def api(cfg: Config, method: str, url: str, body: dict | None = None) -> dict:
    """Panggil REST Google. Hanya host googleapis.com."""
    if urllib.parse.urlparse(url).hostname != "www.googleapis.com":
        raise GoogleError("Alamat API tidak diizinkan")
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {access_token(cfg)}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise GoogleError(f"Google menolak permintaan ({e.code}). Cek izin login") from e
    except OSError as e:
        raise GoogleError("Tidak bisa terhubung ke Google") from e
