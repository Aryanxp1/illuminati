import os
import time
import httpx
from typing import Dict, Any, List, Optional
from ..config import settings

class BifrostClient:
    """
    Unified client for Bifrost by Maxim AI.
    Handles virtual keys, token budgeting, multi-provider failover routing, and telemetry.
    """
    def __init__(self, base_url: str = settings.BIFROST_URL, api_key: str = settings.BIFROST_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.primary_model = settings.BIFROST_PRIMARY_MODEL
        self.fallbacks = [m.strip() for m in settings.BIFROST_FALLBACK_MODELS.split(",") if m.strip()]

    def is_available(self) -> bool:
        """Check if local or remote Bifrost gateway is responding."""
        try:
            r = httpx.get(f"{self.base_url.replace('/v1', '')}/health", timeout=1.0)
            return r.status_code == 200
        except Exception:
            try:
                r = httpx.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=1.0)
                return r.status_code == 200
            except Exception:
                return False

    def get_status(self) -> Dict[str, Any]:
        available = self.is_available()
        openrouter_live = bool(settings.OPENROUTER_API_KEY)
        mode = "LIVE_BIFROST" if available else ("LIVE_OPENROUTER" if openrouter_live else "MOCK_SIMULATION")
        return {
            "gateway": "Bifrost by Maxim AI",
            "url": self.base_url,
            "connected": available or openrouter_live,
            "mode": mode,
            "primary_model": self.primary_model,
            "fallback_models": self.fallbacks,
            "virtual_key": self.api_key[:4] + "***" if self.api_key else "none",
            "openrouter_configured": openrouter_live,
            "budget_cap_usd": settings.DEFAULT_MAX_COST_USD,
            "token_budget": settings.DEFAULT_TOKEN_BUDGET
        }

    async def complete(self, prompt: str = "", system: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1500, messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Executes a completion through Bifrost with automated failover cascade.
        Falls back to OpenRouter if configured, or deterministic simulation mode.
        Supports both single prompt and multi-turn conversation messages list.
        """
        model = model or self.primary_model
        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if prompt:
                messages.append({"role": "user", "content": prompt})

        prompt_text = prompt or (messages[-1]["content"] if messages else "")

        # 1. Try live Bifrost gateway if connected
        if self.is_available():
            models_to_try = [model] + [f for f in self.fallbacks if f != model]
            for try_model in models_to_try:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": try_model,
                                "messages": messages,
                                "max_tokens": max_tokens
                            }
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data["choices"][0]["message"]["content"]
                            usage = data.get("usage", {})
                            return {
                                "content": content,
                                "model": try_model,
                                "used_fallback": try_model != model,
                                "tokens_input": usage.get("prompt_tokens", len(prompt_text) // 4),
                                "tokens_output": usage.get("completion_tokens", len(content) // 4),
                                "cost_usd": (usage.get("total_tokens", 200) / 1000) * 0.00015,
                                "mode": "LIVE_BIFROST"
                            }
                except Exception:
                    continue

        # 2. Try OpenRouter if configured and Bifrost is offline
        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com/Aryanxp1/illuminati",
                            "X-Title": "Illuminati Unified Platform"
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": max_tokens
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        usage = data.get("usage", {})
                        return {
                            "content": content,
                            "model": model,
                            "used_fallback": False,
                            "tokens_input": usage.get("prompt_tokens", len(prompt_text) // 4),
                            "tokens_output": usage.get("completion_tokens", len(content) // 4),
                            "cost_usd": (usage.get("total_tokens", 200) / 1000) * 0.00015,
                            "mode": "LIVE_OPENROUTER"
                        }
            except Exception:
                pass

        # 3. Simulation mode fallback
        sim_text = f"Simulated Bifrost completion for prompt: '{prompt_text[:60]}...'"
        tokens_in = len(prompt_text) // 4 + 15
        tokens_out = len(sim_text) // 4 + 10
        return {
            "content": sim_text,
            "model": model,
            "used_fallback": False,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost_usd": ((tokens_in + tokens_out) / 1000) * 0.00015,
            "mode": "SIMULATION_MODE"
        }

bifrost = BifrostClient()
