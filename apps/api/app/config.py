from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Express Intelligence OS API"
    environment: str = "development"
    database_url: str = "postgresql://express:change-me@postgres:5432/express_intelligence"
    redis_url: str = "redis://redis:6379/0"
    allowed_origins: str = "http://localhost:3001"
    storage_root: str = "/data/source-files"
    google_service_account_file: str = ""
    max_file_bytes: int = 500_000_000_000
    storage_reserve_bytes: int = 100_000_000_000
    max_active_uploads: int = 2
    max_chunk_bytes: int = 64 * 1024 * 1024
    api_keys: str = ""
    require_api_key: bool = False
    rate_limit_per_minute: int = 300
    upload_rate_limit_per_minute: int = 120
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    db_pool_size: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def accepted_api_keys(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    @property
    def accepted_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
