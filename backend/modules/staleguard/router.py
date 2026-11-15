import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ...database import get_db, FreshnessCheckRecord
from .config import load_settings
from .providers import get_llm, get_search
from .pipeline import run_check
from .models import Check, to_iso
from . import store

router = APIRouter(prefix="/api/freshness", tags=["Freshness Detector (Tavily PS 01)"])

SAMPLES_PATH = Path(__file__).parent / "fixtures" / "samples.json"

class QuickCheckRequest(BaseModel):
    text: str
    mode: Optional[str] = "check" # "check" or "ask"
    max_claims: Optional[int] = 5

@router.get("/samples")
def get_samples():
    if SAMPLES_PATH.exists():
        with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {
            "id": "pricing",
            "title": "SaaS Pricing",
            "question": "How much does Spotify Premium cost?",
            "answer": "Spotify Premium individual plan costs $9.99 per month with unlimited music streaming. Duo costs $12.99 per month."
        },
        {
            "id": "api-versions",
            "title": "API Versions",
            "question": "What is the latest stable version of Python and Node.js?",
            "answer": "Python 3.12 is the latest stable version of Python. The current long-term support release of Node.js is version 20."
        }
    ]

@router.post("/check")
async def check_freshness(req: QuickCheckRequest, db: Session = Depends(get_db)):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
        
    settings = load_settings()
    store.init(settings.database_path)
    llm = get_llm(settings)
    search = get_search(settings)
    
    check_id = uuid.uuid4().hex[:12]
    check = Check(
        id=check_id,
        created_at=to_iso(datetime.now(UTC)),
        status="queued" if req.mode == "check" else "generating",
        mode=settings.mode,
        question=req.text if req.mode == "ask" else None,
        answer=req.text if req.mode == "check" else "",
    )
    store.save(settings.database_path, check)
    check_result = await run_check(check.id, settings, llm, search)
    check_dict = check_result.model_dump()
    
    # Save check in unified DB
    try:
        record = FreshnessCheckRecord(
            id=check_dict["id"],
            mode=req.mode or "check",
            query=check_dict.get("question"),
            answer=check_dict.get("answer", req.text),
            freshness_score=check_dict.get("score") or 100,
            verdict_label=check_dict.get("label", "fresh"),
            claims_total=len(check_dict.get("claims", [])),
            claims_stale=len([c for c in check_dict.get("claims", []) if c.get("verdict", {}).get("status") == "outdated"]),
            corrected_answer=check_dict.get("corrected_answer"),
            details_json=json.dumps(check_dict)
        )
        db.add(record)
        db.commit()
    except Exception:
        pass
        
    return check_dict

@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    records = db.query(FreshnessCheckRecord).order_by(FreshnessCheckRecord.created_at.desc()).limit(20).all()
    return [
        {
            "id": r.id,
            "mode": r.mode,
            "score": r.freshness_score,
            "label": r.verdict_label,
            "claims_total": r.claims_total,
            "claims_stale": r.claims_stale,
            "answer_preview": r.answer[:80] + ("..." if len(r.answer) > 80 else ""),
            "created_at": r.created_at.isoformat()
        }
        for r in records
    ]
