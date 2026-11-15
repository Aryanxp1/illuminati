"""BifrostLLM: chat completions through the Bifrost gateway (chat completions API)."""

import asyncio
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from . import prompts
from .config import Settings
from .models import Claim, Evidence, Judgement, ModelCall, RawClaim

STANCES = ("supports", "contradicts", "neutral")
RETRY_DELAYS = (2, 4)  # seconds before retries after an HTTP 429
MAX_RETRY_AFTER = 10
FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json(content: str) -> dict:
    fenced = FENCE.search(content)
    if fenced:
        text = fenced.group(1)
    else:
        # Fallback models may ignore response_format and wrap the object in prose.
        start, end = content.find("{"), content.rfind("}")
        text = content[start : end + 1] if 0 <= start < end else content
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def http_failure(prefix: str, response: httpx.Response, *secrets: str) -> str:
    """`prefix: HTTP <code>[: server message]`, with any configured key masked out."""
    message = f"{prefix}: HTTP {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return message
    detail = (data.get("error") or data.get("detail")) if isinstance(data, dict) else None
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("error")
    if not detail:
        return message
    detail = str(detail)
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "***")
    return f"{message}: {detail[:200]}"


def served_by(requested: str, data: dict) -> tuple[str, bool]:
    """Which provider/model answered, and whether it was a fallback.

    Bifrost reports this in extra_fields.routing_info; fall back to the response model field.
    """
    extra = data.get("extra_fields")
    extra = extra if isinstance(extra, dict) else {}
    routing = extra.get("routing_info")
    routing = routing if isinstance(routing, dict) else {}
    provider = routing.get("provider") or extra.get("provider")
    model = routing.get("model") or data.get("model")
    if not model:
        served = requested
    elif provider:
        # Model ids may contain a slash themselves (groq reports openai/gpt-oss-120b).
        served = model if model.startswith(f"{provider}/") else f"{provider}/{model}"
    elif requested.split("/", 1)[-1] == model:
        served = requested
    else:
        served = model
    is_fallback = routing.get("is_fallback")
    if not isinstance(is_fallback, bool):
        is_fallback = served != requested
    return served, is_fallback


class BifrostLLM:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self.headers = {}
        if settings.bifrost_api_key:
            self.headers["Authorization"] = f"Bearer {settings.bifrost_api_key}"
        if settings.bifrost_virtual_key:
            self.headers["x-bf-vk"] = settings.bifrost_virtual_key

    async def _complete(
        self, stage: str, model: str, messages: list[dict], json_mode: bool
    ) -> tuple[str, ModelCall]:
        """One chat completion: returns the message content and the call record."""
        body = {"model": model, "messages": messages, "temperature": 0}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        fallbacks = [m for m in self.settings.model_fallbacks if m != model]
        if fallbacks:
            body["fallbacks"] = fallbacks
        url = self.settings.bifrost_base_url
        started = time.perf_counter()
        for delay in (*RETRY_DELAYS, None):
            try:
                async with httpx.AsyncClient(
                    base_url=url, headers=self.headers, timeout=60, transport=self.transport
                ) as client:
                    response = await client.post("/v1/chat/completions", json=body)
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot reach the Bifrost gateway at {url}. Is it running?"
                ) from None
            except httpx.TimeoutException:
                raise RuntimeError(f"Bifrost gateway at {url} timed out after 60 s") from None
            if response.status_code != 429 or delay is None:
                break
            try:
                delay = min(float(response.headers["Retry-After"]), MAX_RETRY_AFTER)
            except (KeyError, ValueError):
                pass
            await asyncio.sleep(delay)
        if response.status_code != 200:
            raise RuntimeError(http_failure(
                "Bifrost request failed", response,
                self.settings.bifrost_api_key, self.settings.bifrost_virtual_key,
            ))
        data = response.json()
        usage = data.get("usage") or {}
        served, is_fallback = served_by(model, data)
        call = ModelCall(
            stage=stage,
            requested=model,
            served_by=served,
            is_fallback=is_fallback,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        return content if isinstance(content, str) else "", call

    async def _chat(self, stage: str, model: str, messages: list[dict], parse: Callable):
        for attempt in range(2):
            content, call = await self._complete(stage, model, messages, json_mode=True)
            try:
                return parse(parse_json(content)), call
            except (KeyError, IndexError, TypeError, ValueError, ValidationError):
                if attempt:
                    raise ValueError(f"{model} returned invalid JSON for {stage}") from None

    async def _text(self, stage: str, model: str, messages: list[dict]) -> tuple[str, ModelCall]:
        content, call = await self._complete(stage, model, messages, json_mode=False)
        if not content.strip():
            raise ValueError(f"{model} returned an empty {stage}")
        return content.strip(), call

    async def answer(self, question: str) -> tuple[str, ModelCall]:
        messages = prompts.answer_messages(question)
        return await self._text("answer", self.settings.model_answer, messages)

    async def rewrite(self, answer: str, outdated: list[Claim]) -> tuple[str, ModelCall]:
        messages = prompts.rewrite_messages(answer, outdated)
        return await self._text("rewrite", self.settings.model_judge, messages)

    async def extract_claims(self, answer: str) -> tuple[list[RawClaim], ModelCall]:
        def parse(data: dict) -> list[RawClaim]:
            items = data["claims"]
            if not isinstance(items, list):
                raise ValueError("claims must be a list")
            claims = []
            for item in items:
                try:
                    claims.append(RawClaim.model_validate(item))
                except ValidationError:
                    continue  # one malformed claim should not discard the rest
            return claims

        messages = prompts.extract_messages(answer, datetime.now(UTC).date().isoformat())
        return await self._chat("extract", self.settings.model_extract, messages, parse)

    async def judge(
        self, claim: Claim, evidence: list[Evidence], search_answer: str | None, today: str
    ) -> tuple[Judgement, ModelCall]:
        def parse(data: dict) -> Judgement:
            raw = data.get("stances")
            raw = raw if isinstance(raw, list) else []
            stances = [s if s in STANCES else "neutral" for s in raw[: len(evidence)]]
            stances += ["neutral"] * (len(evidence) - len(stances))
            confidence = min(max(float(data.get("confidence") or 0), 0.0), 1.0)
            return Judgement.model_validate(data | {"stances": stances, "confidence": confidence})

        messages = prompts.judge_messages(claim, evidence, search_answer, today)
        return await self._chat("judge", self.settings.model_judge, messages, parse)
