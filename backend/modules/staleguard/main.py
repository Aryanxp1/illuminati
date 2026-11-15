import json
import math
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .config import REPO_DIR, Settings, load_settings
from .models import Check, CheckRequest, CheckSummary, Health, HealthModels, Sample, to_iso
from .pipeline import run_check
from .providers import get_llm, get_search

VERSION = "0.2.0"
SAMPLES_PATH = Path(__file__).parent / "fixtures" / "samples.json"
FRONTEND_DIST = REPO_DIR / "frontend" / "dist"


def utcnow() -> datetime:
    return datetime.now(UTC)  # one clock for the request limits, so tests can move it


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    llm, search = get_llm(settings), get_search(settings)
    recent_checks: dict[str, list[datetime]] = {}  # client address -> live check times

    def limit_live_checks(client: str) -> None:
        """Live mode only: per-client checks per minute, then the daily cap. Raises 429."""
        now = utcnow()
        recent = [t for t in recent_checks.get(client, []) if now - t < timedelta(minutes=1)]
        if len(recent) >= settings.rate_limit_per_minute:
            wait = 60 - (now - recent[0]).total_seconds()
            raise HTTPException(
                status_code=429,
                detail="Too many checks. Wait a minute and try again.",
                headers={"Retry-After": str(max(1, math.ceil(wait)))},
            )
        recent_checks[client] = [*recent, now]
        if not store.take_daily_slot(
            settings.database_path, now.date().isoformat(), settings.daily_live_checks
        ):
            raise HTTPException(
                status_code=429,
                detail="The daily limit of live checks is reached. Try again tomorrow (UTC).",
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.init(settings.database_path)
        yield

    app = FastAPI(title="ps5", version=VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Health:
        return Health(
            mode=settings.mode,
            version=VERSION,
            models=HealthModels(
                extract=settings.model_extract,
                judge=settings.model_judge,
                answer=settings.model_answer,
                fallbacks=settings.model_fallbacks,
            ),
        )

    @app.get("/api/samples")
    def samples() -> list[Sample]:
        return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))

    @app.post("/api/checks", response_model=None)
    async def create_check(
        request: CheckRequest, http: Request, background: BackgroundTasks, wait: bool = False
    ) -> Check | JSONResponse:
        if not settings.mock_mode:
            limit_live_checks(http.client.host if http.client else "unknown")
        check = Check(
            id=uuid.uuid4().hex[:12],
            created_at=to_iso(datetime.now(UTC)),
            # No answer means ask mode: run_check generates it first.
            status="queued" if request.answer else "generating",
            mode=settings.mode,
            question=request.question,
            answer=request.answer or "",
        )
        store.save(settings.database_path, check)
        if wait:
            return await run_check(check.id, settings, llm, search)
        background.add_task(run_check, check.id, settings, llm, search)
        return JSONResponse({"id": check.id}, status_code=202)

    @app.get("/api/checks")
    def list_checks(limit: int = Query(20, ge=1, le=50)) -> list[CheckSummary]:
        # Off by default: the list would show every pasted answer to anyone on the network.
        if not settings.shared_history:
            raise HTTPException(status_code=404, detail="Shared history is turned off")
        return [
            CheckSummary(
                id=c.id,
                created_at=c.created_at,
                status=c.status,
                mode=c.mode,
                overall_score=c.overall_score,
                excerpt=c.answer[:120],
                summary=c.summary,
            )
            for c in store.list_recent(settings.database_path, limit)
        ]

    @app.get("/api/checks/{check_id}")
    def get_check(check_id: str) -> Check:
        check = store.get(settings.database_path, check_id)
        if check is None:
            raise HTTPException(status_code=404, detail="Check not found")
        return check

    # Mounted last so every /api route wins.
    if (FRONTEND_DIST / "index.html").exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
