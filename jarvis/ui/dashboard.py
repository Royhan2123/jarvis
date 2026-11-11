# ruff: noqa: E501  (halaman HTML inline sengaja satu file)
"""Dashboard web lokal (FastAPI): lihat log, edit config, daftar tool & plugin.

Keamanan: hanya bind 127.0.0.1; header Host divalidasi (anti DNS-rebinding); semua endpoint
butuh token acak per proses (cookie SameSite=Strict); perubahan butuh header X-Requested-With
(anti CSRF); config divalidasi pydantic sebelum disimpan. Tidak ada eksekusi tool dari dashboard.
"""

from __future__ import annotations

import secrets
import threading
from collections import deque
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from pydantic import BaseModel, ValidationError

from jarvis.agent import policy
from jarvis.config import Config
from jarvis.tools import plugins
from jarvis.tools.registry import registry

COOKIE = "jarvis_dash"
MAX_CONFIG_BYTES = 64_000
LOG_LINES: deque[str] = deque(maxlen=500)
_sink_id: int | None = None


class ConfigBody(BaseModel):
    yaml: str


class AgentBody(BaseModel):
    confirm_actions: list[str]
    persist: bool = (
        False  # True: tulis juga ke config.yaml (tanpa itu hanya sampai Jarvis dimatikan)
    )


def _install_log_sink() -> None:
    global _sink_id
    if _sink_id is None:
        _sink_id = logger.add(
            lambda m: LOG_LINES.append(str(m).rstrip()),
            level="INFO",
            format="{time:HH:mm:ss} {level:<7} {message}",
        )


