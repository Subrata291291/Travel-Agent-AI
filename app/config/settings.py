from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # =========================
    # Application
    # =========================

    app_name: str = "Travel Agent"
    app_env: str = "development"
    debug: bool = True

    # =========================
    # API Keys
    # =========================

    groq_api_key: str = ""
    openrouter_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""

    # =========================
    # Models
    # =========================

    groq_model: str = "openai/gpt-oss-20b"
    openrouter_model: str = "openrouter/free"
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"

    # =========================
    # LLM Routing
    # =========================

    primary_llm: str = "groq"
    fallback_llm_1: str = "openrouter"
    fallback_llm_2: str = "gemini"
    fallback_llm_3: str = "openai"

    # =========================
    # Database
    # =========================

    database_url: str = "sqlite:///./travel_agent.db"

    # =========================
    # Authentication / JWT
    # =========================

    # Keep the secret outside the source code.
    # It should come from .env.
    jwt_secret_key: str

    # JWT signing algorithm.
    jwt_algorithm: str = "HS256"

    # Access token lifetime in minutes.
    jwt_expire_minutes: int = 60

    # =========================
    # Environment configuration
    # =========================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()