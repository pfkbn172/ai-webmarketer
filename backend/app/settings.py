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

    # システム共通 AI Provider キー(テナント別資格情報がない場合のフォールバック)
    gemini_api_key_ai_engine: str = Field(default="")
    gemini_api_key_citation_monitor: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    perplexity_api_key: str = Field(default="")
    serpapi_key: str = Field(default="")

    resend_api_key: str = Field(default="")
    mail_from: str = Field(default="marketer@kiseeeen.co.jp")
    mail_notify_to: str = Field(default="")

    # SMTP リレー(Gmail 等経由のメール送信)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    # メール送信バックエンド: "smtp" / "resend" / "auto"(SMTP 設定優先 → Resend → 何もしない)
    mail_backend: str = Field(default="auto")

    # ジョブ実行対象テナント(カンマ区切り UUID 一覧)
    # Phase 1: tenants テーブルが RLS で守られているためスケジューラから列挙できない。
    # 環境変数で運用対象を明示する(マルチテナント時は将来 BYPASSRLS ロールに切替)。
    active_tenant_ids: str = Field(default="")


settings = Settings()
