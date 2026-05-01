"""API 認証情報の暗号化・復号(Fernet = AES-128-CBC + HMAC)。

設計指針 10.1:
- すべての API キー / OAuth refresh token を暗号化して DB に保管
- 平文で扱う時間を最小化(復号 → 即 API 呼び出し → 不要になったら破棄)
- ログ・エラーメッセージに認証情報を含めない

鍵は環境変数 MARKETER_FERNET_KEY で供給。生成は:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.settings import settings


class EncryptionError(Exception):
    """暗号化・復号に失敗したときの例外。元例外の詳細はログに含めない(認証情報漏洩防止)。"""


def _get_cipher() -> Fernet:
    if not settings.fernet_key:
        raise EncryptionError(
            "MARKETER_FERNET_KEY が未設定です。.env を確認してください。"
        )
    try:
        return Fernet(settings.fernet_key.encode())
    except (ValueError, TypeError) as exc:
        raise EncryptionError(f"MARKETER_FERNET_KEY の形式が不正です: {type(exc).__name__}") from None


def encrypt_text(plaintext: str) -> bytes:
    """文字列を Fernet で暗号化して bytes を返す。DB の BYTEA カラムに直接保存可。"""
    cipher = _get_cipher()
    return cipher.encrypt(plaintext.encode("utf-8"))


def decrypt_text(token: bytes) -> str:
    cipher = _get_cipher()
    try:
        return cipher.decrypt(token).decode("utf-8")
    except InvalidToken:
        raise EncryptionError("復号に失敗しました(鍵不一致 / トークン破損)") from None


def encrypt_json(payload: dict[str, Any]) -> bytes:
    """dict を JSON 化して暗号化。OAuth tokens / API キー一式の保管に使う。"""
    return encrypt_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def decrypt_json(token: bytes) -> dict[str, Any]:
    raw = decrypt_text(token)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise EncryptionError("復号後の値が dict ではありません")
    return parsed
