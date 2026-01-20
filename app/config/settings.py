"""Application configuration settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Database
    database_url: str
    pgvector_enabled: bool = True

    # Google Cloud Platform
    gcp_project_id: str
    gcs_bucket_name: str
    gcs_bucket_folder: str = "Cert_Agent"
    gcp_service_account_email: str
    gcp_service_account_key_path: str
    vertex_ai_location: str = "us-central1"

    # OCR Service
    ocr_api_url: str
    ocr_timeout: int = 300

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 180

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    workers: int = 4

    # CORS
    allowed_origins: str = "*"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins into list."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # File Upload
    max_upload_size_mb: int = 50
    allowed_file_types: str = "pdf,png,jpg,jpeg"

    @property
    def allowed_file_types_list(self) -> List[str]:
        """Parse allowed file types into list."""
        return [ft.strip() for ft in self.allowed_file_types.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    # Google Vertex AI
    vertex_ai_text_model: str = "gemini-2.0-flash-exp"
    vertex_ai_embedding_model: str = "text-embedding-004"

    # Signed URLs
    signed_url_expiration_days: int = 7

    # Rate Limiting
    rate_limit_per_minute: int = 60


# Global settings instance
settings = Settings()
