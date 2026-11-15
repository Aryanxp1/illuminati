"""Deterministic freshness score (plan.md "Freshness score"). Pure functions; `now` is passed in."""

import math
from datetime import UTC, datetime

from .models import Claim, Evidence, Label, ScoreBreakdown, Summary, Verdict, Volatility

HALF_LIFE_DAYS = {
    "pricing": 90,
    "version": 120,
    "leadership": 180,
    "regulation": 365,
    "company_fact": 365,
    "statistic": 365,
    "other": 365,
}
VOLATILITY_WEIGHT = {"high": 1.0, "medium": 0.5, "low": 0.0}
AGREEING_STANCE = {"current": "supports", "outdated": "contradicts"}


def _round(x: float) -> int:
    # Half-up, so 42.5 becomes 43 rather than Python's banker's 42.
    return math.floor(x + 0.5)


def _recency(item: Evidence, half_life: float, now: datetime) -> float:
    if not item.published_date:
        return 0.5
    try:
        published = datetime.fromisoformat(item.published_date)
    except ValueError:
        return 0.5
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    age_days = max((now - published).total_seconds() / 86400, 0.0)
    return math.exp(-age_days / half_life)


def score_claim(
    verdict: Verdict,
    confidence: float,
    category: str,
    volatility: Volatility,
    evidence: list[Evidence],
    now: datetime,
) -> tuple[int, ScoreBreakdown]:
    bearing = [e for e in evidence if e.stance in ("supports", "contradicts")]
    half_life = HALF_LIFE_DAYS[category]
    if bearing:
        recency = sum(_recency(e, half_life, now) for e in bearing) / len(bearing)
        agreeing = AGREEING_STANCE.get(verdict)
        agreement = sum(e.stance == agreeing for e in bearing) / len(bearing)
    else:
        recency = agreement = 0.5
    quality = confidence * (0.5 * recency + 0.5 * agreement)

    if verdict == "current":
        score = _round(65 + 35 * quality)
    elif verdict == "outdated":
        score = _round(35 * (1 - quality))
    else:
        score = _round(50 - 15 * VOLATILITY_WEIGHT[volatility])

    breakdown = ScoreBreakdown(
        verdict=verdict,
        confidence=round(confidence, 2),
        recency=round(recency, 2),
        agreement=round(agreement, 2),
        quality=round(quality, 2),
    )
    return score, breakdown


def label_for(verdict: Verdict, score: int) -> Label:
    if verdict == "unverified":
        return "unverified"
    if score >= 75:
        return "fresh"
    if score >= 40:
        return "review"
    return "stale"


def overall_score(claims: list[Claim]) -> int | None:
    scores = [c.freshness_score for c in claims if c.freshness_score is not None]
    return _round(sum(scores) / len(scores)) if scores else None


def summarize(claims: list[Claim]) -> Summary:
    summary = Summary()
    for c in claims:
        if c.status == "skipped":
            summary.skipped += 1
        elif c.label:
            setattr(summary, c.label, getattr(summary, c.label) + 1)
    return summary
