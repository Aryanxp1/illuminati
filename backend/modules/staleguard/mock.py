"""Keyless stand-ins: rule-based extraction, fixture-backed search and judging."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Claim, Evidence, Judgement, ModelCall, RawClaim, SearchResult, to_iso

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_FIXTURES = json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))
SAMPLES = json.loads((FIXTURES / "samples.json").read_text(encoding="utf-8"))
SEARCH_DELAY_S = 0.3  # makes the progressive UI visible; tests set it to 0
MOCK_MODEL = "mock/rules"

YEAR = re.compile(r"\b(19|20)\d{2}\b")
# First matching rule wins: (category, volatility, risk_reason, pattern).
RULES = [
    ("leadership", "medium", "Company leadership changes.",
     re.compile(r"\b(CEO|CTO|CFO|founder|co-founder|president|chief executive)\b", re.I)),
    ("pricing", "high", "Prices and plans change often.",
     re.compile(r"[$€£]\d|\bper (month|year|seat|user)\b|\bpric(e|es|ing)\b", re.I)),
    ("regulation", "low", "Laws, rules and tax rates are amended.",
     re.compile(r"\b(law|act|regulation|directive|tax|VAT|levy|statute|mandate)\b", re.I)),
    ("statistic", "medium", "Figures tied to a date go out of date.",
     re.compile(r"\d+(\.\d+)?%|\b\d[\d,]*\s+(users|customers|employees|developers)\b", re.I)),
    ("version", "high", "Software versions are superseded by new releases.",
     re.compile(r"\bv\d+(\.\d+)*\b|\bversion\s+\d|\b\d+\.\d+(\.\d+)?\b", re.I)),
]


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def classify(sentence: str) -> RawClaim:
    for category, volatility, reason, pattern in RULES:
        if pattern.search(sentence) and (category != "statistic" or YEAR.search(sentence)):
            return RawClaim(text=sentence, category=category, time_sensitive=True,
                            volatility=volatility, risk_reason=reason,
                            search_query=sentence.rstrip("."))
    return RawClaim(text=sentence, category="other", time_sensitive=False, volatility="low",
                    risk_reason="No time-sensitive detail.", search_query="")


def match_fixture(text: str) -> dict | None:
    lowered = text.lower()
    for entry in SEARCH_FIXTURES:
        if all(k in lowered for k in entry["keywords"]):
            return entry
    return None


def mock_call(stage: str) -> ModelCall:
    return ModelCall(stage=stage, requested=MOCK_MODEL, served_by=MOCK_MODEL, is_fallback=False,
                     prompt_tokens=0, completion_tokens=0, latency_ms=0)


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


class MockLLM:
    async def answer(self, question: str) -> tuple[str, ModelCall]:
        asked = words(question)
        best = max(SAMPLES, key=lambda s: len(asked & words(s["question"] or "")))
        if not asked & words(best["question"] or ""):
            best = SAMPLES[0]
        return best["answer"], mock_call("answer")

    async def rewrite(self, answer: str, outdated: list[Claim]) -> tuple[str, ModelCall]:
        # Only the outdated value inside each claim's own span changes. Right to left, so
        # earlier offsets stay valid when a replacement changes the length.
        for claim in sorted(outdated, key=lambda c: c.start, reverse=True):
            entry = match_fixture(claim.text)
            if not entry or "replace" not in entry:
                continue
            old, new = entry["replace"]
            if old in claim.text:
                fixed = claim.text.replace(old, new, 1)
                answer = answer[: claim.start] + fixed + answer[claim.end :]
        return answer, mock_call("rewrite")

    async def extract_claims(self, answer: str) -> tuple[list[RawClaim], ModelCall]:
        return [classify(s) for s in sentences(answer)], mock_call("extract")

    async def judge(
        self, claim: Claim, evidence: list[Evidence], search_answer: str | None, today: str
    ) -> tuple[Judgement, ModelCall]:
        entry = match_fixture(claim.text)
        if entry is None:
            judgement = Judgement(verdict="unverified", confidence=0.0,
                                  explanation="No fixture covers this claim.",
                                  stances=["neutral"] * len(evidence))
        else:
            judgement = Judgement(verdict=entry["verdict"], confidence=entry["confidence"],
                                  current_value=entry["current_value"],
                                  explanation=entry["explanation"],
                                  stances=[r["stance"] for r in entry["results"]][: len(evidence)])
        return judgement, mock_call("judge")


class MockSearch:
    async def search(self, claim: Claim) -> SearchResult:
        # Staggered by claim position so the UI shows claims finishing one by one.
        await asyncio.sleep(SEARCH_DELAY_S * (1 + (int(claim.id[1:]) - 1) % 4))
        entry = match_fixture(claim.text)
        if entry is None:
            return SearchResult(evidence=[])
        now = datetime.now(UTC)
        evidence = [
            Evidence(
                title=r["title"],
                url=r["url"],
                snippet=r["snippet"],
                published_date=(
                    None if r["days_ago"] is None else to_iso(now - timedelta(days=r["days_ago"]))
                ),
                score=r["score"],
            )
            for r in entry["results"]
        ]
        return SearchResult(evidence=evidence, answer=entry["answer"])
