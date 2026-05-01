import pytest
from cryptography.fernet import Fernet

from app.utils import encryption
from app.utils.encryption import (
    EncryptionError,
    decrypt_json,
    decrypt_text,
    encrypt_json,
    encrypt_text,
)


@pytest.fixture(autouse=True)
def _set_fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(encryption.settings, "fernet_key", key)


def test_encrypt_decrypt_text_roundtrip() -> None:
    plain = "sk-abcdef-very-secret-key-001"
    token = encrypt_text(plain)
    assert isinstance(token, bytes)
    assert plain.encode() not in token  # 暗号文に平文が含まれない
    assert decrypt_text(token) == plain


def test_encrypt_decrypt_json_roundtrip() -> None:
    payload = {
        "access_token": "ya29.aaaa",
        "refresh_token": "1//xxxxx",
        "expires_at": 1700000000,
        "scopes": ["webmasters.readonly", "analytics.readonly"],
    }
    token = encrypt_json(payload)
    decoded = decrypt_json(token)
    assert decoded == payload


def test_decrypt_with_corrupted_token_raises() -> None:
    with pytest.raises(EncryptionError, match="復号に失敗"):
        decrypt_text(b"not-a-valid-fernet-token")


def test_encrypt_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(encryption.settings, "fernet_key", "")
    with pytest.raises(EncryptionError, match="MARKETER_FERNET_KEY が未設定"):
        encrypt_text("anything")


def test_invalid_key_format_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(encryption.settings, "fernet_key", "not-a-base64-key")
    with pytest.raises(EncryptionError, match="形式が不正"):
        encrypt_text("anything")
