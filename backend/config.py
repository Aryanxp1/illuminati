import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the Illuminati unified platform
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Illuminati Unified AI Platform"
    VERSION: str = "1.0.0"
    TEAM: str = "Illuminati"
    AUTHOR: str = "Aryan Vishwakarma (@Aryanxp1)"
    
    # Execution mode: if True, uses local deterministic fixtures (no external API keys needed)
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")
    
    # Bifrost AI Gateway settings
    BIFROST_URL: str = os.getenv("BIFROST_URL", "http://localhost:8080/v1")
    BIFROST_API_KEY: str = os.getenv("BIFROST_API_KEY", "bf-illuminati-key")
    BIFROST_PRIMARY_MODEL: str = os.getenv("BIFROST_PRIMARY_MODEL", "openai/gpt-4o-mini")
    BIFROST_FALLBACK_MODELS: str = os.getenv("BIFROST_FALLBACK_MODELS", "claude-3-5-haiku,groq/gpt-oss-120b,ollama/llama3")
    
    # Tavily API settings
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # OpenRouter API settings (OpenAI / Anthropic / DeepSeek inference)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    
    # Database
    DATABASE_PATH: Path = ROOT_DIR / "illuminati.db"
    
    # Coding agent budget defaults
    DEFAULT_TOKEN_BUDGET: int = int(os.getenv("DEFAULT_TOKEN_BUDGET", "8000"))
    DEFAULT_MAX_COST_USD: float = float(os.getenv("DEFAULT_MAX_COST_USD", "0.05"))

settings = Settings()
