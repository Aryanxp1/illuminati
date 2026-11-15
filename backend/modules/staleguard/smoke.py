"""Live smoke test: `uv run python -m app.smoke`.

Always uses the real Bifrost and Tavily clients, whatever MOCK_MODE says. Exit 0 only if all pass.
"""

import asyncio
import dataclasses
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from . import store
from .config import Settings, load_settings
from .llm import BifrostLLM
from .models import Check, Claim, to_iso
from .pipeline import run_check, short_error
from .search import TavilySearch

SENTENCE = "The latest stable version of Python is 3.12."


async def run(settings: Settings) -> bool:
    llm, search = BifrostLLM(settings), TavilySearch(settings)

    bifrost_ok = False
    try:
        _, call = await llm.extract_claims(SENTENCE)
        print(f"PASS bifrost  served_by={call.served_by} latency={call.latency_ms}ms")
        bifrost_ok = True
    except Exception as exc:
        message = short_error(exc)
        if "401" in message and "virtual key" in message.lower():
            hint = ("Set BIFROST_VIRTUAL_KEY (starting with sk-bf-) in .env and restart the "
                    "gateway.")
        else:
            hint = (
                f"Check: is the gateway running at {settings.bifrost_base_url}? "
                f"Is GROQ_API_KEY set for Bifrost? "
                f"Is '{settings.model_extract}' a valid provider/model name?"
            )
        print(f"FAIL bifrost  {message}. {hint}")

    tavily_ok = False
    if not settings.tavily_api_key:
        print("FAIL tavily  TAVILY_API_KEY is not set. Add it to .env.")
    else:
        claim = Claim(id="c1", text=SENTENCE, start=0, end=len(SENTENCE), category="version",
                      time_sensitive=True, volatility="high", risk_reason="",
                      search_query="Python latest stable version")
        try:
            result = await search.search(claim)
            print(f"PASS tavily  {len(result.evidence)} results")
            tavily_ok = True
        except Exception as exc:
            print(f"FAIL tavily  {short_error(exc)}. Check TAVILY_API_KEY and your plan limits.")

    if not (bifrost_ok and tavily_ok):
        return False

    with tempfile.TemporaryDirectory() as tmp:
        # Throwaway database and no cache, so the smoke run neither pollutes history nor
        # passes on stale results.
        live = dataclasses.replace(settings, mock_mode=False, cache_enabled=False,
                                   database_path=Path(tmp) / "smoke.db")
        store.init(live.database_path)
        store.save(live.database_path, Check(id="smoke", created_at=to_iso(datetime.now(UTC)),
                                             status="queued", mode="live", answer=SENTENCE))
        check = await run_check("smoke", live, llm, search)
    passed = check.status == "done"
    labels = ", ".join(f"{c.label or c.status}" for c in check.claims) or "no claims"
    print(
        f"{'PASS' if passed else 'FAIL'} check  status={check.status} claims=[{labels}] "
        f"overall={check.overall_score} llm_calls={check.usage.llm_calls} "
        f"searches={check.usage.search_calls} duration={check.usage.duration_ms}ms"
        + (f" error={check.error}" if check.error else "")
    )
    return passed


def main() -> int:
    return 0 if asyncio.run(run(load_settings())) else 1


if __name__ == "__main__":
    sys.exit(main())
