"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API."""

    environment: str = "development"
    database_url: str = "sqlite:///./paper_harness.db"
    data_dir: str = "../../data"
    llm_provider: str = "none"
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_api_key_env: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 4096
    llm_json_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PAPER_HARNESS_",
        extra="ignore",
    )


settings = Settings()
