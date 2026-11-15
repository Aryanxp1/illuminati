"""run_check: [answer] -> extract -> flag -> search -> judge -> score -> [rewrite].

Progress is saved after every step so polling clients see claims fill in.
"""

import asyncio
import difflib
import hashlib
import re
import time
from datetime import UTC, datetime, timedelta

from . import spans, store
from .config import Settings
from .models import CachedVerification, Check, Claim, Judgement, to_iso
from .providers import LLM, Search
from .scoring import label_for, overall_score, score_claim, summarize

VOLATILITY_RANK = {"high": 0, "medium": 1, "low": 2}
CONCURRENCY = 4
MAX_ANSWER_CHARS = 8000
CACHE_TTL = {"high": timedelta(hours=6), "medium": timedelta(hours=24), "low": timedelta(days=7)}
UNBACKED = "The sources did not clearly support or contradict this claim."


def short_error(exc: Exception) -> str:
    return (str(exc) or type(exc).__name__)[:200]


def truncate(text: str, limit: int = MAX_ANSWER_CHARS) -> str:
    """Cut to `limit` chars, ending at the last sentence boundary when there is one."""
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    end = max(window.rfind(p + w) for p in ".!?" for w in " \n")
    return text[: end + 1] if end > 0 else text[:limit]


def cache_key(settings: Settings, text: str) -> str:
    # Mode and judge model are part of the key, so mock fixtures never answer a live check.
    key = f"{settings.mode}|{settings.model_judge}|{' '.join(text.lower().split())}"
    return hashlib.sha256(key.encode()).hexdigest()


def cached_verification(
    settings: Settings, claim: Claim, now: datetime
) -> CachedVerification | None:
    row = store.cache_get(settings.database_path, cache_key(settings, claim.text))
    if row is None:
        return None
    created_at, data = row
    cached = CachedVerification.model_validate_json(data)
    if now - datetime.fromisoformat(created_at) > CACHE_TTL[cached.volatility]:
        return None
    return cached


def save(settings: Settings, check: Check, started: float) -> None:
    check.summary = summarize(check.claims)
    check.overall_score = overall_score(check.claims)
    calls = check.model_calls
    check.usage.llm_calls = len(calls)
    check.usage.prompt_tokens = sum(c.prompt_tokens for c in calls)
    check.usage.completion_tokens = sum(c.completion_tokens for c in calls)
    check.usage.duration_ms = round((time.perf_counter() - started) * 1000)
    store.save(settings.database_path, check)


async def run_check(check_id: str, settings: Settings, llm: LLM, search: Search) -> Check:
    started = time.perf_counter()
    check = store.get(settings.database_path, check_id)
    try:
        await _run(check, settings, llm, search, started)
    except Exception as exc:
        # Never leave a check stuck in a running status: the client polls until done/error.
        check.status = "error"
        check.error = f"Check failed: {short_error(exc)}"
        save(settings, check, started)
    return check


def apply(claim: Claim, judgement: Judgement, now: datetime) -> None:
    # A verdict counts only when at least one source takes that side.
    backing = {"current": "supports", "outdated": "contradicts"}.get(judgement.verdict)
    if backing and not any(e.stance == backing for e in claim.evidence):
        judgement = judgement.model_copy(update={
            "verdict": "unverified",
            "current_value": None,
            "explanation": " ".join(filter(None, (UNBACKED, judgement.explanation))),
        })
    score, breakdown = score_claim(judgement.verdict, judgement.confidence,
                                   claim.category, claim.volatility, claim.evidence, now)
    claim.verdict = judgement.verdict
    claim.confidence = judgement.confidence
    claim.current_value = judgement.current_value
    claim.explanation = judgement.explanation
    claim.freshness_score = score
    claim.score_breakdown = breakdown
    claim.label = label_for(judgement.verdict, score)


def rewrite_stays_in_claims(answer: str, rewritten: str, claims: list[Claim]) -> bool:
    """True when every word-level change lies inside one claim's span (plus edge punctuation)."""
    old = [m.span() for m in re.finditer(r"\S+", answer)]
    new = re.findall(r"\S+", rewritten)
    allowed = []
    for c in claims:
        start, end = c.start, c.end
        while start > 0 and not (answer[start - 1].isalnum() or answer[start - 1].isspace()):
            start -= 1
        while end < len(answer) and not (answer[end].isalnum() or answer[end].isspace()):
            end += 1
        allowed.append((start, end))

    def inside(lo: int, hi: int) -> bool:
        return any(start <= lo and hi <= end for start, end in allowed)

    matcher = difflib.SequenceMatcher(None, [answer[a:b] for a, b in old], new, autojunk=False)
    for tag, i1, i2, _, _ in matcher.get_opcodes():
        if tag == "equal":
            continue
        if i1 < i2:
            ok = inside(old[i1][0], old[i2 - 1][1])
        else:
            # An insertion must sit between two words of the same claim, so text added
            # before or after a claim (a new sentence, say) is rejected.
            ok = 0 < i1 < len(old) and inside(old[i1 - 1][0], old[i1][1])
        if not ok:
            return False
    return True


async def _run(check: Check, settings: Settings, llm: LLM, search: Search, started: float) -> None:
    if not check.answer:
        check.status = "generating"
        save(settings, check, started)
        try:
            text, call = await llm.answer(check.question)
        except Exception as exc:
            check.status = "error"
            check.error = f"Answer generation failed: {short_error(exc)}"
            save(settings, check, started)
            return
        check.model_calls.append(call)
        check.answer = truncate(text)

    check.status = "extracting"
    save(settings, check, started)

    try:
        raw_claims, call = await llm.extract_claims(check.answer)
    except Exception as exc:
        check.status = "error"
        check.error = f"Claim extraction failed: {short_error(exc)}"
        save(settings, check, started)
        return
    check.model_calls.append(call)

    used: set[int] = set()
    located = []
    for raw in raw_claims:
        span = spans.locate(check.answer, raw.text, used)
        if span is None:
            continue  # not a real substring of the answer
        used.add(span[0])
        located.append((span, raw))
    located.sort(key=lambda item: item[0][0])
    check.claims = [
        Claim(**raw.model_dump(), id=f"c{i}", start=start, end=end)
        for i, ((start, end), raw) in enumerate(located, 1)
    ]
    for c in check.claims:
        c.text = check.answer[c.start : c.end]  # the normalised match may differ in whitespace

    flagged = sorted(
        (c for c in check.claims if c.time_sensitive), key=lambda c: VOLATILITY_RANK[c.volatility]
    )
    to_verify = flagged[: settings.max_claims]
    verify_ids = {c.id for c in to_verify}
    for c in check.claims:
        if c.id not in verify_ids:
            c.status = "skipped"
    check.status = "verifying"
    save(settings, check, started)

    now = datetime.now(UTC)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def verify(claim: Claim) -> None:
        async with semaphore:
            claim.status = "verifying"
            save(settings, check, started)
            try:
                cached = settings.cache_enabled and cached_verification(settings, claim, now)
                if cached:
                    claim.evidence = cached.evidence
                    judgement = Judgement(verdict=cached.verdict, confidence=cached.confidence,
                                          current_value=cached.current_value,
                                          explanation=cached.explanation or "")
                    claim.cached = True
                    check.usage.cache_hits += 1
                else:
                    result = await search.search(claim)
                    check.usage.search_calls += result.calls
                    claim.evidence = result.evidence
                    if result.evidence:
                        judgement, call = await llm.judge(
                            claim, result.evidence, result.answer, now.date().isoformat()
                        )
                        check.model_calls.append(call)
                        for item, stance in zip(claim.evidence, judgement.stances, strict=False):
                            item.stance = stance
                    else:
                        judgement = Judgement(verdict="unverified", confidence=0.0,
                                              explanation="No sources found for this claim.")
                apply(claim, judgement, now)
                # Only verifications backed by sources are worth reusing.
                if settings.cache_enabled and not claim.cached and claim.evidence:
                    entry = CachedVerification(
                        volatility=claim.volatility, verdict=judgement.verdict,
                        confidence=judgement.confidence, current_value=judgement.current_value,
                        explanation=judgement.explanation, evidence=claim.evidence,
                    )
                    store.cache_put(settings.database_path, cache_key(settings, claim.text),
                                    to_iso(now), entry.model_dump_json())
                claim.status = "done"
            except Exception as exc:
                claim.status = "error"
                claim.error = short_error(exc)
                apply(claim, Judgement(verdict="unverified", confidence=0.0,
                                       explanation="Verification failed for this claim."), now)
            save(settings, check, started)

    await asyncio.gather(*(verify(c) for c in to_verify))

    outdated = [c for c in check.claims if c.verdict == "outdated" and c.current_value]
    if outdated:
        try:
            corrected, call = await llm.rewrite(check.answer, outdated)
            check.model_calls.append(call)
            if rewrite_stays_in_claims(check.answer, corrected, outdated):
                check.corrected_answer = corrected
        except Exception:
            pass  # the report stands on its own; corrected_answer stays null
    check.status = "done"
    save(settings, check, started)
