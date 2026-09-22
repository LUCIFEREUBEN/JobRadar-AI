from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    database_url: str
    cerebras_api_key: str | None
    resend_api_key: str | None
    email_from: str | None
    email_to: str | None
    tavily_api_key: str | None
    notifications_enabled: bool
    max_ai_jobs: int
    query_budget: int

def settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./jobradar.db"),
        cerebras_api_key=os.getenv("CEREBRAS_API_KEY"), resend_api_key=os.getenv("RESEND_API_KEY"),
        email_from=os.getenv("EMAIL_FROM"), email_to=os.getenv("EMAIL_TO"), tavily_api_key=os.getenv("TAVILY_API_KEY"),
        notifications_enabled=os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true",
        max_ai_jobs=int(os.getenv("MAX_AI_JOBS_PER_RUN", "25")), query_budget=int(os.getenv("DISCOVERY_QUERY_BUDGET_PER_RUN", "6")),
    )

def yaml_config(name: str) -> dict:
    with (ROOT / "config" / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
