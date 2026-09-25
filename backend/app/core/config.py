from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Self-Healing Tax Filing System (India)"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./tax_filing.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "llama3.2-vision:latest"
    ollama_coder_model: str = "qwen2.5-coder:7b"
    chroma_path: Path = Path("../storage/chroma")
    storage_root: Path = Path("../storage")
    verification_threshold: float = 0.97
    enable_vision: bool = False
    checkpoint_encryption_key: str = ""
    max_upload_bytes: int = 20 * 1024 * 1024
    max_upload_documents: int = 10
    retention_days: int = 7
    max_remediation_attempts: int = 2
    tax_year: str = "2025-26"
    default_regime: str = "new"
    efile_backend: str = "json_self_file"
    form16_extractor: str = "label"
    enable_indexation_option: bool = True
    pan_masking: bool = True
    enable_azure_di: bool = False
    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    tesseract_cmd: str | None = None
    allowed_origins: str = "http://localhost:5173"
    # API key for write/read endpoints; empty disables auth (local dev only).
    api_key: str = ""
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
