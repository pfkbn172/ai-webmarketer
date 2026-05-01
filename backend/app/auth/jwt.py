"""JWT 発行・検証(HS256)。

設計指針 10.1 / implementation_plan.md 6 章:
- アクセストークンは httpOnly Cookie で配布(XSS でも盗まれない)
- TTL は環境変数で制御(デフォルト 60 分)、リフレッシュトークンは 14 日
- claims:
    sub: user_id (uuid)
    role: 'admin' | 'client'
    tenant_id: 現在選択中のテナント(管理者は切替可能)
    iat / exp / jti

リフレッシュトークンは Phase 1 では実装最小限(同じ HS256 + 長い TTL、type='refresh')。
Phase 2 で漏洩対策(回転 / blacklist)を強化する。
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt

from app.settings import settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """JWT のデコード・検証失敗時の共通例外。"""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: uuid.UUID
    role: str
    tenant_id: uuid.UUID | None
    token_type: Literal["access", "refresh"]
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def issue_access_token(
    *, user_id: uuid.UUID, role: str, tenant_id: uuid.UUID | None
) -> tuple[str, datetime]:
    exp = _now() + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "iat": int(_now().timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, exp


def issue_refresh_token(*, user_id: uuid.UUID) -> tuple[str, datetime]:
    exp = _now() + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {
        "sub": str(user_id),
        "iat": int(_now().timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, exp


def decode_token(token: str) -> TokenClaims:
    if not settings.jwt_secret:
        raise TokenError("JWT_SECRET が未設定です")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"JWT 検証失敗: {exc}") from None

    token_type = payload.get("type")
    if token_type not in ("access", "refresh"):
        raise TokenError("不明な token type")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise TokenError(f"sub が不正: {exc}") from None

    tenant_id_raw = payload.get("tenant_id")
    tenant_id: uuid.UUID | None = None
    if tenant_id_raw:
        try:
            tenant_id = uuid.UUID(tenant_id_raw)
        except ValueError as exc:
            raise TokenError(f"tenant_id が不正: {exc}") from None

    return TokenClaims(
        user_id=user_id,
        role=payload.get("role", "client"),
        tenant_id=tenant_id,
        token_type=token_type,  # type: ignore[arg-type]
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )
