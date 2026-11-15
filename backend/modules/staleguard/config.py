import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


@dataclass
class Settings:
    mock_mode: bool = True
    bifrost_base_url: str = "http://127.0.0.1:8080"
    bifrost_api_key: str = ""
    bifrost_virtual_key: str = ""
    model_extract: str = "groq/openai/gpt-oss-120b"
    model_judge: str = "groq/openai/gpt-oss-120b"
    model_answer: str = "groq/openai/gpt-oss-120b"
    model_fallbacks: list[str] = field(default_factory=lambda: ["groq/openai/gpt-oss-20b"])
    tavily_api_key: str = ""
    max_claims: int = 8
    cache_enabled: bool = True
    rate_limit_per_minute: int = 6
    daily_live_checks: int = 100
    shared_history: bool = False
    database_path: Path = BACKEND_DIR / "data" / "ps5.db"

    @property
    def mode(self) -> str:
        return "mock" if self.mock_mode else "live"


def load_settings() -> Settings:
    # Existing environment variables win over .env values.
    load_dotenv(REPO_DIR / ".env")
    load_dotenv(BACKEND_DIR / ".env")
    env = os.environ
    defaults = Settings()
    db_path = Path(env.get("DATABASE_PATH") or defaults.database_path)
    return Settings(
        # Mock unless explicitly switched off, so a typo never triggers paid calls.
        mock_mode=env.get("MOCK_MODE", "true").strip().lower() not in ("false", "0"),
        bifrost_base_url=(env.get("BIFROST_BASE_URL") or defaults.bifrost_base_url).rstrip("/"),
        bifrost_api_key=env.get("BIFROST_API_KEY", ""),
        bifrost_virtual_key=env.get("BIFROST_VIRTUAL_KEY", ""),
        model_extract=env.get("MODEL_EXTRACT") or defaults.model_extract,
        model_judge=env.get("MODEL_JUDGE") or defaults.model_judge,
        model_answer=env.get("MODEL_ANSWER") or defaults.model_answer,
        model_fallbacks=defaults.model_fallbacks if "MODEL_FALLBACKS" not in env
        else [m.strip() for m in env["MODEL_FALLBACKS"].split(",") if m.strip()],
        tavily_api_key=env.get("TAVILY_API_KEY", ""),
        max_claims=int(env.get("MAX_CLAIMS") or defaults.max_claims),
        cache_enabled=env.get("CACHE_ENABLED", "true").strip().lower() not in ("false", "0"),
        rate_limit_per_minute=int(
            env.get("RATE_LIMIT_PER_MINUTE") or defaults.rate_limit_per_minute
        ),
        daily_live_checks=int(env.get("DAILY_LIVE_CHECKS") or defaults.daily_live_checks),
        shared_history=env.get("SHARED_HISTORY", "false").strip().lower() in ("true", "1"),
        database_path=db_path if db_path.is_absolute() else BACKEND_DIR / db_path,
    )
