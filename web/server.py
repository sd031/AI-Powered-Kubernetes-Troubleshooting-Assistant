#!/usr/bin/env python3
"""
FastAPI backend for the K8s AI Troubleshooting Assistant web UI.

Each browser tab gets one WebSocket session. The TroubleshootAgent runs in
a ThreadPoolExecutor (it is synchronous) and emits events back to the
asyncio event loop via asyncio.run_coroutine_threadsafe.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import LLMProvider, Settings, get_settings, persist_to_env_file
from k8s.client import K8sClient
from k8s.tools import K8sTools
from llm.factory import get_llm_provider
from agents.troubleshoot_agent import IssueRecord, TroubleshootAgent
from runbook.generator import RunbookGenerator

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(title="K8s AI Troubleshooter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXECUTOR = ThreadPoolExecutor(max_workers=4)
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"

# ─── Session management ───────────────────────────────────────────────────────

class AgentSession:
    """Owns one TroubleshootAgent instance and its async event queue."""

    def __init__(self, settings: Settings) -> None:
        self.id = str(uuid.uuid4())
        self.settings = settings
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self._loop = asyncio.get_event_loop()

        k8s = K8sClient(
            kubeconfig=settings.effective_kubeconfig(),
            context=settings.k8s_context or None,
        )
        self._k8s = k8s
        tools = K8sTools(
            k8s=k8s,
            max_log_lines=settings.max_log_lines,
            auto_fix=settings.auto_fix,
        )
        llm = get_llm_provider(settings)

        runbook_gen = RunbookGenerator(
            output_dir=settings.ensure_runbook_dir(),
            cluster_context=k8s.current_context(),
            llm_provider=f"{llm.provider_name()} / {llm.model_name()}",
        )

        def on_runbook(issue: IssueRecord) -> None:
            path = runbook_gen.generate(issue)
            runbook_gen.generate_index()
            self._put({
                "type": "runbook",
                "path": str(path),
                "filename": path.name,
            })

        self.agent = TroubleshootAgent(
            llm=llm,
            k8s_tools=tools,
            runbook_callback=on_runbook,
            on_event=self._put,
        )
        # Wire threading primitives for confirmation
        self.agent._confirm_event = threading.Event()

        self._provider_info = {
            "provider": llm.provider_name(),
            "model": llm.model_name(),
            "context": k8s.current_context(),
            "k8s_version": k8s.server_version(),
        }

    def _put(self, event: dict) -> None:
        """Thread-safe: puts an event onto the asyncio queue."""
        asyncio.run_coroutine_threadsafe(self.queue.put(event), self._loop)

    def provider_info(self) -> dict:
        return self._provider_info

    def run_message(self, content: str) -> None:
        self.agent._process_turn(content)

    def run_scan(self) -> None:
        self.agent.run_scan()

    def run_fix(self, problem: str) -> None:
        self.agent.run_diagnose(problem)

    def resolve_confirm(self, answer: bool) -> None:
        self.agent.resolve_confirmation(answer)

    def reset(self) -> None:
        self.agent.reset_conversation()
        self._put({"type": "reset_ack"})


# Active sessions keyed by session_id
_sessions: dict[str, AgentSession] = {}


def _get_or_create_session(session_id: str) -> AgentSession:
    if session_id not in _sessions:
        settings = get_settings()
        _sessions[session_id] = AgentSession(settings)
    return _sessions[session_id]


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    try:
        session = _get_or_create_session(session_id)
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    # Send provider info immediately on connect
    await websocket.send_json({"type": "provider_info", **session.provider_info()})

    loop = asyncio.get_event_loop()

    async def sender() -> None:
        """Forward events from agent queue → WebSocket."""
        while True:
            event = await session.queue.get()
            try:
                await websocket.send_json(event)
            except Exception:
                break

    async def receiver() -> None:
        """Receive messages from WebSocket → dispatch to agent."""
        async for raw in websocket.iter_json():
            msg_type = raw.get("type")

            if msg_type == "message":
                content = raw.get("content", "").strip()
                if content:
                    loop.run_in_executor(EXECUTOR, session.run_message, content)

            elif msg_type == "scan":
                loop.run_in_executor(EXECUTOR, session.run_scan)

            elif msg_type == "fix":
                problem = raw.get("problem", "").strip()
                namespace = raw.get("namespace", "")
                if namespace:
                    problem = f"[Namespace: {namespace}] {problem}"
                if problem:
                    loop.run_in_executor(EXECUTOR, session.run_fix, problem)

            elif msg_type == "confirm":
                session.resolve_confirm(bool(raw.get("answer", False)))

            elif msg_type == "reset":
                loop.run_in_executor(EXECUTOR, session.reset)

    try:
        await asyncio.gather(sender(), receiver())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ─── REST endpoints ────────────────────────────────────────────────────────────

class ConfigRequest(BaseModel):
    llm_provider: Optional[str] = None
    ollama_model: Optional[str] = None
    # Bedrock
    bedrock_model_id: Optional[str] = None
    aws_region: Optional[str] = None
    # Single combined key: "ACCESS_KEY_ID:SECRET_ACCESS_KEY"
    # Empty string = keep existing values unchanged
    bedrock_api_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    # OpenAI
    openai_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    # K8s / behaviour
    k8s_context: Optional[str] = None
    auto_fix: Optional[bool] = None
    max_log_lines: Optional[int] = None


@app.get("/api/config")
def get_config() -> dict:
    s = get_settings()
    return {
        "llm_provider": s.llm_provider.value,
        "ollama_host": s.ollama_host,
        "ollama_model": s.ollama_model,
        # Bedrock — never return actual key values, only whether they are set
        "bedrock_model_id": s.bedrock_model_id,
        "aws_region": s.aws_region,
        "bedrock_api_key_configured": bool(s.bedrock_api_key),
        "aws_session_token_configured": bool(s.aws_session_token),
        # OpenAI — same
        "openai_model": s.openai_model,
        "openai_api_key_configured": bool(s.openai_api_key),
        # Common
        "k8s_context": s.k8s_context or "",
        "auto_fix": s.auto_fix,
        "max_log_lines": s.max_log_lines,
        "runbook_dir": str(s.runbook_dir),
    }


@app.post("/api/config")
def update_config(req: ConfigRequest) -> dict:
    """Update runtime config and clear all sessions so new settings take effect."""
    s = get_settings()
    if req.llm_provider:
        s.llm_provider = LLMProvider(req.llm_provider)
    if req.ollama_model:
        s.ollama_model = req.ollama_model
    if req.bedrock_model_id:
        s.bedrock_model_id = req.bedrock_model_id
    if req.aws_region:
        s.aws_region = req.aws_region
    if req.bedrock_api_key:
        s.bedrock_api_key = req.bedrock_api_key
    if req.aws_session_token:
        s.aws_session_token = req.aws_session_token
    if req.openai_model:
        s.openai_model = req.openai_model
    if req.openai_api_key:
        s.openai_api_key = req.openai_api_key
    if req.k8s_context is not None:
        s.k8s_context = req.k8s_context or None
    if req.auto_fix is not None:
        s.auto_fix = req.auto_fix
    if req.max_log_lines is not None:
        s.max_log_lines = req.max_log_lines
    _sessions.clear()

    # ── Persist changes so they survive server restarts ───────────────────────
    env_updates: dict[str, str] = {}
    if req.llm_provider:
        env_updates["LLM_PROVIDER"] = req.llm_provider
    if req.ollama_model:
        env_updates["OLLAMA_MODEL"] = req.ollama_model
    if req.bedrock_model_id:
        env_updates["BEDROCK_MODEL_ID"] = req.bedrock_model_id
    if req.aws_region:
        env_updates["AWS_REGION"] = req.aws_region
    if req.bedrock_api_key:
        env_updates["BEDROCK_API_KEY"] = req.bedrock_api_key
    if req.aws_session_token:
        env_updates["AWS_SESSION_TOKEN"] = req.aws_session_token
    if req.openai_model:
        env_updates["OPENAI_MODEL"] = req.openai_model
    if req.openai_api_key:
        env_updates["OPENAI_API_KEY"] = req.openai_api_key
    if req.k8s_context is not None:
        env_updates["K8S_CONTEXT"] = req.k8s_context or ""
    if req.auto_fix is not None:
        env_updates["AUTO_FIX"] = "true" if req.auto_fix else "false"
    if req.max_log_lines is not None:
        env_updates["MAX_LOG_LINES"] = str(req.max_log_lines)
    if env_updates:
        persist_to_env_file(env_updates)

    return {"status": "ok"}


@app.get("/api/cluster/contexts")
def list_contexts() -> dict:
    try:
        from kubernetes import config as kconfig
        contexts, active = kconfig.list_kube_config_contexts()
        return {
            "contexts": [c["name"] for c in contexts],
            "active": active["name"] if active else "",
        }
    except Exception as exc:
        return {"contexts": [], "active": "", "error": str(exc)}


@app.get("/api/cluster/health")
def cluster_health() -> dict:
    try:
        s = get_settings()
        k8s = K8sClient(kubeconfig=s.effective_kubeconfig(), context=s.k8s_context or None)
        tools = K8sTools(k8s=k8s)
        summary = tools.check_cluster_health()
        return {"status": "ok", "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/runbooks")
def list_runbooks() -> dict:
    s = get_settings()
    rdir = s.runbook_dir
    if not rdir.exists():
        return {"runbooks": []}

    files = sorted(rdir.glob("*.md"), reverse=True)
    files = [f for f in files if f.name != "index.md"]

    runbooks = []
    for f in files:
        try:
            from datetime import datetime
            dt = datetime.strptime(f.stem[:15], "%Y%m%d-%H%M%S")
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            date_str = "?"
        title = f.stem[16:].replace("-", " ").title() if len(f.stem) > 16 else f.stem
        runbooks.append({
            "filename": f.name,
            "title": title,
            "date": date_str,
            "size": f.stat().st_size,
        })

    return {"runbooks": runbooks}


@app.get("/api/runbooks/{filename}")
def get_runbook(filename: str) -> dict:
    s = get_settings()
    path = s.runbook_dir / filename
    if not path.exists() or not path.suffix == ".md":
        raise HTTPException(status_code=404, detail="Runbook not found")
    return {"filename": filename, "content": path.read_text(encoding="utf-8")}


@app.delete("/api/runbooks/{filename}")
def delete_runbook(filename: str) -> dict:
    s = get_settings()
    path = s.runbook_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Runbook not found")
    path.unlink()
    return {"status": "deleted"}


# ─── Serve built frontend ──────────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        index = STATIC_DIR / "index.html"
        return FileResponse(index)
else:
    @app.get("/")
    def dev_notice() -> HTMLResponse:
        return HTMLResponse(
            "<h2>Backend running.</h2>"
            "<p>Start the frontend dev server: <code>cd web/frontend && npm run dev</code></p>"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
