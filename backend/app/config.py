"""Application settings, loaded from environment / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QH_", env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./quickhammer.db"
    upload_dir: str = "../uploads"
    openhammer_base_url: str = "https://openhammer-api-production.up.railway.app"
    openhammer_edition: str = "10e"

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
