from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The Anthropic SDK reads ANTHROPIC_API_KEY on its own; we never handle it here.
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "medium"
    max_agent_turns: int = 12

    # Free key from https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email
    # Without it, the sanctions check is reported as "not verified" instead of failing.
    portal_transparencia_api_key: str | None = None

    http_timeout_seconds: float = 15.0
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
