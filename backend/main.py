import os
import sys
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

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, Base, SessionLocal, init_db, get_db
from .gateway.bifrost import bifrost
from .gateway.tavily_client import tavily

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
    
    yield

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

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend_static")
