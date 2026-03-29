from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photographer_assistant"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Storage
    storage_backend: str = "local"  # "local" or "s3"
    storage_local_path: str = "./storage"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "photographer-assistant"

    # Upload limits
    max_upload_size_mb: int = 20
    thumbnail_max_size: int = 300
    medium_max_size: int = 1200

    # Limits per user
    max_galleries_per_user: int = 50
    max_images_per_gallery: int = 500

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "Fotobir <onboarding@resend.dev>"
    app_url: str = "http://localhost"
    password_reset_expire_minutes: int = 30

    # Pricing (for invoice generation)
    default_price_per_copy: float = 5.0
    currency: str = "RSD"

    # Rate limiting
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "5/minute"
    rate_limit_refresh: str = "10/minute"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
