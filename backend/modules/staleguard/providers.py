"""The two interfaces the pipeline talks to, and the factories that pick mock or live."""

from typing import Protocol

from .config import Settings
from .llm import BifrostLLM
from .mock import MockLLM, MockSearch
from .models import Claim, Evidence, Judgement, ModelCall, RawClaim, SearchResult
from .search import TavilySearch


class LLM(Protocol):
    async def extract_claims(self, answer: str) -> tuple[list[RawClaim], ModelCall]: ...

    async def judge(
        self, claim: Claim, evidence: list[Evidence], search_answer: str | None, today: str
    ) -> tuple[Judgement, ModelCall]: ...

    async def answer(self, question: str) -> tuple[str, ModelCall]: ...

    async def rewrite(self, answer: str, outdated: list[Claim]) -> tuple[str, ModelCall]: ...


class Search(Protocol):
    async def search(self, claim: Claim) -> SearchResult: ...


def get_llm(settings: Settings) -> LLM:
    return MockLLM() if settings.mock_mode else BifrostLLM(settings)


def get_search(settings: Settings) -> Search:
    return MockSearch() if settings.mock_mode else TavilySearch(settings)