def create_app(cfg: Config, config_path: Path, token: str, port: int) -> FastAPI:
    app = FastAPI(title="Jarvis Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def guard(request: Request, call_next):  # noqa: ANN001, ANN202
        if request.headers.get("host", "") not in allowed_hosts:
            return Response("Host tidak diizinkan", status_code=403)
        return await call_next(request)

    def auth(request: Request) -> None:
        got = request.cookies.get(COOKIE, "")
        if not secrets.compare_digest(got.encode(), token.encode()):
            raise HTTPException(401, "Butuh token. Buka URL dari log Jarvis.")

    def csrf(request: Request) -> None:
        if request.headers.get("x-requested-with") != "jarvis-dashboard":
            raise HTTPException(403, "Header X-Requested-With wajib")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, token: str | None = None):  # noqa: ANN202
        if token is not None:
            if not secrets.compare_digest(token.encode(), globals_token(app).encode()):
                raise HTTPException(401, "Token salah")
            resp = RedirectResponse("/", status_code=303)
            resp.set_cookie(COOKIE, token, httponly=True, samesite="strict")
            return resp
        auth(request)
        return HTMLResponse(PAGE)

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status() -> dict:
        return {
            "name": cfg.general.name,
            "offline_only": cfg.general.offline_only,
            "models": {"fast": cfg.llm.fast_model, "smart": cfg.llm.smart_model},
            "config_path": str(config_path),
        }

    @app.get("/api/logs", dependencies=[Depends(auth)])
    def logs() -> dict:
        return {"lines": list(LOG_LINES)}

    @app.get("/api/tools", dependencies=[Depends(auth)])
    def tools() -> dict:
        items = [
            {
                "name": t.name,
                "risk": t.risk.value,
                "category": t.category,
                "description": t.description,
            }
            for n in registry.names()
            if (t := registry.get(n))
        ]
        return {
            "tools": items,
            "plugins": list(plugins.LOADED),
            "plugins_dir": str(plugins.plugins_dir(cfg)),
        }

    @app.get("/api/config", dependencies=[Depends(auth)])
    def get_config() -> dict:
        text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        return {"yaml": text}

    @app.put("/api/config", dependencies=[Depends(auth), Depends(csrf)])
    def put_config(body: ConfigBody) -> dict:
        if len(body.yaml.encode()) > MAX_CONFIG_BYTES:
            raise HTTPException(413, "Config terlalu besar")
        try:
            Config.model_validate(yaml.safe_load(body.yaml) or {})
        except (yaml.YAMLError, ValidationError) as e:
            raise HTTPException(422, f"Config tidak valid: {str(e)[:600]}") from e
        if config_path.exists():
            config_path.with_suffix(".yaml.bak").write_text(
                config_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        tmp = config_path.with_suffix(".yaml.tmp")
        tmp.write_text(body.yaml, encoding="utf-8")
        tmp.replace(config_path)
        logger.info("Config diubah lewat dashboard (berlaku setelah Jarvis di-restart)")
        return {"ok": True, "note": "Tersimpan. Restart Jarvis agar berlaku."}

    @app.get("/api/agent", dependencies=[Depends(auth)])
    def get_agent() -> dict:
        return {
            "confirm_actions": list(cfg.agent.confirm_actions),
            "actions": [{"id": a, "label": policy.LABELS[a]} for a in policy.ACTIONS],
            "enabled": cfg.agent.enabled,
        }

    @app.put("/api/agent", dependencies=[Depends(auth), Depends(csrf)])
    def put_agent(body: AgentBody) -> dict:
        unknown = [a for a in body.confirm_actions if a not in policy.ACTIONS]
        if unknown:
            raise HTTPException(422, f"Aksi tidak dikenal: {', '.join(unknown)}")
        keep = set(body.confirm_actions)
        cfg.agent.confirm_actions = [a for a in policy.ACTIONS if a in keep]  # type: ignore[assignment]
        persisted = (
            policy.persist(config_path, list(cfg.agent.confirm_actions)) if body.persist else False
        )
        logger.info(
            f"Izin agen diubah lewat dashboard: tanya dulu untuk {cfg.agent.confirm_actions}"
        )
        note = policy.summary(list(cfg.agent.confirm_actions))
        if body.persist and not persisted:
            note += " Tidak tersimpan permanen: baris confirm_actions tidak ada di config.yaml."
        return {
            "ok": True,
            "confirm_actions": list(cfg.agent.confirm_actions),
            "persisted": persisted,
            "note": note,
        }

    app.state.token = token
    return app


def globals_token(app: FastAPI) -> str:
    return app.state.token


def start_dashboard(cfg: Config, config_path: str | Path) -> str | None:
    """Jalankan dashboard di thread latar; kembalikan URL (berisi token) atau None jika gagal."""
    try:
        import uvicorn
    except ImportError:
        logger.warning("Dashboard butuh paket uvicorn")
        return None
    _install_log_sink()
    port = cfg.ui.dashboard.port
    token = secrets.token_urlsafe(24)
    app = create_app(cfg, Path(config_path).resolve(), token, port)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    threading.Thread(target=server.run, name="dashboard", daemon=True).start()
    url = f"http://127.0.0.1:{port}/?token={token}"
    logger.info(f"Dashboard: {url}")
    return url


PAGE = """<!doctype html><meta charset="utf-8"><title>Jarvis Dashboard</title>
<style>body{font:14px system-ui;margin:0;background:#111;color:#eee}header{padding:12px 20px;background:#1b1b1f}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}section{background:#1b1b1f;border-radius:8px;padding:12px}
h2{margin:0 0 8px;font-size:15px}pre,textarea{width:100%;box-sizing:border-box;background:#0b0b0d;color:#cde;border:1px solid #333;
border-radius:6px;padding:8px;font:12px ui-monospace,monospace}pre{height:300px;overflow:auto;margin:0}textarea{height:300px}
table{width:100%;border-collapse:collapse}td{padding:3px 6px;border-bottom:1px solid #2a2a30}button{padding:6px 12px}
.high{color:#f66}.medium{color:#fb4}.low{color:#6c6}</style>
<header><b id=t>Jarvis</b> <span id=s></span></header>
<main><section><h2>Log</h2><pre id=log></pre></section>
<section><h2>Config (config.yaml)</h2><textarea id=cfg spellcheck=false></textarea>
<button onclick=save()>Simpan</button> <span id=msg></span></section>
<section style="grid-column:span 2"><h2>Izin agen kerja</h2>
<div>Tanya izin dulu sebelum: <span id=ag></span></div>
<label><input type=checkbox id=agp> simpan permanen ke config.yaml</label> <button onclick=applyAgent()>Terapkan</button> <span id=agm></span>
<div style="color:#999;margin-top:6px">Berlaku seketika. Blokir keras (sudo, hapus massal, file rahasia) tetap berlaku walau izin dimatikan.</div></section>
<section style="grid-column:span 2"><h2>Tool &amp; plugin</h2><div id=pl></div><table id=tools></table></section></main>
<script>
const j=u=>fetch(u).then(r=>r.json());
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function load(){
 const st=await j('/api/status');t.textContent=st.name+' Dashboard';
 s.textContent=(st.offline_only?'offline_only':'online diizinkan')+' | '+st.models.fast+' / '+st.models.smart;
 cfg.value=(await j('/api/config')).yaml;refresh();tl();loadAgent()}
async function refresh(){const l=(await j('/api/logs')).lines;log.textContent=l.join('\\n');log.scrollTop=log.scrollHeight}
async function tl(){const d=await j('/api/tools');
 pl.textContent='Plugin dimuat: '+(d.plugins.join(', ')||'(tidak ada)')+' — folder: '+d.plugins_dir;
 tools.innerHTML=d.tools.map(x=>`<tr><td>${esc(x.name)}</td><td class=${esc(x.risk)}>${esc(x.risk)}</td><td>${esc(x.category)}</td><td>${esc(x.description)}</td></tr>`).join('')}
async function loadAgent(){const d=await j('/api/agent');
 ag.innerHTML=d.actions.map(a=>`<label style="margin-right:12px"><input type=checkbox data-a="${esc(a.id)}" ${d.confirm_actions.includes(a.id)?'checked':''}> ${esc(a.label)}</label>`).join('')}
async function applyAgent(){const on=[...ag.querySelectorAll('input:checked')].map(x=>x.dataset.a);
 const r=await fetch('/api/agent',{method:'PUT',headers:{'Content-Type':'application/json','X-Requested-With':'jarvis-dashboard'},
 body:JSON.stringify({confirm_actions:on,persist:agp.checked})});const d=await r.json();agm.textContent=r.ok?d.note:(d.detail||'Gagal')}
async function save(){const r=await fetch('/api/config',{method:'PUT',headers:{'Content-Type':'application/json','X-Requested-With':'jarvis-dashboard'},
 body:JSON.stringify({yaml:cfg.value})});const d=await r.json();msg.textContent=r.ok?d.note:(d.detail||'Gagal')}
load();setInterval(refresh,3000);
</script>"""
