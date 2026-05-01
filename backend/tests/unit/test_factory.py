"""AIProviderFactory が ai_provider_configs と環境変数フォールバックで動くことを確認。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai_engine.providers.factory import AIProviderFactory, ProviderFactoryError
from app.db.models.enums import AIUseCaseEnum


async def test_uses_default_provider_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """tenant_credentials も env も無い場合は ProviderFactoryError。"""
    session = MagicMock()
    session.scalars = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=None)))

    # repo の get_decrypted を None に
    from app.ai_engine.providers import factory as f

    async def fake_get_decrypted(self, *a, **kw):
        return None

    monkeypatch.setattr(
        "app.db.repositories.tenant_credential.TenantCredentialRepository.get_decrypted",
        fake_get_decrypted,
    )
    monkeypatch.setattr(f.settings, "gemini_api_key_ai_engine", "")

    with pytest.raises(ProviderFactoryError):
        await AIProviderFactory.get_for_use_case(
            session, uuid.uuid4(), AIUseCaseEnum.theme_suggestion
        )


async def test_uses_env_fallback_when_no_tenant_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """ai_provider_configs 無し + tenant_credentials 無し + env キーありで成功。"""
    session = MagicMock()
    session.scalars = AsyncMock(return_value=MagicMock(one_or_none=MagicMock(return_value=None)))

    from app.ai_engine.providers import factory as f

    async def fake_get_decrypted(self, *a, **kw):
        return None

    monkeypatch.setattr(
        "app.db.repositories.tenant_credential.TenantCredentialRepository.get_decrypted",
        fake_get_decrypted,
    )
    monkeypatch.setattr(f.settings, "gemini_api_key_ai_engine", "test-key")

    provider = await AIProviderFactory.get_for_use_case(
        session, uuid.uuid4(), AIUseCaseEnum.theme_suggestion
    )
    assert provider.name == "gemini"
