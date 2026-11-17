import os
import sys
import time
import uuid
import json
import asyncio
import types
from pathlib import Path
from contextlib import asynccontextmanager

# Windows Defender Application Control compatibility guard:
try:
    import _multiprocessing
except (ImportError, OSError):
    mock_mp = types.ModuleType("_multiprocessing")
    mock_mp.closesocket = lambda fd: None
    mock_mp.send = lambda fd, buf, flags=0: None
    mock_mp.recv = lambda fd, size, flags=0: b""
    sys.modules["_multiprocessing"] = mock_mp

# Ensure root directory and arena are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ARENA_DIR = ROOT_DIR / "backend" / "modules" / "arena"
if str(ARENA_DIR) not in sys.path:
    sys.path.insert(0, str(ARENA_DIR))

from fastapi import FastAPI, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, Base, SessionLocal, init_db, get_db
from .gateway.bifrost import bifrost
from .gateway.tavily_client import tavily
from .terminal_bridge import (
    terminal_manager,
    sanitize_output,
    IDLE_TIMEOUT_SECONDS,
    MAX_SESSION_DURATION_SECONDS
)

# Import module routers
from .modules.coding_agent.router import router as coding_router
from .modules.staleguard.router import router as freshness_router
from .modules.briefing.router import router as briefing_router

# Arena routes and models
from routes import tasks as arena_tasks
from routes import agents as arena_agents
from routes import benchmarks as arena_benchmarks
from routes import lab as arena_lab
from models import BenchmarkTask, Agent
from tasks.seed_tasks import SEED_TASKS
from arena_db import SessionLocal as ArenaSessionLocal

FRONTEND_DIR = ROOT_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB tables
    init_db()
    
    # 2. Seed Arena tasks and reference agents if empty
    db = ArenaSessionLocal()
    try:
        if db.query(BenchmarkTask).count() == 0:
            print("🌱 Seeding 12 built-in Arena benchmark tasks...")
            for t in SEED_TASKS:
                task_obj = BenchmarkTask(
                    id=t["id"],
                    name=t["name"],
                    category=t["category"],
                    prompt=t["prompt"],
                    available_tools=t.get("available_tools", []),
                    expected_output=t.get("expected_output", ""),
                    verifier_rule=t.get("verifier_rule", "exact"),
                    max_steps=t.get("max_steps", 5),
                    max_tokens=t.get("max_tokens", 1500),
                    timeout_seconds=t.get("timeout_seconds", 30),
                    difficulty=t.get("difficulty", "medium"),
                    tags=t.get("tags", []),
                    failure_injection=t.get("failure_injection", {})
                )
                db.add(task_obj)
            db.commit()

        if db.query(Agent).count() == 0:
            print("🌱 Seeding 5 reference agent architectures...")
            agents_seed = [
                {"id": "agent-react-01", "name": "Direct ReAct Loop", "agent_type": "react", "description": "Standard Thought-Action-Observation loop without failure retry"},
                {"id": "agent-react-retry-05", "name": "ReAct with Backoff Retry", "agent_type": "react_retry", "description": "ReAct loop with exponential backoff on HTTP 429/500"},
                {"id": "agent-langgraph-02", "name": "LangGraph StateGraph", "agent_type": "langgraph", "description": "Checkpoint-driven stateful agent with conditional fallback edges"},
                {"id": "agent-custom-03", "name": "Custom JSON Agent", "agent_type": "custom_json", "description": "Strict schema-enforced JSON agent with tool sandboxing"},
                {"id": "agent-webhook-04", "name": "HTTP Webhook Agent", "agent_type": "webhook", "description": "External agent invoked via HTTP POST webhook protocol"}
            ]
            for a in agents_seed:
                agent_obj = Agent(**a)
                db.add(agent_obj)
            db.commit()
    except Exception as e:
        print(f"⚠️ Note on seeding: {e}")
    finally:
        db.close()
    
    try:
        yield
    finally:
        # Graceful cleanup of all active PTY terminal sessions
        terminal_manager.close_all()

