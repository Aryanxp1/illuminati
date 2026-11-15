"""Prompts per stage. Extract and judge return one JSON object; answer and rewrite plain text."""

import json

from .models import Claim, Evidence

EXTRACT_SYSTEM = """You find factual claims in an AI-generated answer and judge which can go stale.

Return one JSON object: {"claims": [...]}. Each claim:
{
  "text": exact substring copied character for character from the answer (one sentence or clause),
  "category": "pricing" | "version" | "regulation" | "leadership" | "company_fact"
              | "statistic" | "other",
  "time_sensitive": true if the fact can change over time (prices, versions, laws, who leads
                    a company, counts, rates), false for timeless facts,
  "volatility": "high" | "medium" | "low" (how fast this kind of fact changes),
  "risk_reason": one short sentence on why it may be outdated,
  "search_query": a web search query that would confirm the current value
}
List claims in the order they appear. Do not paraphrase "text". Skip opinions and advice.
Return at most 15 claims; when there are more, keep the ones most likely to be outdated.
search_query must name the entity and ask for the current value
(e.g. "Spotify Premium plan current price")."""

JUDGE_SYSTEM = """You check whether a claim is still true today, using only the numbered sources.

Return one JSON object:
{
  "verdict": "current" | "outdated" | "unverified",
  "confidence": number from 0 to 1,
  "current_value": what the sources say is true now, or null when the claim is current
                   or the sources do not say,
  "explanation": one or two sentences citing the sources by number,
  "stances": one entry per source in order, each "supports" | "contradicts" | "neutral"
}
Prefer newer sources when they disagree. Use "unverified" when the sources do not settle it.
A source can only contradict the claim if it is at least as recent as the event or date the claim
describes; an older source that gives an earlier value is "neutral", not "contradicts".
When the claim names a release or change dated after the newest source and no source contradicts
it, the verdict is "unverified", not "outdated".
current_value must come from the newest source that states it."""

ANSWER_SYSTEM = """Answer the question directly and factually in one short paragraph of plain text
(at most 6 sentences). State concrete facts such as names, prices, versions and dates."""

REWRITE_SYSTEM = """You correct outdated statements in a text.

Rewrite the text changing only the listed outdated statements so they state the current value.
Keep everything else word for word, with the same length and tone. Add no new facts.
Return only the corrected text, with no preamble or notes."""


def extract_messages(answer: str, today: str) -> list[dict]:
    return [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": f"Today: {today}\nAnswer:\n{answer}"},
    ]


def judge_messages(
    claim: Claim, evidence: list[Evidence], search_answer: str | None, today: str
) -> list[dict]:
    sources = [
        {
            "n": i + 1,
            "title": e.title,
            "url": e.url,
            "published_date": e.published_date,
            "snippet": e.snippet,
        }
        for i, e in enumerate(evidence)
    ]
    user = (
        f"Today: {today}\n"
        f"Claim ({claim.category}): {claim.text}\n"
        f"Search summary (hint only, may be wrong): {search_answer or 'none'}\n"
        f"Sources:\n{json.dumps(sources, indent=1)}"
    )
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


def answer_messages(question: str) -> list[dict]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": question},
    ]


def rewrite_messages(answer: str, outdated: list[Claim]) -> list[dict]:
    fixes = "\n".join(f'- "{c.text}" -> current value: {c.current_value}' for c in outdated)
    user = f"Text:\n{answer}\n\nOutdated statements:\n{fixes}"
    return [{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": user}]
