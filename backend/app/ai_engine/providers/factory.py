"""AIProviderFactory(implementation_plan 4.2)。

ユースケース層は get_for_use_case(tenant_id, use_case) で Provider を取得する。
Factory は ai_provider_configs テーブルを見て (provider, model, prompt_template_id)
を解決し、認証情報を tenant_credentials または環境変数から取り出して
Adapter インスタンスを構築する。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.providers.base import AIProvider
from app.ai_engine.providers.gemini_adapter import GeminiAdapter
from app.ai_engine.providers.mock_adapter import MockAdapter
from app.db.models.ai_provider_config import AIProviderConfig
from app.db.models.enums import (
    AIProviderEnum,
    AIUseCaseEnum,
    CredentialProviderEnum,
)
from app.db.repositories.tenant_credential import TenantCredentialRepository
from app.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class ProviderFactoryError(Exception):
    """設定不備で Adapter を構築できない場合の例外。"""


# 新 Provider 追加時はここに 1 行足すだけ(implementation_plan 4.6)
_REGISTRY: dict[AIProviderEnum, type[AIProvider]] = {
    AIProviderEnum.gemini: GeminiAdapter,
    # AIProviderEnum.claude: ClaudeAdapter,        # Phase 2
    # AIProviderEnum.openai: OpenAIAdapter,        # Phase 2
    # AIProviderEnum.perplexity: PerplexityAdapter,# Phase 2
}


# システムデフォルト(ai_provider_configs に未登録時のフォールバック)
_DEFAULT = {
    "provider": AIProviderEnum.gemini,
    "model": "gemini-2.5-flash",
    "temperature": 0.7,
    "max_tokens": 2000,
}


class AIProviderFactory:
    """テナント × ユースケースに応じた Adapter を返す。

    Phase 1 では認証情報のソース優先度:
    1. tenant_credentials (テナント別 API キー)
    2. 環境変数(MARKETER_GEMINI_API_KEY_AI_ENGINE 等、システム共通)
    """

    @classmethod
    async def get_for_use_case(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        use_case: AIUseCaseEnum,
    ) -> AIProvider:
        # 1. ai_provider_configs を引く
        stmt = select(AIProviderConfig).where(
            AIProviderConfig.tenant_id == tenant_id,
            AIProviderConfig.use_case == use_case,
            AIProviderConfig.is_active.is_(True),
        )
        config = (await session.scalars(stmt)).one_or_none()

        provider_enum = config.provider if config else _DEFAULT["provider"]
        model = config.model_name if config else _DEFAULT["model"]

        adapter_cls = _REGISTRY.get(provider_enum)
        if adapter_cls is None:
            raise ProviderFactoryError(
                f"AIProvider {provider_enum.value} の Adapter が未実装です。"
                f"factory.py の _REGISTRY に追加してください。"
            )

        # 2. API キーを取り出す
        api_key = await cls._resolve_api_key(session, tenant_id, provider_enum)
        if not api_key:
            raise ProviderFactoryError(
                f"{provider_enum.value} の API キーが未設定です。"
                f"tenant_credentials または .env を確認してください。"
            )

        log.info(
            "ai_provider_resolved",
            tenant_id=str(tenant_id),
            use_case=use_case.value,
            provider=provider_enum.value,
            model=model,
        )
        return adapter_cls(api_key=api_key, model=model)

    @classmethod
    async def _resolve_api_key(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        provider: AIProviderEnum,
    ) -> str | None:
        repo = TenantCredentialRepository(session)
        # テナント別資格情報をまず探す
        cred_provider_map = {
            AIProviderEnum.gemini: CredentialProviderEnum.gemini_ai_engine,
            AIProviderEnum.openai: CredentialProviderEnum.openai,
            AIProviderEnum.claude: CredentialProviderEnum.anthropic,
            AIProviderEnum.perplexity: CredentialProviderEnum.perplexity,
        }
        cred = await repo.get_decrypted(tenant_id, cred_provider_map[provider])
        if cred and cred.get("api_key"):
            return cred["api_key"]

        # フォールバック: 環境変数(システム共通キー)
        env_map = {
            AIProviderEnum.gemini: getattr(settings, "gemini_api_key_ai_engine", None),
            AIProviderEnum.openai: getattr(settings, "openai_api_key", None),
            AIProviderEnum.claude: getattr(settings, "anthropic_api_key", None),
            AIProviderEnum.perplexity: getattr(settings, "perplexity_api_key", None),
        }
        return env_map.get(provider)


def make_mock_provider() -> AIProvider:
    """テストで Factory の代わりに直接使うモック。"""
    return MockAdapter()
