from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photographer_assistant"

    # Auth0
    auth0_domain: str = "dev-xurif6k6cvmaiq7h.us.auth0.com"
    auth0_audience: str = "https://fotomil.xyz/api"
    auth0_algorithms: list[str] = ["RS256"]

    auth0_client_id: str = "qN5srsmAHZ0R0FjidNIhuBzzdbC1Bhhm"
    auth0_mgmt_client_id: str = ""
    auth0_mgmt_client_secret: str = ""

    # Admin
    admin_emails: list[str] = []

    # Lab portal auth
    jwt_secret_key: str = "change-me-in-production-12345"
    lab_token_expire_hours: int = 24

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

    # Email (Resend) — used for notifications, not auth
    resend_api_key: str = ""
    email_from: str = "FotoMil <noreply@fotomil.xyz>"
    app_url: str = "http://localhost"

    # Pricing (for invoice generation)
    default_price_per_copy: float = 5.0
    currency: str = "RSD"

    # Rate limiting
    rate_limit_default: str = "30/minute"

    # Sentry
    sentry_dsn: str = ""
    sentry_environment: str = "development"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