app = FastAPI(
    title="Illuminati — Unified AI Agent & Reliability Observatory Platform",
    version=settings.VERSION,
    description="All-in-one AI platform solving Bifrost PS01, PS02 and Tavily PS01, PS02",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all 4 problem statement module routers
app.include_router(coding_router)         # Bifrost PS 01: Coding Agent (Fewest Tokens)
app.include_router(arena_tasks.router)     # Bifrost PS 02: Arena Tasks
app.include_router(arena_agents.router)    # Bifrost PS 02: Arena Agents
app.include_router(arena_benchmarks.router)# Bifrost PS 02: Arena Benchmark Runs
app.include_router(arena_lab.router)       # Bifrost PS 02: Reliability Lab & ARS
app.include_router(freshness_router)       # Tavily PS 01: StaleGuard Freshness Detector
app.include_router(briefing_router)        # Tavily PS 02: Pre-Meeting Briefing Agent

# Unified Gateway & System status endpoints
@app.get("/api/gateway/status")
def gateway_status():
    bf_status = bifrost.get_status()
    tv_status = tavily.get_status()
    is_live = bf_status.get("connected", False) and tv_status.get("api_key_configured", False)
    return {
        "bifrost": bf_status,
        "tavily": tv_status,
        "team": settings.TEAM,
        "author": settings.AUTHOR,
        "mode": "LIVE_PRODUCTION" if is_live else "SIMULATION_MODE"
    }

@app.get("/api/system/stats")
def system_stats(db: Session = Depends(get_db)):
    from models import BenchmarkRun, BenchmarkTask, Agent
    from backend.database import FreshnessCheckRecord, MeetingBriefRecord, CodingTaskRecord
    return {
        "platform": settings.PROJECT_NAME,
        "team": settings.TEAM,
        "author": settings.AUTHOR,
        "engines": {
            "bifrost_ps01_coding_agent": {
                "name": "Token-Governed Coding Agent",
                "tasks_executed": db.query(CodingTaskRecord).count()
            },
            "bifrost_ps02_agentbench_arena": {
                "name": "AgentBench Arena & Observatory",
                "benchmarks_run": db.query(BenchmarkRun).count(),
                "available_tasks": db.query(BenchmarkTask).count(),
                "reference_agents": db.query(Agent).count()
            },
            "tavily_ps01_freshness_detector": {
                "name": "StaleGuard Freshness Detector",
                "checks_completed": db.query(FreshnessCheckRecord).count()
            },
            "tavily_ps02_pre_meeting_briefing": {
                "name": "Groundwork / Vouch Meeting Intelligence",
                "briefs_generated": db.query(MeetingBriefRecord).count()
            }
        }
    }

# Serve frontend dashboard & documentation
@app.get("/")
def serve_dashboard():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Illuminati Unified AI Platform API is running. Frontend index.html not found."}

@app.get("/overview")
@app.get("/docs-guide")
@app.get("/docs.html")
@app.get("/documentation")
def serve_documentation():
    docs_file = FRONTEND_DIR / "docs.html"
    if docs_file.exists():
        return FileResponse(docs_file)
    return {"message": "Documentation page not found at frontend/docs.html"}

@app.get("/terminal")
def serve_terminal():
    terminal_file = FRONTEND_DIR / "terminal.html"
    if terminal_file.exists():
        return FileResponse(terminal_file)
    return {"message": "Terminal UI not found at frontend/terminal.html"}

@app.get("/api/terminal/stats")
def terminal_stats():
    return {
        "active_sessions": terminal_manager.active_count(),
        "max_sessions": terminal_manager.max_sessions,
        "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
        "max_duration_seconds": MAX_SESSION_DURATION_SECONDS
    }

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())

    cols = 100
    rows = 30
    try:
        cols_q = websocket.query_params.get("cols")
        rows_q = websocket.query_params.get("rows")
        if cols_q:
            cols = max(20, min(int(cols_q), 300))
        if rows_q:
            rows = max(10, min(int(rows_q), 100))
    except Exception:
        pass

    try:
        pty_session = await terminal_manager.create_session(session_id, cols=cols, rows=rows)
    except Exception as exc:
        err_msg = (
            "\r\n\x1b[1;31m[!] Illuminati Cloud Terminal Notice\x1b[0m\r\n"
            f"\x1b[33m{str(exc)}\x1b[0m\r\n\r\n"
        )
        await websocket.send_text(err_msg)
        await asyncio.sleep(0.5)
        await websocket.close(code=1008)
        return

    async def pty_to_ws():
        try:
            while pty_session.is_alive():
                chunk = await pty_session.read()
                if chunk:
                    clean_chunk = sanitize_output(chunk)
                    await websocket.send_text(clean_chunk)
                else:
                    await asyncio.sleep(0.015)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass

    async def ws_to_pty():
        try:
            while pty_session.is_alive():
                msg = await websocket.receive_text()
                if not msg:
                    continue
                if msg.startswith("{") and msg.endswith("}"):
                    try:
                        data = json.loads(msg)
                        msg_type = data.get("type")
                        if msg_type == "resize":
                            new_cols = data.get("cols", cols)
                            new_rows = data.get("rows", rows)
                            pty_session.resize(new_cols, new_rows)
                            continue
                        elif msg_type == "ping":
                            pong_resp = {"type": "pong", "time": time.time()}
                            if "client_time" in data:
                                pong_resp["client_time"] = data["client_time"]
                            await websocket.send_text(json.dumps(pong_resp))
                            continue
                        elif msg_type == "input":
                            raw_in = data.get("data", "")
                            await pty_session.write(raw_in)
                            continue
                    except json.JSONDecodeError:
                        pass
                await pty_session.write(msg)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass

    async def session_watchdog():
        try:
            while pty_session.is_alive():
                await asyncio.sleep(2.0)
                now = time.time()
                if (now - pty_session.last_active_at) > IDLE_TIMEOUT_SECONDS:
                    await websocket.send_text(
                        "\r\n\x1b[1;33m[Session timed out due to 5 minutes of inactivity. Disconnected.]\x1b[0m\r\n"
                    )
                    break
                if (now - pty_session.created_at) > MAX_SESSION_DURATION_SECONDS:
                    await websocket.send_text(
                        "\r\n\x1b[1;33m[Session reached maximum time limit (15m). Disconnected.]\x1b[0m\r\n"
                    )
                    break
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    t_pty = asyncio.create_task(pty_to_ws())
    t_ws = asyncio.create_task(ws_to_pty())
    t_wd = asyncio.create_task(session_watchdog())

    done, pending = await asyncio.wait(
        [t_pty, t_ws, t_wd],
        return_when=asyncio.FIRST_COMPLETED
    )
    for p in pending:
        p.cancel()

    await terminal_manager.remove_session(session_id)
    try:
        await websocket.close()
    except Exception:
        pass

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend_static")
