"""TavilySearch: live web evidence for one claim."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from .config import Settings
from .llm import http_failure
from .models import Claim, Evidence, SearchResult, to_iso

TAVILY_URL = "https://api.tavily.com/search"
NEWS_CATEGORIES = ("leadership", "company_fact")
# Prefer recent sources for fast-moving facts; low volatility searches the whole web.
TIME_RANGES = {"high": "month", "medium": "year"}


def normalise_date(value: object) -> str | None:
    """Tavily dates come as RFC 2822 ("Tue, 11 Mar 2025 17:00:00 GMT") or ISO; return ISO UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return to_iso(dt)


class TavilySearch:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key = settings.tavily_api_key
        self.transport = transport

    async def search(self, claim: Claim) -> SearchResult:
        body = {
            "query": claim.search_query or claim.text,
            "topic": "news" if claim.category in NEWS_CATEGORIES else "general",
            "max_results": 5,
            "include_answer": True,
            "include_published_date": True,
            "search_depth": "basic",
        }
        time_range = TIME_RANGES.get(claim.volatility)
        if time_range:
            body["time_range"] = time_range
        data = await self._post(body)
        calls = 1
        if time_range and not data.get("results"):
            del body["time_range"]  # nothing recent: fall back to the unfiltered search
            data = await self._post(body)
            calls = 2
        evidence = []
        for r in data.get("results") or []:
            if not isinstance(r, dict) or not r.get("url"):
                continue
            evidence.append(
                Evidence(
                    title=str(r.get("title") or r["url"]),
                    url=str(r["url"]),
                    snippet=str(r.get("content") or "")[:500],
                    published_date=normalise_date(r.get("published_date")),
                    score=min(max(float(r.get("score") or 0), 0.0), 1.0),
                    stance="neutral",
                )
            )
        answer = data.get("answer")
        return SearchResult(
            evidence=evidence, answer=answer if isinstance(answer, str) else None, calls=calls
        )

    async def _post(self, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=20, transport=self.transport) as client:
                response = await client.post(
                    TAVILY_URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"}
                )
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot reach Tavily at {TAVILY_URL}. Check the network.") from None
        except httpx.TimeoutException:
            raise RuntimeError(f"Tavily at {TAVILY_URL} timed out after 20 s") from None
        if response.status_code != 200:
            raise RuntimeError(http_failure("Tavily search failed", response, self.api_key))
        return response.json()
