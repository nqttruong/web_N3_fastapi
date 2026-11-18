"""Application settings loaded from environment variables / the repo-root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "JLPT AI Review API"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(..., description="SQLAlchemy URL, e.g. postgresql+psycopg://...")
    test_database_url: str | None = None
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    log_level: str = "INFO"
    sql_echo: bool = False

    # --- Import (PR2) ---
    # Uploaded screenshots are stored here (relative paths in DB). Created on demand.
    import_storage_dir: Path = REPO_ROOT / "backend" / "var" / "imports"
    import_max_text_chars: int = Field(200_000, ge=1)
    import_max_html_bytes: int = Field(3_000_000, ge=1)
    import_max_images: int = Field(10, ge=1, le=50)
    import_max_image_bytes: int = Field(10 * 1024 * 1024, ge=1)
    # Long screenshots are fine (e.g. 1440 x 30000); this guards against decompression bombs.
    import_max_image_pixels: int = Field(60_000_000, ge=1)
    import_rate_limit_per_minute: int = Field(30, ge=1)
    # Uncommitted drafts (and their files) older than this are removed by `app.imports.cleanup`.
    import_draft_ttl_days: int = Field(14, ge=1)
    # Optional shared secret for the locally-installed Chrome extension capture endpoint.
    extension_import_token: SecretStr | None = None
    # Local single-user controls; pairing codes are generated one-time by the Web API.
    sync_admin_key: SecretStr | None = None
    sync_public_https_base_url: str | None = None

    # Android content packs are read directly from a local Git checkout. The scanner only
    # reads tracked JSON assets and never fetches Git remotes or executes repository code.
    android_learning_source_dir: Path | None = REPO_ROOT.parent / "app" / "N3 Sensei"
    learning_content_sync_interval_minutes: int = Field(30, ge=5, le=1440)
    learning_content_sync_max_run_seconds: int = Field(300, ge=10, le=1800)
    learning_content_sync_token: SecretStr | None = None
    mimikara_pdf_path: Path = REPO_ROOT / (
        "[VTI Mirai share] 140 - 880 TỪ VỰNG MIMIKARA N3 MINATO.xlsx - TU VUNG MIMIKARA N3.pdf"
    )

    # --- OCR (PR2) ---
    ocr_engine: Literal["tesseract", "none"] = "tesseract"
    ocr_tesseract_cmd: str = "tesseract"
    ocr_languages: str = "jpn"
    ocr_psm: int = Field(6, ge=0, le=13)
    ocr_timeout_seconds: int = Field(120, ge=5)

    # --- AI explanations (PR3) ---
    # "none" disables API generation; manual ChatGPT mode keeps working.
    ai_provider: Literal["openai", "none"] = "openai"
    openai_api_key: SecretStr | None = None
    # Must support the Responses API with Structured Outputs (configurable, not hardcoded).
    openai_model: str = "gpt-6-astra"
    ai_request_timeout: float = Field(90.0, ge=5)
    ai_max_concurrent_requests: int = Field(2, ge=1, le=16)
    ai_max_retries: int = Field(3, ge=0, le=8)  # transient errors (timeout, 429, 5xx)
    ai_max_format_retries: int = Field(1, ge=0, le=3)  # invalid/inconsistent output
    ai_max_output_tokens: int = Field(8000, ge=500)
    # Budget guards. Daily request cap always applies; the USD cap needs both prices.
    ai_max_requests_per_day: int = Field(200, ge=1)
    ai_monthly_budget_usd: float = Field(0.0, ge=0)  # 0 = no USD cap
    ai_price_input_per_1m_tokens: float | None = Field(None, ge=0)
    ai_price_output_per_1m_tokens: float | None = Field(None, ge=0)
    ai_batch_max_questions: int = Field(50, ge=1, le=500)
    ai_worker_enabled: bool = True
    ai_worker_poll_seconds: float = Field(2.0, gt=0)

    @field_validator(
        "openai_api_key",
        "extension_import_token",
        "sync_admin_key",
        "android_learning_source_dir",
        "learning_content_sync_token",
        "ai_price_input_per_1m_tokens",
        "ai_price_output_per_1m_tokens",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("extension_import_token", mode="before")
    @classmethod
    def _extension_token_minimum_length(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() and len(value.strip()) < 32:
            raise ValueError("EXTENSION_IMPORT_TOKEN must contain at least 32 characters")
        return value

    @field_validator("sync_admin_key", mode="before")
    @classmethod
    def _sync_admin_key_minimum_length(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() and len(value.strip()) < 32:
            raise ValueError("SYNC_ADMIN_KEY must contain at least 32 characters")
        return value

    @field_validator("learning_content_sync_token", mode="before")
    @classmethod
    def _learning_sync_token_minimum_length(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() and len(value.strip()) < 32:
            raise ValueError("LEARNING_CONTENT_SYNC_TOKEN must contain at least 32 characters")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must be an explicit allowlist; '*' is not allowed")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
