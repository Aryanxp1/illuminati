"""Shapes from contracts/api.md, plus the internal types the providers exchange."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CheckStatus = Literal["queued", "generating", "extracting", "verifying", "done", "error"]
Category = Literal[
    "pricing", "version", "regulation", "leadership", "company_fact", "statistic", "other"
]
Volatility = Literal["high", "medium", "low"]
ClaimStatus = Literal["pending", "verifying", "done", "skipped", "error"]
Verdict = Literal["current", "outdated", "unverified"]
Label = Literal["fresh", "review", "stale", "unverified"]
Stance = Literal["supports", "contradicts", "neutral"]
Mode = Literal["mock", "live"]


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class HealthModels(BaseModel):
    extract: str
    judge: str
    answer: str
    fallbacks: list[str]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    mode: Mode
    version: str
    models: HealthModels


class Sample(BaseModel):
    id: str
    title: str
    question: str | None
    answer: str


class CheckRequest(BaseModel):
    answer: str | None = Field(default=None, min_length=1, max_length=8000)
    question: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def answer_or_question(self) -> "CheckRequest":
        if self.answer is None and self.question is None:
            raise ValueError("Provide an answer to check or a question to ask.")
        return self


class Evidence(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: str | None
    score: float
    stance: Stance = "neutral"


class ScoreBreakdown(BaseModel):
    verdict: Verdict
    confidence: float
    recency: float
    agreement: float
    quality: float


class Claim(BaseModel):
    id: str
    text: str
    start: int
    end: int
    category: Category
    time_sensitive: bool
    volatility: Volatility
    risk_reason: str
    search_query: str
    status: ClaimStatus = "pending"
    verdict: Verdict | None = None
    freshness_score: int | None = None
    label: Label | None = None
    current_value: str | None = None
    explanation: str | None = None
    confidence: float | None = None
    score_breakdown: ScoreBreakdown | None = None
    evidence: list[Evidence] = []
    cached: bool = False
    error: str | None = None


class ModelCall(BaseModel):
    stage: Literal["answer", "extract", "judge", "rewrite"]
    requested: str
    served_by: str
    is_fallback: bool
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class Summary(BaseModel):
    fresh: int = 0
    review: int = 0
    stale: int = 0
    unverified: int = 0
    skipped: int = 0


class Usage(BaseModel):
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    search_calls: int = 0
    cache_hits: int = 0
    duration_ms: int = 0


class Check(BaseModel):
    id: str
    created_at: str
    status: CheckStatus
    mode: Mode
    question: str | None = None
    answer: str
    corrected_answer: str | None = None
    overall_score: int | None = None
    summary: Summary = Field(default_factory=Summary)
    claims: list[Claim] = []
    model_calls: list[ModelCall] = []
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None


class CheckSummary(BaseModel):
    id: str
    created_at: str
    status: CheckStatus
    mode: Mode
    overall_score: int | None
    excerpt: str
    summary: Summary


# Internal: what providers return.


class RawClaim(BaseModel):
    text: str = Field(min_length=1)
    category: Category
    time_sensitive: bool
    volatility: Volatility
    risk_reason: str = ""
    search_query: str = ""


class Judgement(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    current_value: str | None = None
    explanation: str = ""
    stances: list[Stance] = []


class SearchResult(BaseModel):
    evidence: list[Evidence]
    answer: str | None = None
    calls: int = 1  # HTTP requests made, so a retry counts toward usage.search_calls


class CachedVerification(BaseModel):
    volatility: Volatility
    verdict: Verdict
    confidence: float
    current_value: str | None
    explanation: str | None
    evidence: list[Evidence]
