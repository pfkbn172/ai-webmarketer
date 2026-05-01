from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="MARKETER_",
        extra="ignore",
    )

    env: str = Field(default="development")
    base_url: str = Field(default="http://127.0.0.1:3009")
    api_port: int = Field(default=3009)

    db_dsn: str = Field(default="postgresql+asyncpg://marketer:CHANGE_ME@127.0.0.1:5432/marketer")
    db_password: str = Field(default="")
    db_pool_size: int = Field(default=5)

    fernet_key: str = Field(default="")
    jwt_secret: str = Field(default="")
    jwt_ttl_minutes: int = Field(default=60)
    jwt_refresh_ttl_days: int = Field(default=14)


settings = Settings()
