from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_model_hard: str | None = None
    anthropic_effort: str = "medium"    # low | medium | high | xhigh | max
    llm_concurrency: int = 6            # model calls in flight per request
    engine: str = "llm"                 # "llm" or "offline": where candidates come from when a request does not say

    database_url: str = "sqlite:///./aimpg.db"

    sandbox_timeout_s: float = 10.0
    sandbox_concurrency: int = 2
    request_budget_s: float = 240.0

    key_daily_quota: int = 200          # problems per invite code per UTC day
    daily_spend_cap_usd: float = 5.0    # all codes combined
    include_debug: bool = False         # sympy fields + difficulty_features in responses


settings = Settings()
